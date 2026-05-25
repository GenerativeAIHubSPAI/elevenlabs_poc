
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