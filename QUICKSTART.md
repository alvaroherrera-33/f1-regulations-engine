# 🚀 Quick Start Guide

## Local Development Setup

### 1. Prerequisites

Make sure you have installed:
- **Docker Desktop** (includes Docker Compose)
- A text editor (VS Code recommended)

### 2. Get OpenRouter API Key

1. Go to https://openrouter.ai/
2. Sign up or log in
3. Navigate to "Keys" section
4. Create a new API key
5. Copy the key (starts with `sk-or-...`)

### 3. Configure Environment

```bash
# Copy the environment template
copy .env.example .env

# Edit .env and add your API key
# Replace 'your_openrouter_api_key_here' with your actual key
```

### 4. Prepare Regulation Archives

Place your F1 regulation PDFs in the `archives/` directory:

```bash
archives/
├── 2024/
│   ├── Technical_Regulations_2024_Issue_1.pdf
│   └── Sporting_Regulations_2024_Issue_1.pdf
├── 2023/
│   └── ...
```

### 5. Start Services

```bash
# Start all services (database, backend, frontend)
docker-compose up

# Wait for services to start (first time takes ~2-3 minutes)
# You'll see logs from all three services
```

### 6. Ingest Regulations

Open a new terminal and run:

```bash
# This will process all PDFs and load them into the database
docker-compose exec backend python -m scripts.ingest_archives
```

This will:
- Scan the `archives/` directory
- Extract articles from each PDF
- Generate embeddings
- Store everything in PostgreSQL

**Note**: This may take 5-15 minutes depending on the number of PDFs.

### 7. Access the Application

Once you see "Application startup complete" in the logs:

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 6. Stop the Application

```bash
# Press Ctrl+C in the terminal where docker-compose is running
# Then run:
docker-compose down
```

## Next Steps

The foundation is ready! Now we'll build:

1. **Phase 2**: PDF upload and parsing
2. **Phase 3**: RAG retrieval system
3. **Phase 4**: Chat interface
4. **Phase 5**: Deployment to Railway

## Troubleshooting

### Port Already in Use

If you see "port already in use" errors:

```bash
# Stop conflicting services or change ports in docker-compose.yml
# Example: Change "3000:3000" to "3001:3000"
```

### Database Connection Issues

```bash
# Reset database
docker-compose down -v  # Warning: deletes all data
docker-compose up
```

### API Key Not Working

- Make sure `.env` file is in the root directory (same level as `docker-compose.yml`)
- Check that there are no quotes around the API key
- Restart docker-compose after editing `.env`

## Development Workflow

### Backend Development

```bash
# Enter backend container
docker-compose exec backend bash

# Or run locally without Docker
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
# Enter frontend container
docker-compose exec frontend sh

# Or run locally without Docker
cd frontend
npm install
npm run dev
```

### View Database

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d f1_regs

# Useful commands:
\dt              # List tables
\d articles      # Describe articles table
SELECT * FROM documents LIMIT 10;
```

## Project Structure Overview

```
f1-regulations-engine/
├── backend/           ← FastAPI Python backend
├── frontend/          ← Next.js React frontend
├── data/             ← PDF storage (gitignored)
├── docker-compose.yml ← Local dev orchestration
└── .env              ← Your secrets (gitignored)
```

Ready to develop! 🏎️
