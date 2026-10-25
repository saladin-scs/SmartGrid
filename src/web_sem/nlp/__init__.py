"""Natural-language entry points.

CRUD name checks call :func:`prepare_individual_name` and nothing else.
Question answering lives in :mod:`web_sem.nlp.service`.
"""


def prepare_individual_name(name: str) -> str:
    """Collapse whitespace in an individual name before CRUD validation."""
    return " ".join(name.split())
