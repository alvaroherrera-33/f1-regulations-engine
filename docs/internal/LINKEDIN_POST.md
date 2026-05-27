# LinkedIn Launch Post

**Target audience:** F1 engineers, data engineers, AI/ML engineers, technical recruiters at F1 teams and motorsport companies.

**Tone:** Direct, technical, no hype. Let the work speak.

---

## POST (copy-paste ready)

---

I built an AI search engine for F1 regulations.

Ask it "What is the minimum car weight in 2026?" and it answers in seconds with the exact article, section, and issue number. No hallucinations — every claim is sourced.

The technical stack:

- Hybrid retrieval combining pgvector similarity search and PostgreSQL full-text search, merged with Reciprocal Rank Fusion. Both recall and precision matter when you are navigating 16,000+ articles across four years of Technical, Sporting, and Financial regulations.

- An agentic reasoning loop that runs up to three search-and-reason cycles before committing to an answer. This handles cross-references between articles — the kind that shows up constantly in the FIA docs.

- Local embeddings via all-MiniLM-L6-v2, running on the backend. No third-party embedding API call per query.

- Full multilingual support: questions in English, Spanish, French, German, and Italian all route correctly and get answers in the same language.

It covers 2023 through 2026 regulations, stays up to date via a daily cron job that checks the FIA website for new PDFs, and runs entirely on free-tier infrastructure (Render, Supabase, Vercel).

Live demo: https://f1-regulations-engine-project.vercel.app
Source: https://github.com/alvaroherrera-33/f1-regulations-engine

Happy to discuss the retrieval architecture or the ingestion pipeline if anyone is working on something similar.

---

## HASHTAGS (add after the post)

#Formula1 #MachineLearning #RAG #NLP #Python #FastAPI #pgvector #MotorsportTech #AIEngineering #Formula1Tech

---

## NOTES FOR PUBLISHING

- Post at 08:00–09:00 local time Tuesday or Wednesday (highest LinkedIn engagement for technical content)
- Pin a comment with a direct question like "What would you want to ask about F1 regulations?" to drive engagement
- If you get comments from F1 team engineers — reply within the first 2 hours. The algorithm rewards fast responses.
- Do NOT use the LinkedIn "Add document" feature — plain text performs better for technical posts.
- No image on the post itself (text-only posts outperform image posts for technical audiences on LinkedIn)

