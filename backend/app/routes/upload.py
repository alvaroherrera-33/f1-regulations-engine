"""PDF upload route handler."""
import asyncio
import io
import logging
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin_key
from app.config import settings
from app.database import get_db
from app.models import Document, UploadResponse
from ingestion.pipeline import ingest_document

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

ALLOWED_SECTIONS = {"Technical", "Sporting", "Financial"}
_PDF_MAGIC = b"%PDF-"  # A-02: magic bytes for PDF validation

# M-05: limit concurrent ingestion to 1 -- avoids OOM on Render free tier (512 MB RAM)
# sentence-transformers loads a 90 MB model into memory; two simultaneous uploads
# would double that and likely crash the container.
_ingestion_semaphore = asyncio.Semaphore(1)


async def _ingest_with_semaphore(file_path: str, document_id: int) -> None:
    """Run ingestion pipeline with a concurrency limit of 1."""
    async with _ingestion_semaphore:
        await ingest_document(file_path, document_id)


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    year: int = Form(...),
    section: str = Form(...),
    issue: int = Form(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_key),
):
    """
    Upload a regulation PDF file.

    Requires X-Admin-Key header. Creates a document record and saves the PDF
    to disk. Returns a job ID; ingestion runs asynchronously in the background.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate section
    if section not in ALLOWED_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Must be one of: {', '.join(sorted(ALLOWED_SECTIONS))}",
        )

    # Validate year range
    if not (2020 <= year <= 2030):
        raise HTTPException(status_code=400, detail="Year must be between 2020 and 2030")

    # A-02: Read in 64 KB chunks -- verify PDF magic bytes + enforce size limit
    # without loading the whole file into memory before checking.
    buf = io.BytesIO()
    total = 0
    first_chunk = True
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        if first_chunk:
            if not chunk.startswith(_PDF_MAGIC):
                raise HTTPException(
                    status_code=400,
                    detail="Not a valid PDF (magic bytes missing). Only PDF files are accepted.",
                )
            first_chunk = False
        total += len(chunk)
        if total > settings.max_upload_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)} MB",
            )
        buf.write(chunk)
    contents = buf.getvalue()

    # Generate unique filename (no path traversal possible -- we control all parts)
    job_id = str(uuid.uuid4())
    safe_section = section.replace(" ", "_")
    filename = f"{year}_{safe_section}_issue{issue}_{job_id}.pdf"

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Save file to disk (async -- avoids blocking the event loop on large uploads)
    file_path = os.path.join(settings.upload_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(contents)

    # Create document record
    stmt = insert(Document).values(
        name=file.filename,
        year=year,
        section=section,
        issue=issue,
        file_path=file_path,
    ).returning(Document.id)

    try:
        result = await db.execute(stmt)
        document_id = result.scalar_one()
        await db.commit()
    except Exception as e:
        logger.error("DB insert failed during upload: %s", e)
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Upload failed: could not create document record")

    # M-05: Trigger async ingestion pipeline (rate-limited via semaphore)
    asyncio.create_task(_ingest_with_semaphore(file_path, document_id))

    return UploadResponse(
        job_id=job_id,
        status="uploaded",
        message="PDF uploaded successfully. Ingestion will begin shortly.",
    )


@router.get("/upload/status/{job_id}")
async def get_upload_status(job_id: str):
    """
    Get the status of a PDF ingestion job.

    Job tracking is not yet implemented; status always returns pending.
    """
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job tracking not yet implemented",
    }
