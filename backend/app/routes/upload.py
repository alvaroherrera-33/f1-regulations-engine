"""PDF upload route handler."""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
import os
import uuid
from datetime import datetime

import asyncio

from app.database import get_db
from app.models import UploadResponse, Document
from app.config import settings
from ingestion.pipeline import ingest_document

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    year: int = Form(...),
    section: str = Form(...),
    issue: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a regulation PDF file.
    
    Creates a document record and saves the PDF to disk.
    Returns a job ID that can be used to track ingestion progress.
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Check file size
    contents = await file.read()
    if len(contents) > settings.max_upload_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size} bytes"
        )
    
    # Generate unique filename
    job_id = str(uuid.uuid4())
    filename = f"{year}_{section}_issue{issue}_{job_id}.pdf"
    
    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    # Save file to disk
    file_path = os.path.join(settings.upload_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(contents)
    
    # Create document record
    stmt = insert(Document).values(
        name=file.filename,
        year=year,
        section=section,
        issue=issue,
        file_path=file_path
    ).returning(Document.id)
    
    try:
        result = await db.execute(stmt)
        document_id = result.scalar_one()
        await db.commit()
    except Exception as e:
        # Clean up file if database insert fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Trigger async ingestion pipeline
    asyncio.create_task(ingest_document(file_path, document_id))
    
    return UploadResponse(
        job_id=job_id,
        status="uploaded",
        message=f"PDF uploaded successfully. Ingestion will begin shortly."
    )


@router.get("/upload/status/{job_id}")
async def get_upload_status(job_id: str):
    """
    Get the status of a PDF ingestion job.
    
    TODO: Implement job tracking system
    """
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job tracking not yet implemented"
    }
