# Deployment Guide — Render + Supabase + Vercel

This guide covers the production deployment stack used by this project.

## Architecture

| Component | Service | Notes |
|-----------|---------|-------|
| Backend API | [Render](https://render.com) (free tier) | FastAPI + uvicorn |
| Database | [Supabase](https://supabase.com) (free tier) | PostgreSQL + pgvector |
| Frontend | [Vercel](https://vercel.com) (hobby tier) | Next.js 14 |

---

## 1. Database — Supabase

**1.1 Create a project** at [supabase.com](https://supabase.com) and note your project ID.

**1.2 Enable pgvector**

In the Supabase SQL editor, run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**1.3 Run the schema**

Copy the contents of `backend/database/schema.sql` into the SQL editor and execute it.

**1.4 Get the connection string**

Use the **Session Pooler** connection string from Project Settings → Database:

```
postgresql+asyncpg://postgres.PROJECT_ID:PASSWORD@aws-1-REGION.pooler.supabase.com:5432/postgres?ssl=require
```

> **Important:** Use the Session Pooler, not the direct connection. Render's free tier is IPv4-only; the direct connection URL is IPv6.

---

## 2. Backend — Render

**2.1 Connect your GitHub repository** in the Render dashboard.

**2.2 Create a new Web Service** pointing to this repo. Render will detect `render.yaml` and pre-populate the settings.

**2.3 Set environment variables** in the Render dashboard (these are marked `sync: false` in `render.yaml` and must be set manually):

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | Session Pooler URL from step 1.4 |
| `OPENROUTER_API_KEY` | Your OpenRouter key (used to generate chat answers) |
| `ALLOWED_ORIGINS` | Your Vercel frontend URL (e.g. `https://your-app.vercel.app`) |
| `ADMIN_API_KEY` | Random secret (protects upload/admin endpoints) |

**2.4 Deploy** — Render will build and start the service. The build only installs the
Python dependencies (a couple of minutes): embeddings use ONNX Runtime with the model
vendored in `backend/models/`, so there is no PyTorch install or model download at
runtime — which keeps the service within the 512MB free-tier limit.

**2.5 Verify**

```bash
curl https://your-backend.onrender.com/health
```

---

## 3. Frontend — Vercel

**3.1 Import the repository** at [vercel.com/new](https://vercel.com/new).

**3.2 Set the root directory** to `frontend`.

**3.3 Add environment variable**

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | Your Render backend URL |

**3.4 Deploy** — Vercel will build and publish the Next.js app automatically.

---

## 4. Keep-Alive Cron (GitHub Actions)

Render's free tier sleeps after 15 minutes of inactivity. A GitHub Actions workflow (`.github/workflows/keep-alive.yml`) pings the `/warmup` endpoint every 14 minutes to prevent cold starts.

No configuration is needed — the workflow runs automatically once the repo is pushed to GitHub.

---

## 5. Ingesting Regulation PDFs

After deployment, ingest data 