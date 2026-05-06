"""Chat endpoint for RAG queries."""
import logging

from fastapi import APIRouter, Depends, HTTPException
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
    try:
        from app.llm.client import LLMClient
        llm_client = LLMClient()

        # Step 1: Detect Intent (local, no LLM)
        intent = await llm_client.detect_intent(request.query)

        if intent == "CONVERSATIONAL":
            logger.info("Routing CONVERSATIONAL: %s", request.query[:80])
            answer = await llm_client.generate_conversational_response(request.query)
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
            return ChatResponse(
                answer="I couldn't find specific regulations matching your query. Could you please clarify your question or adjust the filters (year, section, etc.)?",
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

                display_steps = research_history
                if len(research_history) == 1:
                    thought = research_history[0].get("thought", "").lower()
                    if any(k in thought for k in ["greeting", "hola", "spanish", "not a specific question", "common courtesy"]):
                        display_steps = []
                        citations = []

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
            return ChatResponse(
                answer=_AI_UNAVAILABLE,
                citations=llm_client._extract_citations(all_retrieved_articles),
                retrieved_count=len(all_retrieved_articles),
                research_steps=research_history
            )

        return ChatResponse(
            answer=final_answer,
            citations=final_citations,
            retrieved_count=len(all_retrieved_articles),
            research_steps=research_history
        )

    except Exception as e:
        logger.error("Unexpected error in chat endpoint: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your query: {str(e)}"
        )


@router.get("/chat/health")
async def chat_health():
    """Health check for chat endpoint."""
    return {"status": "healthy", "service": "chat", "message": "RAG system operational"}
