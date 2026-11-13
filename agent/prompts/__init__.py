"""Versioned prompt files: one Markdown file per node, front matter holds `version` and `node`."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).resolve().parent
UNTRUSTED_LINE = re.compile(r"untrusted|instructions inside|inject|change your task|addressed to an AI", re.I)


@lru_cache(maxsize=64)
def _read(name: str) -> tuple[dict, str]:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        return yaml.safe_load(text[3:end]) or {}, text[end + 4:].strip()
    return {}, text.strip()


def load_prompt(name: str, **values: str) -> str:
    """Prompt body with {placeholders} filled from `values` (missing placeholders are left as they are)."""
    _, body = _read(name)
    from common.config import defences_on

    if not defences_on():  # attack baseline only: drop every instruction about untrusted or injected text
        body = "\n".join(line for line in body.splitlines() if not UNTRUSTED_LINE.search(line))
    for key, value in values.items():
        body = body.replace("{" + key + "}", str(value))
    return body


def prompt_version(name: str) -> str:
    return str(_read(name)[0].get("version", "1"))
