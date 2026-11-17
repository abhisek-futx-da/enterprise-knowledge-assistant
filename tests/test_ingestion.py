import io

import pytest
from docx import Document as DocxDocument

from app.ingestion.chunking import chunk_pages
from app.ingestion.extract import ExtractionError, Page, extract_pages
from tests.conftest import register, upload


def test_chunks_keep_page_numbers_and_overlap():
    long_text = " ".join(f"Sentence number {i} talks about leave policy." for i in range(200))
    drafts = chunk_pages([Page(1, long_text), Page(2, "Second page text about travel policy.")])
    assert len(drafts) > 2
    assert {d.page for d in drafts} == {1, 2}
    assert [d.index for d in drafts] == list(range(len(drafts)))
    assert all(len(d.text) <= 800 for d in drafts)


def test_docx_extraction():
    doc = DocxDocument()
    doc.add_paragraph("The cafeteria opens at 8am.")
    buf = io.BytesIO()
    doc.save(buf)
    pages = extract_pages("notes.docx", buf.getvalue())
    assert "cafeteria" in pages[0].text


@pytest.mark.parametrize("name,data,msg", [
    ("virus.exe", b"MZ...", "Unsupported"),
    ("fake.pdf", b"not a pdf", "not a PDF"),
    ("empty.txt", b"   ", "No extractable text"),
    ("binary.txt", b"\xff\xfe\x00", "UTF-8"),
])
def test_extraction_errors(name, data, msg):
    with pytest.raises(ExtractionError, match=msg):
        extract_pages(name, data)


def test_upload_ingests_to_ready(client):
    user = register(client)
    doc = upload(client, user, "product_faq.txt")
    assert doc["status"] == "ready"
    assert doc["num_chunks"] >= 1
    listed = client.get("/documents", headers=user["headers"]).json()
    assert [d["id"] for d in listed] == [doc["id"]]


def test_upload_rejects_bad_type_and_size(client, monkeypatch):
    user = register(client)
    r = client.post("/documents", headers=user["headers"], files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    r = client.post("/documents", headers=user["headers"], files={"file": ("big.txt", b"x" * 10, "text/plain")})
    assert r.status_code == 413


def test_unparseable_file_marked_failed(client):
    user = register(client)
    doc = upload(client, user, "scan.pdf", b"%PDF-1.4 garbage")
    assert doc["status"] == "failed"
    assert doc["error"]


def test_delete_document_removes_it_from_search(client):
    user = register(client)
    doc = upload(client, user, "product_faq.txt")
    assert client.post("/search", headers=user["headers"], json={"query": "E-417"}).json()
    assert client.delete(f"/documents/{doc['id']}", headers=user["headers"]).status_code == 204
    assert client.post("/search", headers=user["headers"], json={"query": "E-417"}).json() == []
