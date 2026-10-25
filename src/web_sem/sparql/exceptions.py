"""Errors raised while talking to Apache Jena Fuseki."""


class SparqlServiceError(Exception):
    """Base error for Fuseki SPARQL operations."""


class SparqlConfigError(SparqlServiceError):
    """Fuseki settings are missing or invalid."""


class SparqlQueryError(SparqlServiceError):
    """A SELECT query was rejected or failed against Fuseki."""


class SparqlUpdateError(SparqlServiceError):
    """A SPARQL update was rejected or failed against Fuseki."""
