"""Resolve classes and individuals mentioned in a French question.

Class forms come from the CamelCase local names in ENERGIE.rdf. A question
token matches a piece when its lemma or its singular surface does. Individuals
are local names supplied by the caller, normally read from Fuseki. Nothing in
this module adds a synonym for an ontology name.
"""

from __future__ import annotations

import re
from functools import cache, lru_cache

from web_sem.nlp.catalog import all_class_names, is_ancestor
from web_sem.nlp.normalize import FrenchDoc, Token, analyze, normalize
from web_sem.ontology import (
    LOCAL_NAME_RE,
    MAX_LOCAL_NAME,
    ONTOLOGY_NS,
    display_name,
    list_properties,
    reserved_names,
)

_FUNCTION = frozenset(
    {
        "le",
        "la",
        "les",
        "l",
        "un",
        "une",
        "de",
        "du",
        "des",
        "d",
        "et",
        "ou",
        "que",
        "qui",
        "se",
        "ne",
        "pas",
        "y",
        "moi",
        "il",
        "elle",
        "on",
        "ce",
        "cette",
        "ces",
        "son",
        "sa",
        "ses",
        "mon",
        "ma",
        "mes",
        "en",
        "dans",
        "par",
        "pour",
        "sur",
        "avec",
        "sans",
        "etre",
        "avoir",
        "est",
        "sont",
        "a",
        "aux",
    }
)
_IRI_RE = re.compile(re.escape(ONTOLOGY_NS) + r"(" + LOCAL_NAME_RE.pattern[1:-1] + r")")
_SKIP_POS = frozenset({"PUNCT", "SPACE", "SYM"})


def content_tokens(doc: FrenchDoc) -> list[Token]:
    return [token for token in doc.tokens if _is_content(token)]


def resolve_classes(doc: FrenchDoc) -> list[str]:
    """Return ontology classes mentioned in ``doc``, most specific first."""
    content = content_tokens(doc)
    hits: list[tuple[str, int, int]] = []
    exact = set(all_class_names())
    for local_name, words in _class_forms():
        width = len(words)
        if width == 0 or width > len(content):
            continue
        for start in range(len(content) - width + 1):
            if all(_same(content[start + offset], words[offset]) for offset in range(width)):
                hits.append((local_name, start, start + width))
    for index, token in enumerate(content):
        if token.text in exact:
            hits.append((token.text, index, index + 1))

    kept: list[tuple[str, int, int]] = []
    for local_name, start, end in sorted(hits, key=lambda item: (-(item[2] - item[1]), item[1], item[0])):
        span = set(range(start, end))
        if any(span & set(range(other_start, other_end)) for _name, other_start, other_end in kept):
            continue
        kept.append((local_name, start, end))

    names = {local_name for local_name, _start, _end in kept}
    resolved: list[str] = []
    seen: set[str] = set()
    for local_name, _start, _end in kept:
        if local_name in seen:
            continue
        if any(is_ancestor(local_name, other) for other in names if other != local_name):
            continue
        seen.add(local_name)
        resolved.append(local_name)
    return resolved


def resolve_individuals(
    question: str,
    doc: FrenchDoc,
    individuals: frozenset[str] | None,
) -> list[str]:
    """Resolve known names, or safe local-name candidates for a live lookup."""
    known = individuals
    reserved = set(all_class_names()) | set(reserved_names()) if known is None else set()
    reserved_parts = {
        normalize(word)
        for local_name in all_class_names()
        for word in display_name(local_name).split()
    }
    reserved_parts.update(
        normalize(word)
        for item in list_properties()
        for word in item.display_name.split()
    )
    found: list[str] = []
    seen: set[str] = set()
    candidates = [
        (
            token.text,
            token.pos == "PROPN"
            and index > 0
            and normalize(token.text) not in reserved_parts,
        )
        for index, token in enumerate(doc.tokens)
    ]
    candidates.extend((name, True) for name in _IRI_RE.findall(question))
    for local_name, proper_noun in candidates:
        if (
            LOCAL_NAME_RE.fullmatch(local_name)
            and len(local_name) <= MAX_LOCAL_NAME
            and (
                known is None and local_name not in reserved
                or known is not None and local_name in known
            )
            and local_name not in seen
            and (proper_noun or _CAMEL_RE.search(local_name) or "_" in local_name)
        ):
            seen.add(local_name)
            found.append(local_name)
    return found


def resolve_properties(doc: FrenchDoc, classes: list[str] | None = None) -> list[str]:
    """Match ontology property names by their lemmatized CamelCase components."""
    content = content_tokens(doc)
    hits: list[tuple[str, int, int]] = []
    class_words = {
        normalize(word)
        for local_name in classes or ()
        for word in display_name(local_name).split()
    }
    for item in list_properties():
        words = tuple(part for part in item.display_name.split() if part)
        width = len(words)
        if not width:
            continue
        for index, token in enumerate(content):
            if any(
                normalize(word) not in class_words and _same(token, word)
                for word in words
            ):
                hits.append((item.local_name, index, index + 1))
        if any(token.text == item.local_name for token in content):
            hits.append((item.local_name, 0, 1))

    selected = sorted(hits, key=lambda item: (-(item[2] - item[1]), item[1], item[0]))
    resolved: list[str] = []
    seen: set[str] = set()
    for local_name, _start, _end in selected:
        if local_name not in seen:
            seen.add(local_name)
            resolved.append(local_name)
    return resolved


def _is_content(token: Token) -> bool:
    if token.pos in _SKIP_POS or token.lemma in _FUNCTION:
        return False
    return bool(normalize(token.text))


def _same(token: Token, word: str) -> bool:
    surface = normalize(word)
    lemma = _word_lemma(word)
    observed = {token.lemma, normalize(token.text)}
    observed.discard("")
    for candidate in (surface, lemma):
        if not candidate:
            continue
        if candidate in observed:
            return True
        if any(value in {candidate + "s", candidate + "x"} for value in observed):
            return True
    return False


_CAMEL_RE = re.compile(r"[a-z][A-Z]")


@lru_cache(maxsize=1)
def _class_forms() -> tuple[tuple[str, tuple[str, ...]], ...]:
    forms: list[tuple[str, tuple[str, ...]]] = []
    for local_name in all_class_names():
        words = tuple(part for part in display_name(local_name).split() if part)
        forms.append((local_name, words))
    return tuple(forms)


@cache
def _word_lemma(word: str) -> str:
    doc = analyze(word)
    lemmas = [token.lemma for token in doc.tokens if token.lemma]
    if len(lemmas) == 1:
        return lemmas[0]
    return normalize(word)
