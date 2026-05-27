"""PDF text extraction service.

This module extracts readable text from uploaded PDF files using PyMuPDF. It
processes documents page by page, skips empty or very short pages, and returns
page-numbered text blocks that can be passed to the knowledge-base ingestion
pipeline.

This parser handles PDFs with an embedded text layer. Scanned or image-only PDFs
require OCR, which is intentionally not handled here.
"""


import fitz  # PyMuPDF


def extract_pdf_pages(file_bytes: bytes, min_words_per_page: int = 10) -> list[dict]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    pages = []

    for page_index, page in enumerate(doc):
        text = page.get_text("text").strip()

        if not text:
            continue

        if len(text.split()) < min_words_per_page:
            continue

        pages.append(
            {
                "page": page_index + 1,
                "text": text,
            }
        )

    return pages