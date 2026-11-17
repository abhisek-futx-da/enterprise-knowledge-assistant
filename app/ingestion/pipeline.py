import logging

from app.cache import bump_corpus_version
from app.db import SessionLocal
from app.ingestion.chunking import chunk_pages
from app.ingestion.embeddings import embed_documents
from app.ingestion.extract import ExtractionError, extract_pages
from app.models import Chunk, Document

log = logging.getLogger(__name__)


def ingest_document(document_id: str, data: bytes) -> None:
    """Extract -> chunk -> embed (batched) -> store. Runs after the upload response is sent."""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            pages = extract_pages(doc.filename, data)
            drafts = chunk_pages(pages)
            vectors = embed_documents([d.text for d in drafts])
            db.add_all(
                Chunk(
                    document_id=doc.id, owner_id=doc.owner_id, chunk_index=d.index,
                    page=d.page, text=d.text, embedding=v,
                )
                for d, v in zip(drafts, vectors, strict=True)
            )
            doc.num_pages, doc.num_chunks, doc.status = len(pages), len(drafts), "ready"
        except ExtractionError as exc:
            doc.status, doc.error = "failed", str(exc)
        except Exception:
            log.exception("Ingestion failed for %s", document_id)
            doc.status, doc.error = "failed", "Internal error during ingestion"
        db.commit()
        bump_corpus_version(doc.owner_id)
    finally:
        db.close()
