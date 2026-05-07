"""Chat endpoint for RAG queries."""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatRequest, ChatResponse
from app.retrieval.retriever import retrieve_articles
from app.llm.client import generate_answer_with_citations, OpenRouterError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_AI_UNAVAILABLE = (
    "The AI service is temporarily unavailable. "
    "Please try again in a few moments."
)


async def _log_query(
    db: AsyncSession,
    *,
    query: str,
    intent: str,
    year: int | None,
    section: str | None,
    answer: str | None,
    retrieved_count: int,
    research_steps: int,
    response_time_ms: int,
    cited_articles: list[str],
    error_occurred: bool = False,
):
    """Insert a row into query_logs. Never raises — logging must not break the response."""
    try:
        cited = ",".join(cited_articles) if cited_articles else None
        await db.execute(
            text("""
                INSERT INTO query_logs
                    (query, intent, year, section, answer, retrieved_count,
                     research_steps, response_time_ms, cited_articles, error_occurred)
                VALUES
                    (:query, :intent, :year, :section, :answer, :retrieved_count,
                     :research_steps, :response_time_ms, :cited_articles, :error_occurred)
            """),
            {
                "query": query[:2000],
                "intent": intent,
                "year": year,
                "section": section,
                "answer": answer[:4000] if answer else None,
                "retrieved_count": retrieved_count,
                "research_steps": research_steps,
                "response_time_ms": response_time_ms,
                "cited_articles": cited,
                "error_occurred": error_occurred,
            }
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to log query: %s", exc)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask a question about F1 regulations.

    Process:
    1. Detect intent locally (free, instant).
    2. Single LLM call: extract filters + rewrite query (prepare_search).
    3. Agentic retrieval loop (max 3 steps).
    4. Return answer with citations.
    """
    t_start = time.monotonic()

    try:
        from app.llm.client import LLMClient
        llm_client = LLMClient()

        # Step 1: Detect Intent (local, no LLM)
        intent = await llm_client.detect_intent(request.query)

        if intent == "CONVERSATIONAL":
            logger.info("Routing CONVERSATIONAL: %s", request.query[:80])
            answer = await llm_client.generate_conversational_response(request.query)
            ms = int((time.monotonic() - t_start) * 1000)
            await _log_query(
                db, query=request.query, intent="CONVERSATIONAL",
                year=None, section=None, answer=answer,
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[],
            )
            return ChatResponse(
                answer=answer,
                citations=[],
                retrieved_count=0,
                research_steps=[]
            )

        logger.info("Routing REGULATIONS: %s", request.query[:80])

        # Step 2: One LLM call -- extract filters + rewrite query
        try:
            prepared = await llm_client.prepare_search(request.query)
        except OpenRouterError:
            ms = int((time.monotonic() - t_start) * 1000)
            await _log_query(
                db, query=request.query, intent="REGULATIONS",
                year=None, section=None, answer=_AI_UNAVAILABLE,
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[], error_occurred=True,
            )
            return ChatResponse(
                answer=_AI_UNAVAILABLE,
                citations=[],
                retrieved_count=0,
                research_steps=[]
            )

        query_year = request.year or prepared.get("year")
        query_section = request.section or prepared.get("section")
        expanded_query = prepared.get("search_query", request.query)

        # Step 3: Initial retrieval
        articles = await retrieve_articles(
            db=db,
            query=expanded_query,
            year=query_year,
            section=query_section,
            issue=request.issue,
        )

        if not articles:
            ms = int((time.monotonic() - t_start) * 1000)
            no_results_msg = "I couldn't find specific regulations matching your query. Could you please clarify your question or adjust the filters (year, section, etc.)?"
            await _log_query(
                db, query=request.query, intent="REGULATIONS",
                year=query_year, section=query_section, answer=no_results_msg,
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[],
            )
            return ChatResponse(
                answer=no_results_msg,
                citations=[],
                retrieved_count=0
            )

        # Agentic Research Loop (max 3 steps)
        all_retrieved_articles = []
        research_history = []
        max_steps = 3
        current_step_query = expanded_query

        for step in range(max_steps):
            logger.debug("Research step %d, query: %s", step + 1, current_step_query[:80])

            new_articles = await retrieve_articles(
                db=db,
                query=current_step_query,
                year=query_year,
                section=query_section,
                issue=request.issue,
                top_k=5
            )

            seen_codes = {a.article_code for a in all_retrieved_articles}
            for na in new_articles:
                if na.article_code not in seen_codes:
                    all_retrieved_articles.append(na)
                    seen_codes.add(na.article_code)

            try:
                result = await llm_client.generate_reasoning_step(
                    query=request.query,
                    articles=all_retrieved_articles,
                    history=research_history
                )
            except OpenRouterError:
                ms = int((time.monotonic() - t_start) * 1000)
                codes = [a.article_code for a in all_retrieved_articles]
                await _log_query(
                    db, query=request.query, intent="REGULATIONS",
                    year=query_year, section=query_section, answer=_AI_UNAVAILABLE,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=len(research_history),
                    response_time_ms=ms, cited_articles=codes, error_occurred=True,
                )
                return ChatResponse(
                    answer=_AI_UNAVAILABLE,
                    citations=llm_client._extract_citations(all_retrieved_articles),
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=research_history
                )

            research_history.append({
                "step": step + 1,
                "thought": result.get("thought", ""),
                "action": result.get("action", ""),
                "query": current_step_query
            })

            if result.get("action") == "ANSWER":
                answer = result.get("answer")
                citations = llm_client._extract_citations(all_retrieved_articles)
                codes = [a.article_code for a in all_retrieved_articles]

                display_steps = research_history
                if len(research_history) == 1:
                    thought = research_history[0].get("thought", "").lower()
                    if any(k in thought for k in ["greeting", "hola", "spanish", "not a specific question", "common courtesy"]):
                        display_steps = []
                        citations = []
                        codes = []

                ms = int((time.monotonic() - t_start) * 1000)
                await _log_query(
                    db, query=request.query, intent="REGULATIONS",
                    year=query_year, section=query_section, answer=answer,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=len(research_history),
                    response_time_ms=ms, cited_articles=codes,
                )
                return ChatResponse(
                    answer=answer,
                    citations=citations,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=display_steps
                )

            elif result.get("action") == "SEARCH":
                current_step_query = result.get("search_query", expanded_query)
            else:
                break

        # Final fallback if loop finishes without ANSWER
        try:
            final_answer, final_citations = await generate_answer_with_citations(
                query=request.query,
                articles=all_retrieved_articles
            )
        except OpenRouterError:
            ms = int((time.monotonic() - t_start) * 1000)
            codes = [a.article_code for a in all_retrieved_articles]
            await _log_query(
                db, query=request.query, intent="REGULATIONS",
                year=query_year, section=query_section, answer=_AI_UNAVAILABLE,
                retrieved_count=len(all_retrieved_articles),
                research_steps=len(research_history),
                response_time_ms=ms, cited_articles=codes, error_occurred=True,
            )
            return ChatResponse(
                answer=_AI_UNAVAILABLE,
                citations=llm_client._extract_citations(all_retrieved_articles),
                retrieved_count=len(all_retrieved_articles),
                research_steps=research_history
            )

        ms = int((time.monotonic() - t_start) * 1000)
        codes = [a.article_code for a in all_retrieved_articles]
        await _log_query(
            db, query=request.query, intent="REGULATIONS",
            year=query_year, section=query_section, answer=final_answer,
            retrieved_count=len(all_retrieved_articles),
            research_steps=len(research_history),
            response_time_ms=ms, cited_articles=codes,
        )
        return ChatResponse(
            answer=final_answer,
            citations=final_citations,
            retrieved_count=len(all_retrieved_articles),
            research_steps=research_history
        )

    except Exception as e:
        logger.error("Unexpected error in chat endpoint: %s", e, exc_info=True)
        ms = int((time.monotonic() - t_start) * 1000)
        try:
            await _log_query(
                db, query=request.query, intent="UNKNOWN",
                year=None, section=None, answer=str(e),
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[], error_occurred=True,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your query: {str(e)}"
        )


@router.get("/chat/health")
async def chat_health():
    """Health check for chat endpoint."""
    return {"status": "healthy", "service": "chat", "message": "RAG system operational"}
