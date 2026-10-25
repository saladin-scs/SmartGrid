"""SPARQL access to the Apache Jena Fuseki dataset."""

from .exceptions import (
    SparqlConfigError,
    SparqlQueryError,
    SparqlServiceError,
    SparqlUpdateError,
)
from .service import SparqlService

__all__ = [
    'SparqlConfigError',
    'SparqlQueryError',
    'SparqlService',
    'SparqlServiceError',
    'SparqlUpdateError',
]
