#!/usr/bin/env python3
"""Generate a simple PDF from the project Markdown documentation.

The script intentionally uses only the Python standard library so report
generation does not add a runtime dependency to the prototype application.
"""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = (
    PROJECT_ROOT / "docs" / "api_reference.md",
    PROJECT_ROOT / "docs" / "project_report.md",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "project_report.pdf"

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 54
BODY_SIZE = 9
BODY_LEADING = 12

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TABLE_DIVIDER_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _plain_text(value: str) -> str:
    """Remove the small Markdown subset used by the project documentation."""
    value = _LINK_RE.sub(r"\1 <\2>", value)
    return value.replace("**", "").replace("__", "").replace("`", "")


def _escape_pdf_text(value: str) -> str:
    """Escape a PDF literal string and keep it compatible with core fonts."""
    compatible = value.encode("latin-1", "replace").decode("latin-1")
    compatible = "".join(char for char in compatible if ord(char) >= 32)
    return compatible.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _style_for_heading(level: int) -> tuple[str, int, int]:
    if level == 1:
        return ("F2", 16, 22)
    if level == 2:
        return ("F2", 13, 18)
    return ("F2", 10, 14)


def _wrap(value: str, width: int, code: bool = False) -> list[str]:
    if not value:
        return [""]

    if code:
        return [value[index:index + width] for index in range(0, len(value), width)]

    return textwrap.wrap(
        value,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [value]


def _markdown_lines(source: Path) -> list[tuple[str, str, int, int]]:
    """Turn project Markdown into simple PDF text instructions.

    Each tuple is text, font, font size, and vertical leading. This is a
    deliberately small renderer, but it preserves headings, lists, code, and
    readable table rows from the maintained documentation.
    """
    instructions: list[tuple[str, str, int, int]] = []
    in_code_block = False

    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            for wrapped in _wrap(line, 92, code=True):
                instructions.append((wrapped, "F1", 8, 10))
            continue

        if not line.strip() or line.strip() == "---":
            instructions.append(("", "F1", BODY_SIZE, 7))
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            font, size, leading = _style_for_heading(len(heading.group(1)))
            for wrapped in _wrap(_plain_text(heading.group(2)), 70):
                instructions.append((wrapped, font, size, leading))
            continue

        if _TABLE_DIVIDER_RE.match(line):
            continue

        cleaned = _plain_text(line.strip())
        if cleaned.startswith("|") and cleaned.endswith("|"):
            cells = [cell.strip() for cell in cleaned.strip("|").split("|")]
            cleaned = " | ".join(cells)

        is_list = cleaned.startswith("- ") or re.match(r"^\d+\.\s+", cleaned)
        width = 88 if is_list else 96
        for wrapped in _wrap(cleaned, width):
            instructions.append((wrapped, "F1", BODY_SIZE, BODY_LEADING))

    return instructions


def _paginate(instructions: list[tuple[str, str, int, int]]) -> list[list[tuple[str, str, int, int, int]]]:
    """Place text instructions on US Letter pages with safe margins."""
    pages: list[list[tuple[str, str, int, int, int]]] = [[]]
    y = PAGE_HEIGHT - MARGIN

    for text, font, size, leading in instructions:
        if y - leading < MARGIN:
            pages.append([])
            y = PAGE_HEIGHT - MARGIN

        pages[-1].append((text, font, size, leading, y))
        y -= leading

    return pages


def _page_stream(lines: list[tuple[str, str, int, int, int]]) -> bytes:
    commands: list[str] = []
    for text, font, size, _leading, y in lines:
        if not text:
            continue
        commands.extend(
            (
                "BT",
                f"/{font} {size} Tf",
                f"1 0 0 1 {MARGIN} {y} Tm",
                f"({_escape_pdf_text(text)}) Tj",
                "ET",
            )
        )
    return "\n".join(commands).encode("latin-1")


def _build_pdf(pages: list[list[tuple[str, str, int, int, int]]]) -> bytes:
    """Build a minimal PDF 1.4 document using built-in Helvetica fonts."""
    page_numbers = [3 + index * 2 for index in range(len(pages))]
    page_references = " ".join(f"{number} 0 R" for number in page_numbers)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{page_references}] /Count {len(pages)} >>".encode("ascii"),
    ]

    resources = (
        "/Resources << /Font << "
        "/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
        "/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
        ">> >>"
    )
    for index, page in enumerate(pages):
        page_number = page_numbers[index]
        content_number = page_number + 1
        page_object = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"{resources} /Contents {content_number} 0 R >>"
        ).encode("ascii")
        stream = _page_stream(page)
        content_object = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        objects.extend((page_object, content_object))

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode("ascii"))
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(document)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile project Markdown documentation into a PDF report."
    )
    parser.add_argument(
        "--input",
        "-i",
        action="append",
        dest="inputs",
        metavar="PATH",
        help="Markdown source to include. Repeat to select multiple files.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        help="Output PDF path (default: docs/project_report.pdf).",
    )
    args = parser.parse_args()

    sources = [_resolve_path(value) for value in args.inputs] if args.inputs else list(DEFAULT_INPUTS)
    for source in sources:
        if not source.is_file():
            parser.error(f"Markdown source does not exist: {source}")

    output = _resolve_path(args.output) if args.output else DEFAULT_OUTPUT
    instructions = [("Behavior Scoring - Project Documentation", "F2", 18, 26)]
    instructions.append(("", "F1", BODY_SIZE, 7))
    for source in sources:
        relative_source = source.relative_to(PROJECT_ROOT) if source.is_relative_to(PROJECT_ROOT) else source
        instructions.append((f"Source: {relative_source.as_posix()}", "F2", 10, 15))
        instructions.extend(_markdown_lines(source))
        instructions.append(("", "F1", BODY_SIZE, 12))

    pages = _paginate(instructions)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_build_pdf(pages))
    print(f"Wrote {output} ({len(pages)} page(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
