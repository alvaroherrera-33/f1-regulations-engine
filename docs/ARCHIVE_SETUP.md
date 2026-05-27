# Archive Setup

The `archives/` directory holds the FIA regulation PDFs that get ingested into the database. The directory is excluded from version control (`.gitignore`) — you must obtain and organize the PDFs yourself.

## Directory Structure

```
archives/
├── 2026/
│   ├── Technical_Regulations_2026_Issue_1.pdf
│   ├── Sporting_Regulations_2026_Issue_4.pdf
│   └── Financial_Regulations_2026_Issue_1.pdf
├── 2025/
│   ├── Technical_Regulations_2025_Issue_3.pdf
│   └── ...
├── 2024/
│   └── ...
└── 2023/
    └── ...
```

## File Naming Convention

The ingestion script (`scripts/ingest_archives.py`) parses metadata from the file path and name. Use this pattern:

```
archives/{YEAR}/{Section}_Regulations_{YEAR}_Issue_{N}.pdf
```

Where `Section` is one of: `Technical`, `Sporting`, `Financial`, `Power_Unit`.

Examples:
- `archives/2026/Technical_Regulations_2026_Issue_1.pdf`
- `archives/2025/Sporting_Regulations_2025_Issue_12.pdf`
- `archives/2024/Financial_Regulations_2024_Issue_1.pdf`

## Obtaining the PDFs

Official FIA regulation documents are available at [fia.com](https://www.fia.com/regulations/category/110).

## Running Ingestion

With PostgreSQL running (locally via Docker Compose, or pointed at a remote database):

```bash
cd backend
source venv/bin/activate
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/f1_regs \
  python -m scripts.ingest_archives
```

The script skips PDFs that have already been indexed (based on filename + year + section + issue), so it is safe to re-run after adding new files.

## Checking Ingestion Status

```bash
curl http://localhost:8000/status
# {"documents_count": 98, "articles_count": 16284, "embeddings_count": 16284}
```

## Automated Sync (Production)

In production, a daily cron job (`fia-sync-daily` in `render.yaml`) checks the FIA website for new regulation PDFs and ingests them automatically. See `backend/scripts/fia_scraper.py` for implementation details.
