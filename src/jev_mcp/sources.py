"""Turn file paths / globs / inline texts into (id, text) items small enough for Jev."""

from __future__ import annotations

import glob
import os
from collections.abc import Iterator
from pathlib import Path

BINARY_SNIFF_BYTES = 8192


def expand_paths(sources: list[str]) -> list[str]:
    """Resolve paths, globs and directories into a sorted, de-duplicated file list."""
    found: set[str] = set()
    for src in sources:
        if os.path.isdir(src):
            src = os.path.join(src, "**", "*")
        matches = glob.glob(src, recursive=True) if glob.has_magic(src) else [src]
        # Forward slashes: valid on Windows too, and no JSON escaping ("a\b" costs 2 chars per separator).
        found.update(Path(os.path.normpath(m)).as_posix() for m in matches if os.path.isfile(m))
    return sorted(found)


def is_binary(path: str) -> bool:
    with open(path, "rb") as f:
        return b"\0" in f.read(BINARY_SNIFF_BYTES)


def chunk(text: str, size: int) -> list[str]:
    """Split text into pieces of at most `size` chars, preferring newline boundaries."""
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind("\n", start, end)
            if cut > start:
                end = cut + 1
        parts.append(text[start:end])
        start = end
    return parts


def iter_items(
    paths: list[str] | None,
    texts: dict[str, str] | None,
    chunk_chars: int,
) -> Iterator[tuple[str, str]]:
    """Yield (id, text). Chunked files get ids like `path#0`, `path#1`."""
    for key, text in (texts or {}).items():
        yield from _label(key, chunk(text, chunk_chars))
    for path in expand_paths(paths or []):
        if is_binary(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if text.strip():
            yield from _label(path, chunk(text, chunk_chars))


def _label(key: str, parts: list[str]) -> Iterator[tuple[str, str]]:
    if len(parts) == 1:
        yield key, parts[0]
    else:
        for i, part in enumerate(parts):
            yield f"{key}#{i}", part
