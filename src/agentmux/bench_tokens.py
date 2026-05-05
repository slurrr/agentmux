from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from transformers import AutoTokenizer


@dataclass(frozen=True)
class TokenCountResult:
    tokens: int
    tokenizer_path: str
    loaded: bool
    fallback_used: bool
    fallback_reason: str | None = None


@lru_cache(maxsize=8)
def _load_tokenizer(model_path: str):
    path = Path(model_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(model_path)
    return AutoTokenizer.from_pretrained(
        str(path),
        local_files_only=True,
    )


def count_text_tokens(text: str, model_path: str) -> TokenCountResult:
    if not text:
        return TokenCountResult(
            tokens=0,
            tokenizer_path=model_path,
            loaded=False,
            fallback_used=False,
            fallback_reason=None,
        )
    try:
        tokenizer = _load_tokenizer(model_path)
        return TokenCountResult(
            tokens=len(tokenizer.encode(text, add_special_tokens=False)),
            tokenizer_path=model_path,
            loaded=True,
            fallback_used=False,
            fallback_reason=None,
        )
    except Exception as exc:  # noqa: BLE001
        return TokenCountResult(
            tokens=len(text.split()),
            tokenizer_path=model_path,
            loaded=False,
            fallback_used=True,
            fallback_reason=f"{exc.__class__.__name__}: {exc}",
        )
