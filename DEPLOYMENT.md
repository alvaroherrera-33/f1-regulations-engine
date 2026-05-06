# 🚀 Railway Deployment Guide

This guide walks you through deploying the F1 Regulations RAG Engine to Railway.

## 📋 Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Repository**: Push your code to GitHub
3. **OpenRouter API Key**: Get yours from [openrouter.ai](https://openrouter.ai)

---

## 🗄️ Step 1: Create Railway Project

### 1.1 Create New Project

1. Go to [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy PostgreSQL"**
4. Railway will create a PostgreSQL database

### 1.2 Add pgvector Extension

1. Click on your PostgreSQL service
2. Go to **"Data"** tab
3. Click **"Query"**
4. Run this command:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

5. Verify with:

```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 1.3 Initialize Database Schema

1. Still in the Query tab, copy and paste the entire contents of `/backend/database/schema.sql`
2. Click **"Run"** to execute the schema
3. Verify tables were created:

```sql
\dt
```

You should see: `documents`, `articles`, `article_embeddings`

---

## 🔧 Step 2: Deploy Backend

### 2.1 Add Backend Service

1. In your Railway project, click **"+ New"**
2. Select **"GitHub Repo"**
3. Authorize Railway to access your repositories
4. Select your `f1-regulations-engine` repository
5. Railway will detect it's a Python project

### 2.2 Configure Backend

1. Click on the backend service
2. Go to **"Settings"**
3. Set **Root Directory**: `backend`
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 2.3 Add Environment Variables

In the **"Variables"** tab, add:

```bash
# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LLM_MODEL=anthropic/claude-3.5-sonnet
EMBEDDING_MODEL=openai/text-embedding-3-small

# Database (Railway will auto-populate this)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# CORS - Add your Railway frontend URL later
ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend-url.railway.app

# Upload settings
MAX_UPLOAD_SIZE=52428800
UPLOAD_DIR=/app/data/regulations
```

### 2.4 Connect Database

1. In the backend service settings
2. Go to **"Service"** → **"Variables"**
3. Click **"+ New Variable"** → **"Add Reference"**
4. Select your PostgreSQL service
5. Choose `DATABASE_URL`

### 2.5 Deploy

1. Click **"Deploy"**
2. Watch the build logs
3. Once deployed, copy your backend URL (e.g., `https://your-backend.railway.app`)

### 2.6 Test Backend

```bash
curl https://your-backend.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "timestamp": "...",
  "database": "connected"
}
```

---

## 🎨 Step 3: Deploy Frontend

### 3.1 Add Frontend Service

1. Click **"+ New"** in your Railway project
2. Select **"GitHub Repo"** (same repository)
3. Select your repo again
4. Railway will create a second service

### 3.2 Configure Frontend

1. Click on the frontend service
2. Go to **"Settings"**
3. Set **Root Directory**: `frontend`
4. Set **Build Command**: `npm install && npm run build`
5. Set **Start Command**: `npm start`

### 3.3 Add Environment Variables

In the **"Variables"** tab:

```bash
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

Replace `your-backend.railway.app` with your actual backend URL from Step 2.5.

### 3.4 Deploy

1. Click **"Deploy"**
2. Wait for build to complete
3. Copy your frontend URL (e.g., `https://your-frontend.railway.app`)

### 3.5 Update Backend CORS

1. Go back to your backend service
2. Update `ALLOWED_ORIGINS` variable:

```bash
ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend.railway.app
```

Replace with your actual frontend URL.

3. Redeploy backend (it will auto-redeploy)

---

## ✅ Step 4: Verify Deployment

### 4.1 Test Backend Endpoints

```bash
# Health check
curl https://your-backend.railway.app/health

# API docs
open https://your-backend.railway.app/docs
```

### 4.2 Test Frontend

1. Open `https://your-frontend.railway.app`
2. Navigate to **Upload** page
3. Try uploading a PDF
4. Navigate to **Chat** page
5. Ask a question

### 4.3 Test Full Workflow

1. **Upload**: Upload a test regulation PDF
2. **Wait**: Check backend logs for ingestion progress
3. **Chat**: Go to chat page and ask questions
4. **Verify**: Check that citations appear correctly

---

## 🔍 Step 5: Monitoring & Debugging

### View Logs

**Backend logs**:
1. Click on backend service
2. Go to **"Deployments"**
3. Click on latest deployment
4. View real-time logs

**Frontend logs**:
- Same process for frontend service

### Common Issues

#### Database Connection Errors

**Problem**: `Database connection failed`

**Solution**:
1. Verify `DATABASE_URL` is set correctly
2. Check PostgreSQL service is running
3. Ensure pgvector extension is installed

---

#### CORS Errors

**Problem**: `CORS policy blocked`

**Solution**:
1. Check `ALLOWED_ORIGINS` includes your frontend URL
2. Ensure no trailing slashes in URLs
3. Redeploy backend after changes

---

#### Upload Path Errors

**Problem**: `Permission denied` when uploading

**Solution**:
Railway uses ephemeral storage. For production, you should:
1. Use Railway's volume storage, or
2. Use S3/external storage for PDFs

**Quick fix for testing**:
In `backend/app/routes/upload.py`, update `upload_dir` to use `/tmp`:

```python
UPLOAD_DIR = "/tmp/regulations"
```

---

#### Build Failures

**Problem**: Build fails with dependency errors

**Solution**:
1. Verify `requirements.txt` has all dependencies
2. Check Python version (should be 3.11+)
3. Review build logs for specific errors

---

## 💰 Cost Estimation (Railway)

**Hobby Plan** (Free tier):
- $5/month credit
- Sufficient for testing
- Limited resources

**Pro Plan** ($20/month):
- $20 credit included
- Additional usage billed
- Better for production

**Estimated costs**:
- PostgreSQL: ~$5-10/month
- Backend: ~$3-5/month
- Frontend: ~$3-5/month
- **Total**: ~$11-20/month

---

## 🎯 Production Optimizations

### For Better Performance

1. **Enable Caching**:
   - Cache embeddings for common queries
   - Use Redis for session management

2. **Add Rate Limiting**:
   - Prevent API abuse
   - Use middleware like `slowapi`

3. **External Storage**:
   - Move PDFs to S3
   - Keep database for metadata only

4. **Database Indexing**:
   - Already included in schema
   - Monitor query performance

5. **Frontend Optimization**:
   - Enable Next.js image optimization
   - Use CDN for static assets

---

## 📊 Post-Deployment Checklist

- [ ] Backend health check returns 200
- [ ] Frontend loads without errors
- [ ] Can upload a PDF successfully
- [ ] PDF ingestion completes (check logs)
- [ ] Chat returns answers with citations
- [ ] Citations display correctly
- [ ] Filters work (year, section, issue)
- [ ] API docs accessible at `/docs`
- [ ] CORS configured correctly
- [ ] Environment variables set
- [ ] Database has data
- [ ] Monitoring enabled

---

## 🆘 Support

**Railway Documentation**: [docs.railway.app](https://docs.railway.app)

**Common Railway Commands** (using Railway CLI):

```bash
# Install CLI
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs

# Run commands
railway run python manage.py migrate
```

---

## 🎉 You're Done!

Your F1 Regulations RAG Engine is now live!

**Share your deployment**:
- Frontend URL: `https://your-frontend.railway.app`
- API Docs: `https://your-backend.railway.app/docs`

**Next steps**:
- Add more regulations
- Fine-tune prompts
- Add analytics
- Share with users!

🏎️ Happy racing! 🏎️
