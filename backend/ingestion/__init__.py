"""Ingestion module for PDF processing and database insertion."""
from ingestion.local_embeddings import LocalEmbeddingsGenerator, generate_embeddings
from ingestion.pdf_parser import ParsedArticle, PDFParser, parse_pdf
from ingestion.pipeline import IngestionPipeline, ingest_document

__all__ = [
    "PDFParser",
    "parse_pdf",
    "ParsedArticle",
    "LocalEmbeddingsGenerator",
    "generate_embeddings",
    "IngestionPipeline",
    "ingest_document"
]
