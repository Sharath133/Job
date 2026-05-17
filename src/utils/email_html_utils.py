from __future__ import annotations

import html
import re

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def strip_markdown_bold(text: str) -> str:
    """Remove markdown bold markers, keeping inner text."""
    return _BOLD_PATTERN.sub(r"\1", text)


def markdown_bold_to_html(text: str) -> str:
    """Convert **bold** markdown to HTML with escaped plain text."""
    parts: list[str] = []
    last_index = 0
    for match in _BOLD_PATTERN.finditer(text):
        parts.append(html.escape(text[last_index : match.start()]))
        parts.append(f"<strong>{html.escape(match.group(1))}</strong>")
        last_index = match.end()
    parts.append(html.escape(text[last_index:]))
    body = "".join(parts).replace("\n", "<br>\n")
    return f"<html><body>{body}</body></html>"
