"""Normalize questions using spaCy lemmatization.

Loads ``fr_core_news_sm`` and returns lemmatized tokens.
Falls back to simple tokenization when the model is unavailable.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypeVar

try:
    import spacy

    _nlp = spacy.load("fr_core_news_sm")
except (ImportError, OSError, OverflowError):
    _nlp = None

T = TypeVar("T")

_CLITICS = frozenset({
    "l", "d", "j", "m", "t", "s", "n", "c", "qu", "jusqu", "lorsqu", "puisqu",
    "au", "aux", "en", "et", "ou", "est", "il", "ce", "que", "qui", "dans",
    "sur", "pour", "par", "avec", "y",
})

def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Case-fold, strip accents, and turn punctuation into spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_marks.casefold().replace("’", "'").replace("`", "'")
    spaced = re.sub(r"['_-]+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", spaced)
    return " ".join(cleaned.split())


def lemmas(text: str) -> list[str]:
    """Return lemmatized, lowercased tokens from ``text`` using spaCy."""
    if _nlp is None:
        return _fallback_lemmas(text)
    doc = _nlp(text)
    return [token.lemma_.lower() for token in doc if not token.is_space and not token.is_punct]


def _fallback_lemmas(text: str) -> list[str]:
    """Simple fallback: no accents, apostrophes split, crude singular."""
    lowered = _strip_accents(text).replace("’", "'").replace("`", "'")
    spaced = re.sub(r"['_-]+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", spaced)
    words = cleaned.split()
    return [w[:-1] if len(w) > 3 and w.endswith(("s", "x")) else w for w in words]


def normalized_question(text: str) -> str:
    """Lemmas without accents or punctuation, joined by single spaces."""
    words = []
    for lemma in lemmas(text):
        cleaned = re.sub(r"[^a-z0-9]+", " ", _strip_accents(lemma))
        for w in cleaned.split():
            if w and w not in _CLITICS:
                words.append(w)
    return " ".join(words)


def find_phrases(normalized: str, phrases: list[tuple[str, T]]) -> list[T]:
    """Return the objects whose phrase appears as whole words in the text."""
    padded = f" {normalized} "
    return [obj for phrase, obj in phrases if phrase and f" {phrase} " in padded]