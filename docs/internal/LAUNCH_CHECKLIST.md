# Launch Checklist — F1 Regulations Engine

## Before Launch Day

- [ ] **Add the screenshot to the repo**
      1. Open https://f1-regulations-engine-project.vercel.app/chat
      2. Type a real question (e.g. "What is the minimum car weight in 2026?")
      3. Wait for the full answer with citations
      4. Take a full-page screenshot (1280px wide minimum)
      5. Save as `docs/screenshot.png`
      6. Commit: `git add docs/screenshot.png && git commit -m "docs: add chat screenshot"`
      7. Push to main — Vercel will redeploy, README will show the image on GitHub

- [ ] **Verify live demo is warm**
      Open https://f1-regulations-engine-project.vercel.app/chat and run a test query.
      If the backend is cold (first response takes 30–45 s), ping it once and wait.

- [ ] **Check GitHub repo looks correct**
      - Description visible: "AI-powered search across FIA Formula 1 regulations..."
      - 12 topics visible: rag, formula1, pgvector, fastapi, etc.
      - README renders: screenshot, badges, architecture diagram, curl example
      - CI badge shows green

- [ ] **Update LinkedIn profile**
      Add the project to Featured or Projects section before posting.
      URL: https://f1-regulations-engine-project.vercel.app

---

## Launch Day (choose Tuesday or Wednesday, 08:00–09:30 local time)

**Step 1 — LinkedIn post**

Copy the post from `docs/internal/LINKEDIN_POST.md` and publish it.
Immediately pin a first comment:

> If you want to test it: ask about a specific rule, a year comparison, or something like "What changed in the 2026 Technical Regulations?" — curious what edge cases people find.

**Step 2 — Monitor for 2 hours**

Respond to every comment within the first 2 hours — LinkedIn's algorithm uses early engagement velocity to decide reach.

**Step 3 — Share to relevant LinkedIn groups (optional, same day)**
- Formula 1 Professionals
- Motorsport Data Analytics
- AI/ML Engineers

Just paste the post link — do not repost the full text in groups.

---

## Post-Launch (days 2–7)

- [ ] **Reply to any GitHub issues or stars** — thank early stargazers
- [ ] **Post a follow-up technical thread on LinkedIn** (day 3–4)
      Topic: "How the hybrid retrieval + RRF works, and why it matters for regulation search"
      This positions you as an expert, not just someone who shipped a demo.
- [ ] **Add the project to your CV / portfolio** with metrics:
      - 16,000+ articles indexed
      - 4 years of regulations (2023–2026)
      - <3 s average response time
      - Multilingual (5 languages)
      - Live at [URL]

---

## If F1 Teams Engage

Priority targets: McLaren, Mercedes, Ferrari, Red Bull, Alpine — all have active data/software engineering departments.

If a team engineer comments or connects:
1. Reply publicly to their comment (shows others)
2. Send a direct connection request with a short note: "Thanks for the comment on the F1 regs engine — happy to discuss the retrieval architecture if you're exploring similar tooling."

Do NOT lead with "I'm looking for a job." Lead with the technical work.

---

## Key Numbers to Reference

| Metric | Value |
|--------|-------|
| Articles indexed | 16,000+ |
| Years covered | 2023, 2024, 2025, 2026 |
| Regulation types | Technical, Sporting, Financial |
| Embedding model | all-MiniLM-L6-v2 (384 dims, local) |
| Retrieval method | Hybrid vector + FTS + RRF (k=60) |
| Agentic loop steps | Up to 3 per query |
| Languages supported | EN, ES, FR, DE, IT |
| Infrastructure cost | $0/month (free tiers) |
| CI | ruff + pytest (62 tests) + tsc |
