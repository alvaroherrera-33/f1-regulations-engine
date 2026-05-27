# F1 Regulations Engine - Project Plan

> Last updated: 2026-05-20
> Status: COMPLETE

## Production URLs

- **Frontend:** https://f1-regulations-engine-project.vercel.app
- **Backend API:** https://f1-regulations-engine.onrender.com
- **API Docs:** https://f1-regulations-engine.onrender.com/docs

## Completed

### Phase 1 - Core Stabilization
- [x] Local intent detection (zero LLM calls)
- [x] Unified prepare_search (1 LLM call instead of 2)
- [x] Agentic reasoning loop (up to 3 steps)
- [x] Hybrid retrieval with RRF (vector + FTS)
- [x] Parent article enrichment
- [x] Query logging and feedback system

### Phase 2 - Quality & Evaluation
- [x] Evaluation framework with test set
- [x] Citation fallback patterns
- [x] Citation cap at 8 with pruning
- [x] Embedding cache for queries
- [x] Multiple eval rounds (v1-v4)

### Phase 3 - Frontend Redesign
- [x] Minimal clean style (Vercel/Linear inspired)
- [x] Dark theme (#0c0c0c base, #eb0000 accent)
- [x] Simplified navbar (Chat, Compare, About)
- [x] Redesigned landing page
- [x] Chat with inline filters (no sidebar)
- [x] Compare page for cross-year article diff
- [x] About page with pipeline and stack
- [x] Stats page with live metrics
- [x] Responsive design (mobile breakpoints)
- [x] Comprehensive .prose CSS for markdown
- [x] Hover states and transitions via globals.css

### Phase 4 - Deployment
- [x] Backend on Render (free tier)
- [x] Frontend on Vercel
- [x] Database on Supabase (Session Pooler)
- [x] 98 PDFs ingested (16,000+ articles indexed across 3 seasons)
- [x] README with badges and demo link
