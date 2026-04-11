from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def slug_to_title(slug: str) -> str:
    cleaned = re.sub(r"[-_]+", " ", slug).strip()
    return cleaned.title() if cleaned else slug


def deduplicate_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(value)
    return result
