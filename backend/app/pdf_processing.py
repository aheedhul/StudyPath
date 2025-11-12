from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import pdfplumber
from fastapi import UploadFile
from PyPDF2 import PdfReader


@dataclass
class ChapterMetadata:
    title: str
    level: int
    page_start: int
    page_end: int

    @property
    def page_count(self) -> int:
        return max(1, self.page_end - self.page_start + 1)


def _walk_outline(reader: PdfReader, entries: List | None, level: int) -> Iterator[tuple[int, str, int]]:
    if not entries:
        return

    if callable(entries):  # Some PyPDF2 versions expose outline as a callable
        try:
            entries = entries()
        except Exception:
            return

    for entry in entries:
        if isinstance(entry, list):
            # Nested list wraps deeper outline items
            yield from _walk_outline(reader, entry, level)
            continue

        title = getattr(entry, "title", "Untitled") or "Untitled"
        try:
            page_index = reader.get_destination_page_number(entry)
        except Exception:
            page_index = 0

        yield page_index, title.strip(), level

        children = getattr(entry, "children", None)
        if children:
            yield from _walk_outline(reader, children, level + 1)


def extract_outline(file_path: Path) -> List[ChapterMetadata]:
    reader = PdfReader(str(file_path))
    try:
        outline = reader.outline
        if callable(outline):  # Older/newer PyPDF2 variations
            outline = outline()
    except Exception:
        outline = []

    flattened: List[tuple[int, str, int]] = list(_walk_outline(reader, outline, level=1))
    if not flattened:
        return []

    try:
        total_pages = len(reader.pages)
    except Exception:
        total_pages = getattr(reader, "_get_num_pages", lambda: 0)() or 0

    chapters: List[ChapterMetadata] = []
    for idx, (page_index, title, level) in enumerate(flattened):
        start_page = page_index
        if idx + 1 < len(flattened):
            next_page = flattened[idx + 1][0]
            end_page = max(start_page, next_page - 1)
        else:
            end_page = max(start_page, total_pages - 1)
        chapters.append(
            ChapterMetadata(
                title=title,
                level=level,
                page_start=start_page + 1,
                page_end=end_page + 1,
            )
        )
    return chapters


def summarize_pdf(file_path: Path) -> dict:
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)

    chapters = extract_outline(file_path)
    if not chapters:
        # fallback heuristic: split into equal chunks of 15 pages
        chunk_size = 15
        chapters = [
            ChapterMetadata(
                title=f"Section {i + 1}",
                level=1,
                page_start=i * chunk_size + 1,
                page_end=min((i + 1) * chunk_size, total_pages),
            )
            for i in range((total_pages + chunk_size - 1) // chunk_size)
        ]

    report = {
        "total_pages": total_pages,
        "chapters": [chapter.__dict__ for chapter in chapters],
    }
    return report


async def persist_upload(upload: UploadFile, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    contents = await upload.read()
    destination.write_bytes(contents)
    # Store metadata for traceability
    destination.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "filename": upload.filename,
                "content_type": upload.content_type,
                "size": len(contents),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination
