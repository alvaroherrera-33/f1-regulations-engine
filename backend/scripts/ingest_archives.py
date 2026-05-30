"""
Batch ingestion script for processing all PDFs in the archives folder.

This script processes all regulation PDFs from the archives directory,
extracts articles, generates embeddings, and stores them in the database.

Usage:
    python -m backend.scripts.ingest_archives

Environment:
    Requires DATABASE_URL and OPENROUTER_API_KEY to be set.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import delete, insert, select

from app.database import async_session
from app.models import Document as DocumentModel
from ingestion.pdf_parser import parse_pdf
from ingestion.pipeline import IngestionPipeline


async def find_regulation_pdfs(archives_dir: str) -> List[Tuple[str, dict]]:
    """
    Find all regulation PDFs in the archives directory.

    Expected structure:
        archives/
        ├── 2024/
        │   ├── Technical_Regulations_2024_Issue_1.pdf
        │   ├── Sporting_Regulations_2024_Issue_2.pdf
        │   └── ...
        ├── 2023/
        │   └── ...

    Returns:
        List of (file_path, metadata) tuples
    """
    pdf_files = []
    archives_path = Path(archives_dir)

    if not archives_path.exists():
        print(f"⚠️ Archives directory not found: {archives_dir}")
        return []

    # Walk through archives directory
    for pdf_file in archives_path.rglob("*.pdf"):
        # Try to extract metadata from path and filename
        year = None
        section = None
        issue = None

        # Extract year from directory structure
        parts = pdf_file.parts
        for part in parts:
            if part.isdigit() and len(part) == 4:
                year = int(part)
                break

        # Extract from filename or folder
        filename = pdf_file.stem

        # Check folder structure for 2026 (sectionB, sectionC, etc.)
        for part in pdf_file.parts:
            if "sectionB" in part.lower():
                section = "Sporting"
            elif "sectionC" in part.lower():
                section = "Technical"
            elif "sectionD" in part.lower():
                section = "Financial"
            elif "sectionE" in part.lower():
                section = "Financial" # Usually Financial or related
            elif "sectionF" in part.lower():
                section = "Power Unit"

        # Fallback to filename patterns
        if not section:
            if "Technical" in filename:
                section = "Technical"
            elif "Sporting" in filename:
                section = "Sporting"
            elif "Financial" in filename:
                section = "Financial"
            elif "Power" in filename or "PU" in filename:
                section = "Power Unit"

        # Try to extract issue number (Support "Issue" and "Iss")
        issue_indicators = ["Issue", "Iss"]
        for indicator in issue_indicators:
            if indicator in filename:
                try:
                    # Extract part after indicator
                    parts = filename.split(indicator)
                    if len(parts) > 1:
                        issue_part = parts[-1].strip()
                        # Take only the first continuous block of digits
                        digits = ""
                        for char in issue_part:
                            if char.isdigit():
                                digits += char
                            elif digits:
                                break
                        if digits:
                            issue = int(digits)
                            break
                except Exception:
                    continue

        if not issue:
            issue = 1

        # Default year from filename if not in path
        if not year:
            for part in filename.split('_'):
                if part.isdigit() and len(part) == 4:
                    year = int(part)
                    break

        if year and section:
            metadata = {
                'year': year,
                'section': section,
                'issue': issue,
                'name': pdf_file.name,
                'path': str(pdf_file.absolute())
            }
            pdf_files.append((str(pdf_file.absolute()), metadata))
        else:
            print(f"⚠️ Skipping {pdf_file.name} - couldn't extract metadata")

    return pdf_files


async def ingest_all_documents(allow_degraded: bool = True, reingest: bool = False):
    """Process all PDFs from archives directory.

    Args:
        allow_degraded: when False, documents failing the structural validation
            gate (orphans / low TOC coverage) are rejected instead of stored.
            Only meaningful with STRUCTURAL_PARSER=true.
        reingest: when True, delete an already-ingested document (cascade) and
            re-ingest it, instead of skipping. Makes re-runs idempotent.
    """

    # Get archives directory (relative to project root)
    project_root = Path(__file__).parent.parent.parent
    archives_dir = project_root / "archives"

    print("=" * 60)
    print("🏎️  F1 Regulations Archive Ingestion")
    print("=" * 60)
    print()

    # Find all PDFs
    print("📂 Scanning archives directory...")
    pdf_files = await find_regulation_pdfs(str(archives_dir))

    if not pdf_files:
        print("❌ No PDF files found in archives directory")
        return

    print(f"✅ Found {len(pdf_files)} regulation documents")
    print()

    # Display what we found
    print("Documents to process:")
    for i, (path, meta) in enumerate(pdf_files, 1):
        print(f"  {i}. {meta['name']}")
        print(f"     Year: {meta['year']}, Section: {meta['section']}, Issue: {meta['issue']}")
    print()

    # Process each document
    for i, (pdf_path, metadata) in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {metadata['name']}")
        print("-" * 60)

        try:
            async with async_session() as db:
                pipeline = IngestionPipeline(db)

                # Check if document already exists
                stmt = select(DocumentModel).where(
                    DocumentModel.year == metadata['year'],
                    DocumentModel.section == metadata['section'],
                    DocumentModel.issue == metadata['issue']
                )
                result = await db.execute(stmt)
                existing_doc = result.scalar_one_or_none()

                if existing_doc:
                    if not reingest:
                        print("⏭️  Already ingested - skipping")
                        continue
                    print("♻️  Re-ingesting (deleting existing document + cascade)")
                    await db.execute(
                        delete(DocumentModel).where(DocumentModel.id == existing_doc.id)
                    )
                    await db.commit()

                # Create document record
                stmt = insert(DocumentModel).values(
                    name=metadata['name'],
                    year=metadata['year'],
                    section=metadata['section'],
                    issue=metadata['issue'],
                    file_path=metadata['path']
                ).returning(DocumentModel.id)

                result = await db.execute(stmt)
                document_id = result.scalar_one()
                await db.commit()

                # Ingest document
                result = await pipeline.ingest_document(
                    pdf_path, document_id, allow_degraded=allow_degraded
                )

                if result['status'] == 'success':
                    print(f"✅ Success: {result['articles_count']} articles ingested")
                elif result['status'] == 'degraded':
                    print(f"⚠️  Degraded (stored): {result['message']}")
                elif result['status'] == 'rejected':
                    # Gate failed and allow_degraded=False → remove the empty doc row
                    print(f"⛔ Rejected by validation gate: {result['message']}")
                    await db.execute(
                        delete(DocumentModel).where(DocumentModel.id == document_id)
                    )
                    await db.commit()
                else:
                    print(f"❌ Error: {result['message']}")

        except Exception as e:
            print(f"❌ Error processing {metadata['name']}: {e}")
            continue

    print()
    print("=" * 60)
    print("✅ Archive ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch-ingest FIA regulation PDFs.")
    parser.add_argument(
        "--allow-degraded", action="store_true",
        help="Store documents even if the structural validation gate fails "
             "(default: hard gate rejects them).",
    )
    parser.add_argument(
        "--reingest", action="store_true",
        help="Delete and re-ingest documents that already exist (idempotent re-run).",
    )
    args = parser.parse_args()
    asyncio.run(ingest_all_documents(
        allow_degraded=args.allow_degraded, reingest=args.reingest
    ))
