"""Normalize questions using spaCy's French language model.

Loads ``fr_core_news_sm`` for tokenization, which handles French clitics such
as ``d'``, ``l'``, ``j'`` and punctuation more accurately than a blank model.
Falls back to a regex tokenizer when the model is unavailable.
"""

from __future__ import annotations

import re
import unicodedata

_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ_'-]+")
_CLITICS = frozenset({"l", "d", "j", "n", "m", "t", "s", "c", "qu"})
_tokenizer: object | None | bool = None


def normalize(text: str) -> str:
    """Case-fold, strip accents, and turn punctuation into spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_marks.casefold().replace("’", "'").replace("`", "'")
    spaced = re.sub(r"['_-]+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", spaced)
    return " ".join(cleaned.split())


def normalized_question(text: str) -> str:
    """Return the token string used for alias and intent matching."""
    pieces: list[str] = []
    for token in _token_texts(text):
        for piece in normalize(token).split():
            if piece and piece not in _CLITICS:
                pieces.append(piece)
    return " ".join(pieces)


def find_phrases[T](text: str, phrases: list[tuple[str, T]]) -> list[T]:
    """Return longest non-overlapping phrase payloads inside ``text``."""
    if not text:
        return []
    padded = f" {text} "
    taken = [False] * len(padded)
    found: list[T] = []
    ordered = sorted(phrases, key=lambda item: (-len(item[0]), item[0]))
    for phrase, payload in ordered:
        if not phrase:
            continue
        needle = f" {phrase} "
        start = 0
        while True:
            index = padded.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            if any(taken[index:end]):
                start = index + 1
                continue
            for position in range(index, end):
                taken[position] = True
            found.append(payload)
            start = end
    return found


def _token_texts(text: str) -> list[str]:
    tokenizer = _french_tokenizer()
    if tokenizer is None:
        return _TOKEN.findall(text)
    return [
        token.text
        for token in tokenizer(text)
        if not token.is_space and not token.is_punct
    ]


def _french_tokenizer():
    """Return the fr_core_news_sm pipeline, or None when unavailable."""
    global _tokenizer
    if _tokenizer is False:
        return None
    if _tokenizer is None:
        try:
            import spacy

            _tokenizer = spacy.load("fr_core_news_sm")
        except (ImportError, OSError):
            _tokenizer = False
            return None
    return _tokenizer
