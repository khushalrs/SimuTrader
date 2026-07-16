from __future__ import annotations


def sanitize_ascii_printable(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in str(value) if 32 <= ord(ch) <= 126).strip()
    if not cleaned:
        return None
    return cleaned[:max_len]
