from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.ingestion.extract import Page


@dataclass
class ChunkDraft:
    index: int
    page: int
    text: str


def chunk_pages(pages: list[Page]) -> list[ChunkDraft]:
    """Split per page so every chunk keeps an exact page number for its citation."""
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size,
        chunk_overlap=s.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    drafts: list[ChunkDraft] = []
    for page in pages:
        for piece in splitter.split_text(page.text):
            drafts.append(ChunkDraft(index=len(drafts), page=page.number, text=piece.strip()))
    return [d for d in drafts if d.text]
