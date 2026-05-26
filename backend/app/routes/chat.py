"""Chat endpoint for RAG queries."""
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.llm.client import OpenRouterError, generate_answer_with_citations
from app.models import ChatRequest, ChatResponse, FeedbackRequest, StatsResponse
from app.retrieval.retriever import HybridRetriever, retrieve_articles

limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_AI_UNAVAILABLE = (
    "The AI service is temporarily unavailable. "
    "Please try again in a few moments."
)

# Hard timeout per agentic step (seconds). Prevents runaway requests on Render free tier.
_STEP_TIMEOUT_S = 22.0


def _citations_or_fallback(citations, all_retrieved_articles):
    """
    If the LLM returned 0 parsed citations, fall back to the top-3 retrieved articles.
    This ensures the user always gets relevant article references.
    """
    if citations:
        return citations
    return list(all_retrieved_articles[:3])


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
) -> Optional[int]:
    """Insert a row into query_logs. Returns the new row ID, or None on failure."""
    try:
        cited = ",".join(cited_articles) if cited_articles else None
        result = await db.execute(
            text("""
                INSERT INTO query_logs
                    (query, intent, year, section, answer, retrieved_count,
                     research_steps, response_time_ms, cited_articles, error_occurred)
                VALUES
                    (:query, :intent, :year, :section, :answer, :retrieved_count,
                     :research_steps, :response_time_ms, :cited_articles, :error_occurred)
                RETURNING id
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
        row = result.fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.warning("Failed to log query: %s", exc)
        return None


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(
    request: Request,
    body: ChatRequest,
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
        intent = await llm_client.detect_intent(body.query)

        if intent == "CONVERSATIONAL":
            logger.info("Routing CONVERSATIONAL: %s", body.query[:80])
            answer = await llm_client.generate_conversational_response(body.query)
            ms = int((time.monotonic() - t_start) * 1000)
            qid = await _log_query(
                db, query=body.query, intent="CONVERSATIONAL",
                year=None, section=None, answer=answer,
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[],
            )
            return ChatResponse(
                answer=answer,
                citations=[],
                retrieved_count=0,
                research_steps=[],
                query_id=qid,
            )

        logger.info("Routing REGULATIONS: %s", body.query[:80])

        # Step 2: One LLM call -- extract filters + rewrite query
        try:
            prepared = await llm_client.prepare_search(body.query)
        except OpenRouterError:
            ms = int((time.monotonic() - t_start) * 1000)
            await _log_query(
                db, query=body.query, intent="REGULATIONS",
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

        query_year = body.year or prepared.get("year")
        query_section = body.section or prepared.get("section")
        expanded_query = prepared.get("search_query", body.query)

        # Step 3: Initial retrieval — use HybridRetriever directly to capture confidence
        _retriever = HybridRetriever(db)
        articles = await _retriever.retrieve(
            query=expanded_query,
            year=query_year,
            section=query_section,
            issue=body.issue,
        )
        retrieval_confidence = _retriever.confidence

        if not articles:
            ms = int((time.monotonic() - t_start) * 1000)
            no_results_msg = "I couldn't find specific regulations matching your query. Could you please clarify your question or adjust the filters (year, section, etc.)?"
            qid = await _log_query(
                db, query=body.query, intent="REGULATIONS",
                year=query_year, section=query_section, answer=no_results_msg,
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[],
            )
            return ChatResponse(
                answer=no_results_msg,
                citations=[],
                retrieved_count=0,
                query_id=qid,
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
                issue=body.issue,
                top_k=8
            )

            seen_codes = {a.article_code for a in all_retrieved_articles}
            for na in new_articles:
                if na.article_code not in seen_codes:
                    all_retrieved_articles.append(na)
                    seen_codes.add(na.article_code)

            try:
                result = await asyncio.wait_for(
                    llm_client.generate_reasoning_step(
                        query=body.query,
                        articles=all_retrieved_articles,
                        history=research_history,
                    ),
                    timeout=_STEP_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                logger.warning("Agentic step %d timed out after %.0fs", step + 1, _STEP_TIMEOUT_S)
                break
            except OpenRouterError:
                ms = int((time.monotonic() - t_start) * 1000)
                codes = [a.article_code for a in all_retrieved_articles]
                await _log_query(
                    db, query=body.query, intent="REGULATIONS",
                    year=query_year, section=query_section, answer=_AI_UNAVAILABLE,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=len(research_history),
                    response_time_ms=ms, cited_articles=codes, error_occurred=True,
                )
                return ChatResponse(
                    answer=_AI_UNAVAILABLE,
                    citations=llm_client._extract_citations(all_retrieved_articles, None),
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
                citations = _citations_or_fallback(
                    llm_client._extract_citations(all_retrieved_articles, answer),
                    all_retrieved_articles,
                )
                codes = [c.article_code for c in citations]

                display_steps = research_history
                if len(research_history) == 1:
                    thought = research_history[0].get("thought", "").lower()
                    if any(k in thought for k in ["greeting", "hola", "spanish", "not a specific question", "common courtesy"]):
                        display_steps = []
                        citations = []
                        codes = []

                ms = int((time.monotonic() - t_start) * 1000)
                qid = await _log_query(
                    db, query=body.query, intent="REGULATIONS",
                    year=query_year, section=query_section, answer=answer,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=len(research_history),
                    response_time_ms=ms, cited_articles=codes,
                )
                return ChatResponse(
                    answer=answer,
                    citations=citations,
                    retrieved_count=len(all_retrieved_articles),
                    research_steps=display_steps,
                    query_id=qid,
                    confidence=retrieval_confidence,
                )

            elif result.get("action") == "SEARCH":
                current_step_query = result.get("search_query", expanded_query)
            else:
                break

        # Final fallback if loop finishes without ANSWER
        try:
            final_answer, final_citations = await generate_answer_with_citations(
                query=body.query,
                articles=all_retrieved_articles
            )
        except OpenRouterError:
            ms = int((time.monotonic() - t_start) * 1000)
            codes = [a.article_code for a in all_retrieved_articles]
            await _log_query(
                db, query=body.query, intent="REGULATIONS",
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
        qid = await _log_query(
            db, query=body.query, intent="REGULATIONS",
            year=query_year, section=query_section, answer=final_answer,
            retrieved_count=len(all_retrieved_articles),
            research_steps=len(research_history),
            response_time_ms=ms, cited_articles=codes,
        )
        return ChatResponse(
            answer=final_answer,
            citations=final_citations,
            retrieved_count=len(all_retrieved_articles),
            research_steps=research_history,
            query_id=qid,
            confidence=retrieval_confidence,
        )

    except Exception as e:
        logger.error("Unexpected error in chat endpoint: %s", e, exc_info=True)
        ms = int((time.monotonic() - t_start) * 1000)
        try:
            await _log_query(
                db, query=body.query, intent="UNKNOWN",
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


@router.post("/chat/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit thumbs-up / thumbs-down feedback for a previous chat response.

    The query_id is returned in every ChatResponse and links back to the
    query_logs row created when the answer was generated.
    """
    try:
        await db.execute(
            text("UPDATE query_logs SET was_helpful = :helpful WHERE id = :id"),
            {"helpful": feedback.was_helpful, "id": feedback.query_id},
        )
        await db.commit()
        return {"status": "ok", "query_id": feedback.query_id}
    except Exception as exc:
        logger.warning("Failed to save feedback: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save feedback.")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Return aggregate usage and quality statistics from query_logs."""
    try:
        result = await db.execute(text("""
            SELECT
                COUNT(*)                                                      AS total_queries,
                COUNT(*) FILTER (WHERE intent = 'REGULATIONS')               AS regulation_queries,
                COUNT(*) FILTER (WHERE intent = 'CONVERSATIONAL')            AS conversational_queries,
                COUNT(*) FILTER (WHERE error_occurred)                       AS errors,
                COALESCE(ROUND(AVG(response_time_ms))::int, 0)               AS avg_response_ms,
                COUNT(*) FILTER (WHERE was_helpful = TRUE)                   AS positive_feedback,
                COUNT(*) FILTER (WHERE was_helpful = FALSE)                  AS negative_feedback,
                MAX(created_at)                                               AS last_query_at
            FROM query_logs
        """))
        row = result.fetchone()
        if not row:
            return StatsResponse(
                total_queries=0, regulation_queries=0, conversational_queries=0,
                errors=0, avg_response_ms=0, positive_feedback=0, negative_feedback=0,
            )
        return StatsResponse(
            total_queries=row[0],
            regulation_queries=row[1],
            conversational_queries=row[2],
            errors=row[3],
            avg_response_ms=row[4],
            positive_feedback=row[5],
            negative_feedback=row[6],
            last_query_at=row[7],
        )
    except Exception as exc:
        logger.error("Failed to fetch stats: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch statistics.")


@router.get("/chat/health")
async def chat_health():
    """Health check for chat endpoint."""
    return {"status": "healthy", "service": "chat", "message": "RAG system operational"}
