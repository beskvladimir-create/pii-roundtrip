"""Нарезка длинных документов для моделей с ограниченным окном."""

from __future__ import annotations


def chunks(text: str, size: int = 1200, overlap: int = 200) -> list[tuple[int, str]]:
    """Окна до size символов с перекрытием, границы по переводу строки или пробелу."""
    if len(text) <= size:
        return [(0, text)]
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = max(text.rfind("\n", start + size // 2, end), text.rfind(" ", start + size // 2, end))
            if cut > start:
                end = cut
        out.append((start, text[start:end]))
        if end >= len(text):
            break
        nxt = end - overlap
        sp = text.find(" ", nxt, end)
        start = sp + 1 if sp != -1 else nxt
    return out
