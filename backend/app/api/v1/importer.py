"""
导入 API：上传 TXT/DOCX 文件并解析章节结构。

端点
----
POST /importer/parse
    接收上传文件，返回解析出的章节列表 JSON。
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/importer", tags=["importer"])


# ── Response schema ────────────────────────────────────────────────────
class ParsedChapter(BaseModel):
    index: int
    marker: str           # e.g. "第1章", "Chapter 2", "后记"
    marker_type: str      # "chapter" | "volume" | "chapter_en" | "postscript"
    title: str            # text after the marker on same line
    content: str          # body until next marker
    start_line: int
    end_line: int


class ParseResult(BaseModel):
    filename: str
    total_lines: int
    chapters: list[ParsedChapter]


# ── Chapter marker regex patterns ──────────────────────────────────────
# Ordered: more specific first
CHAPTER_PATTERNS = [
    # 第X卷（卷）
    (re.compile(r"^\s*(第[零一二三四五六七八九十百千\d]+卷)\s*(.*)"), "volume"),
    # 第X章
    (re.compile(r"^\s*(第[零一二三四五六七八九十百千\d]+章)\s*(.*)"), "chapter"),
    # Chapter X
    (re.compile(r"^\s*(Chapter\s+\d+)\s*(.*)", re.IGNORECASE), "chapter_en"),
    # 后记 / 尾声 / 完本感言
    (re.compile(r"^\s*(后记|尾声|完本感言|番外)\s*(.*)"), "postscript"),
]


def _read_txt(content: bytes) -> str:
    """Try UTF-8, fall back to gbk for Chinese txt files."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("gbk", errors="replace")


def _read_docx(content: bytes) -> str:
    """Extract plain text from .docx bytes via python-docx."""
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="python-docx not installed. Run: pip install python-docx",
        )
    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs)


def _parse_chapters(text: str) -> list[ParsedChapter]:
    """Split text into chapter blocks by marker patterns."""
    lines = text.split("\n")
    markers: list[tuple[int, str, str, str]] = []  # (line_no, marker, title, type)

    for i, line in enumerate(lines):
        for pattern, mtype in CHAPTER_PATTERNS:
            m = pattern.match(line)
            if m:
                markers.append((i, m.group(1), m.group(2).strip(), mtype))
                break

    if not markers:
        # No chapters found — return whole file as one block
        return [
            ParsedChapter(
                index=0,
                marker="全文",
                marker_type="chapter",
                title="",
                content=text,
                start_line=1,
                end_line=len(lines),
            )
        ]

    chapters: list[ParsedChapter] = []
    for idx, (start, marker, title, ct) in enumerate(markers):
        end = markers[idx + 1][0] if idx + 1 < len(markers) else len(lines)
        body_lines = lines[start + 1 : end]
        content = "\n".join(body_lines).strip()
        chapters.append(
            ParsedChapter(
                index=idx,
                marker=marker,
                marker_type=ct,
                title=title.strip(),
                content=content,
                start_line=start + 1,
                end_line=end,
            )
        )

    return chapters


# ── Endpoint ───────────────────────────────────────────────────────────
@router.post("/parse", response_model=ParseResult)
async def parse_file(file: Annotated[UploadFile, File(...)]):
    """上传 .txt 或 .docx, 返回章节解析结果。"""
    filename = file.filename or "unknown"
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    ext = Path(filename).suffix.lower()
    if ext not in (".txt", ".docx"):
        raise HTTPException(
            status_code=400, detail="Only .txt and .docx files are supported"
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    if ext == ".txt":
        text = _read_txt(content)
    elif ext == ".docx":
        text = _read_docx(content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

    chapters = _parse_chapters(text)
    total_lines = len(text.split("\n"))

    return ParseResult(
        filename=filename,
        total_lines=total_lines,
        chapters=chapters,
    )