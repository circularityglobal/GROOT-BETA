"""
REFINET Cloud — Document Exporter
Export documents as Markdown or PDF.
PDF creation uses PyMuPDF (fitz) — already in requirements. Fully sovereign.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("refinet.document_exporter")


def export_markdown(
    title: str,
    content: str,
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> str:
    """Export document as formatted Markdown with frontmatter."""
    lines = ["---"]
    lines.append(f"title: \"{title}\"")
    if category:
        lines.append(f"category: {category}")
    if doc_type:
        lines.append(f"type: {doc_type}")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines.append(f"exported_from: REFINET Cloud")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(content)
    return "\n".join(lines)


def export_pdf(
    title: str,
    content: str,
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
) -> bytes:
    """
    Export document as PDF using PyMuPDF (fitz).
    Creates a clean, readable PDF with title, metadata, and content.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = fitz.open()

    # Page dimensions (A4)
    width, height = 595.28, 841.89
    margin = 72  # 1 inch margins
    text_width = width - 2 * margin
    y_pos = margin

    def new_page():
        nonlocal y_pos
        page = doc.new_page(width=width, height=height)
        y_pos = margin
        return page

    page = new_page()

    # Title
    title_font_size = 18
    page.insert_text(
        (margin, y_pos + title_font_size),
        title,
        fontsize=title_font_size,
        fontname="helv",
        color=(0.2, 0.8, 0.75),  # REFINET teal
    )
    y_pos += title_font_size + 12

    # Metadata line
    meta_parts = []
    if category:
        meta_parts.append(f"Category: {category}")
    if tags:
        meta_parts.append(f"Tags: {', '.join(tags[:8])}")
    meta_parts.append("Exported from REFINET Cloud")
    meta_line = " | ".join(meta_parts)

    page.insert_text(
        (margin, y_pos + 9),
        meta_line,
        fontsize=9,
        fontname="helv",
        color=(0.5, 0.5, 0.5),
    )
    y_pos += 24

    # Separator line
    page.draw_line(
        (margin, y_pos), (width - margin, y_pos),
        color=(0.8, 0.8, 0.8), width=0.5,
    )
    y_pos += 16

    # Content — split into lines and pages
    font_size = 10
    line_height = font_size * 1.5
    max_chars_per_line = int(text_width / (font_size * 0.5))

    for paragraph in content.split("\n"):
        if not paragraph.strip():
            y_pos += line_height * 0.5
            continue

        # Word-wrap the paragraph
        words = paragraph.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            if len(test_line) > max_chars_per_line:
                # Flush current line
                if y_pos + line_height > height - margin:
                    page = new_page()
                page.insert_text(
                    (margin, y_pos + font_size),
                    current_line,
                    fontsize=font_size,
                    fontname="helv",
                )
                y_pos += line_height
                current_line = word
            else:
                current_line = test_line

        # Flush remaining
        if current_line:
            if y_pos + line_height > height - margin:
                page = new_page()
            page.insert_text(
                (margin, y_pos + font_size),
                current_line,
                fontsize=font_size,
                fontname="helv",
            )
            y_pos += line_height

        y_pos += line_height * 0.3  # paragraph spacing

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
