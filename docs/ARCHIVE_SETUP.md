# 🏎️ F1 Regulations RAG Engine - Archive Setup

This project uses a **pre-loaded archive** of F1 regulations rather than user uploads.

## 📁 Archive Structure

The `archives/` directory should contain regulation PDFs organized by year:

```
archives/
├── 2024/
│   ├── Technical_Regulations_2024_Issue_1.pdf
│   ├── Sporting_Regulations_2024_Issue_2.pdf
│   ├── Financial_Regulations_2024_Issue_1.pdf
│   └── Power_Unit_Regulations_2024_Issue_1.pdf
├── 2023/
│   ├── Technical_Regulations_2023_Issue_7.pdf
│   ├── Sporting_Regulations_2023_Issue_12.pdf
│   └── ...
├── 2022/
│   └── ...
└── ...
```

## 🔄 Initial Ingestion

After setting up the project, you need to ingest all documents from the archives:

### Local Development

```bash
# 1. Start Docker Compose
docker-compose up -d

# 2. Wait for services to be ready
sleep 10

# 3. Run ingestion script
docker-compose exec backend python -m scripts.ingest_archives
```

Or run directly:

```bash
cd backend
python -m scripts.ingest_archives
```

### Production (Railway)

After deploying to Railway:

```bash
# Using Railway CLI
railway run python -m scripts.ingest_archives
```

Or connect to your backend service and run the command there.

## 📝 Naming Convention

The ingestion script automatically extracts metadata from filenames:

**Pattern**: `{Section}_Regulations_{Year}_Issue_{Number}.pdf`

**Examples**:
- `Technical_Regulations_2024_Issue_1.pdf`
  - Year: 2024
  - Section: Technical
  - Issue: 1

- `Sporting_Regulations_2023_Issue_12.pdf`
  - Year: 2023
  - Section: Sporting
  - Issue: 12

**Supported Sections**:
- Technical
- Sporting
- Financial
- Power Unit (or PU)

## 🎯 What the Script Does

1. **Scans** `archives/` directory recursively
2. **Extracts** metadata from filenames and directory structure
3. **Parses** each PDF to extract articles with hierarchy
4. **Generates** embeddings for semantic search
5. **Stores** everything in the PostgreSQL database
6. **Skips** documents that are already ingested

## ⚙️ Progress Monitoring

The script outputs:
- Total documents found
- Processing status for each document
- Number of articles extracted per document
- Any errors encountered
- Final summary

Example output:
```
============================================================
🏎️  F1 Regulations Archive Ingestion
============================================================

📂 Scanning archives directory...
✅ Found 12 regulation documents

Documents to process:
  1. Technical_Regulations_2024_Issue_1.pdf
     Year: 2024, Section: Technical, Issue: 1
  ...

[1/12] Processing: Technical_Regulations_2024_Issue_1.pdf
------------------------------------------------------------
Parsing PDF...
Extracted 234 articles
Generating embeddings...
Generated 234 embeddings
Storing in database...
✅ Success: 234 articles ingested

...

============================================================
✅ Archive ingestion complete!
============================================================
```

## 🔍 Verification

After ingestion, verify the data:

```bash
# Check documents
curl http://localhost:8000/api/articles | jq

# Test chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the minimum weight?",
    "year": 2024,
    "section": "Technical"
  }'
```

## 🔄 Re-ingestion

If you need to re-ingest documents:

1. **Delete old data** (optional):
```sql
-- Connect to database
docker-compose exec db psql -U postgres -d f1_regs

-- Clear everything
TRUNCATE article_embeddings, articles, documents CASCADE;
```

2. **Run ingestion again**:
```bash
docker-compose exec backend python -m scripts.ingest_archives
```

## 📊 Database Schema

The script populates these tables:

- **documents**: PDF metadata (year, section, issue, file_path)
- **articles**: Parsed article content with hierarchy
- **article_embeddings**: Vector embeddings for semantic search

## 🚨 Troubleshooting

### Script fails with import errors
```bash
# Make sure you're in the backend directory
cd backend
python -m scripts.ingest_archives
```

### No PDFs found
- Check that `archives/` directory exists
- Verify PDFs are named correctly
- Check file permissions

### Embedding API errors
- Verify your `OPENROUTER_API_KEY` is set
- Check network connectivity
- Review OpenRouter rate limits

### Database connection errors
- Ensure PostgreSQL is running
- Verify `DATABASE_URL` is correct
- Check pgvector extension is installed

## 🎯 Adding New Documents

To add new regulations:

1. Place PDF in appropriate year folder: `archives/2024/`
2. Name following convention: `{Section}_Regulations_{Year}_Issue_{Number}.pdf`
3. Run ingestion script
4. Script will automatically detect and ingest new documents

## 📝 Notes

- **Pre-loaded data** means users don't need to upload PDFs
- **Curated experience** - you control which regulations are available
- **Faster setup** - users can immediately start querying
- **Production ready** - no file upload security concerns
- **Offline capable** - all data is in the database

This approach is **ideal for portfolio projects** - cleaner, more professional, and easier to demo! 🏎️
