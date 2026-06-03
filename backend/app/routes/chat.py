"""Chat endpoint for RAG queries."""
import asyncio
import logging
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.llm.client import OpenRouterError, generate_answer_with_citations
from app.models import ChatRequest, ChatResponse, FeedbackRequest, StatsResponse
from app.rate_limit import get_client_ip, make_feedback_token, verify_feedback_token  # A-01 / A-03
from app.retrieval.retriever import HybridRetriever, retrieve_articles

limiter = Limiter(key_func=get_client_ip)  # A-01: real IP from proxy

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_AI_UNAVAILABLE = (
    "The AI service is temporarily unavailable. "
    "Please try again in a few moments."
)

# Hard timeout per agentic step (seconds). Prevents runaway requests on Render free tier.
_STEP_TIMEOUT_S = 22.0


def _token(qid: Optional[int]) -> Optional[str]:
    """Generate feedback HMAC token for a query_id; returns None if qid is None."""
    return make_feedback_token(qid) if qid is not None else None


# B-02: X-Admin-Key header scheme (optional — used for debug mode only)
_admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def _is_debug_request(debug: bool, admin_key: str | None) -> bool:
    """Return True only when debug=1 AND a valid admin key is supplied.

    B-02: research_steps contain internal LLM reasoning; exposing them in
    production leaks implementation details and can aid prompt-injection tuning.
    """
    configured_key = getattr(__import__("app.config", fromlist=["settings"]).settings, "admin_api_key", "")
    if not debug or not configured_key:
        return False
    if not admin_key:
        return False
    return secrets.compare_digest(admin_key, configured_key)


def _citations_or_fallback(citations, all_retrieved_articles):
    """
    If the LLM returned 0 parsed citations, fall back to the top-3 retrieved articles
    as proper Citation objects (not raw Article objects which fail Pydantic validation).
    """
    if citations:
        return citations
    # Build Citation objects from the retrieved articles rather than returning
    # raw Article objects — passing Articles into ChatResponse.citations raises a
    # Pydantic ValidationError and causes HTTP 500.
    from app.llm.client import LLMClient
    return [LLMClient._make_citation(a) for a in all_retrieved_articles[:3]]


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
@limiter.limit("5/minute;50/day")  # A-01: tighter limit with daily cap
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    debug: bool = Query(default=False, description="Include research_steps (requires valid X-Admin-Key)"),
    admin_key: str | None = Depends(_admin_key_header),
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
                feedback_token=_token(qid),
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

        query_year = body.year or prepared.get("year") or 2026  # default to latest season
        query_section = body.section or prepared.get("section")
        expanded_query = prepared.get("search_query", body.query)

        # Step 3: Initial retrieval -- use HybridRetriever directly to capture confidence
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
                feedback_token=_token(qid),
            )

        # Agentic Research Loop (max 2 steps — step 3 rarely helps, adds ~15s)
        all_retrieved_articles = []
        research_history = []
        max_steps = 2
        current_step_query = expanded_query

        for step in range(max_steps):
            logger.debug("Research step %d, query: %s", step + 1, current_step_query[:80])

            new_articles = await retrieve_articles(
                db=db,
                query=current_step_query,
                year=query_year,
                section=query_section,
                issue=body.issue,
                top_k=6
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
                answer = (result.get("answer") or "").strip()
                if not answer:
                    # LLM chose ANSWER but returned no text — don't 500 on a
                    # None answer; fall through to the synthesis fallback below.
                    break
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
                    research_steps=display_steps if _is_debug_request(debug, admin_key) else [],
                    query_id=qid,
                    confidence=retrieval_confidence,
                    feedback_token=_token(qid),
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
        except Exception as gen_exc:
            # Any failure here (OpenRouter down, malformed LLM JSON, etc.) must
            # degrade gracefully to the retrieved citations — never a 500.
            logger.warning("Final answer generation failed (graceful): %s", gen_exc)
            ms = int((time.monotonic() - t_start) * 1000)
            codes = [a.article_code for a in all_retrieved_articles]
            try:
                fallback_cits = llm_client._extract_citations(all_retrieved_articles, None)
            except Exception:
                fallback_cits = []
            qid = await _log_query(
                db, query=body.query, intent="REGULATIONS",
                year=query_year, section=query_section, answer=_AI_UNAVAILABLE,
                retrieved_count=len(all_retrieved_articles),
                research_steps=len(research_history),
                response_time_ms=ms, cited_articles=codes, error_occurred=True,
            )
            return ChatResponse(
                answer=_AI_UNAVAILABLE,
                citations=fallback_cits,
                retrieved_count=len(all_retrieved_articles),
                research_steps=[],
                query_id=qid,
                feedback_token=_token(qid),
            )

        if not (final_answer or "").strip():
            final_answer = (
                "I couldn't compose a definitive answer from the retrieved "
                "articles. Please try rephrasing your question."
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
            research_steps=research_history if _is_debug_request(debug, admin_key) else [],
            query_id=qid,
            confidence=retrieval_confidence,
            feedback_token=_token(qid),
        )

    except Exception as e:
        logger.error("Unexpected error in chat endpoint: %s", e, exc_info=True)
        ms = int((time.monotonic() - t_start) * 1000)
        try:
            await _log_query(
                db, query=body.query, intent="UNKNOWN",
                year=None, section=None, answer="UNEXPECTED_ERROR",
                retrieved_count=0, research_steps=0,
                response_time_ms=ms, cited_articles=[], error_occurred=True,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your query. Please try again.",
        )


@router.post("/chat/feedback")
@limiter.limit("30/hour")  # A-03: prevent feedback spam
async def submit_feedback(
    request: Request,
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit thumbs-up / thumbs-down feedback for a previous chat response.

    The query_id and feedback_token are returned in every ChatResponse.
    When a token is provided it is validated via HMAC to prevent arbitrary
    feedback manipulation.  Requests without a token are still accepted for
    backward compatibility but will not pass HMAC validation.
    """
    # A-03: validate HMAC token when present
    if feedback.feedback_token is not None:
        if not verify_feedback_token(feedback.query_id, feedback.feedback_token):
            raise HTTPException(status_code=403, detail="Invalid or expired feedback token.")

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
