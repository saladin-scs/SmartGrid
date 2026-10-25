"""Execute SPARQL SELECT queries and controlled updates against Fuseki."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
from typing import Any

from django.conf import settings
from SPARQLWrapper import BASIC, JSON, POST, SELECT, QueryResult, SPARQLWrapper
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException

from .exceptions import (
    SparqlConfigError,
    SparqlQueryError,
    SparqlServiceError,
    SparqlUpdateError,
)

# Strings, IRIs, and comments are masked before keyword checks so literals
# cannot hide or imitate a SPARQL operation.
_MASK_RE = re.compile(
    r'"""[\s\S]*?"""'
    r"|'''[\s\S]*?'''"
    r'|"(?:[^"\\]|\\.)*"'
    r"|'(?:[^'\\]|\\.)*'"
    r'|<[^>]*>'
    r'|#[^\n]*'
)
_TOKEN_RE = re.compile(r'[A-Za-z_]\w*|[{};]')
_OPERATION_FORMS = frozenset(
    {
        'SELECT',
        'ASK',
        'CONSTRUCT',
        'DESCRIBE',
        'INSERT',
        'DELETE',
        'CREATE',
        'CLEAR',
        'DROP',
        'LOAD',
        'COPY',
        'MOVE',
        'ADD',
    }
)
# INSERT and DELETE change triples. Graph administration (DROP, CLEAR, LOAD, ...)
# is rejected so an update cannot wipe the dataset or fetch remote data.
_ALLOWED_UPDATES = frozenset({'INSERT', 'DELETE'})
_MESSAGE_LIMIT = 500


def _top_level_forms(query: str) -> list[str]:
    """Return SPARQL operation keywords that sit outside graph patterns."""
    skeleton = _MASK_RE.sub(' ', query)
    forms: list[str] = []
    depth = 0
    for match in _TOKEN_RE.finditer(skeleton):
        token = match.group()
        if token == '{':
            depth += 1
            continue
        if token == '}':
            depth = max(depth - 1, 0)
            continue
        if token == ';' or depth != 0:
            continue
        if skeleton[match.end() : match.end() + 1] == ':':
            continue
        upper = token.upper()
        if upper in _OPERATION_FORMS:
            forms.append(upper)
    return forms


def _shorten(message: str) -> str:
    text = ' '.join(message.split())
    if len(text) <= _MESSAGE_LIMIT:
        return text
    return f'{text[:_MESSAGE_LIMIT]}...'


def _http_url(value: str, setting: str) -> str:
    if not isinstance(value, str):
        raise SparqlConfigError(f'{setting} must be an absolute HTTP(S) URL.')
    url = value.strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise SparqlConfigError(f'{setting} must be an absolute HTTP(S) URL.')
    return url.rstrip('/')


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    raw = exc.read()
    body = raw.decode('utf-8', errors='replace').strip() if raw else ''
    if body:
        return f'HTTP {exc.code}: {body}'
    return f'HTTP {exc.code}'


class SparqlService:
    """Run SELECT queries and INSERT/DELETE updates against Apache Jena Fuseki."""

    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        *,
        query_url: str | None = None,
        update_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.query_url = _http_url(
            settings.FUSEKI_QUERY_URL if query_url is None else query_url,
            'FUSEKI_QUERY_URL',
        )
        self.update_url = _http_url(
            settings.FUSEKI_UPDATE_URL if update_url is None else update_url,
            'FUSEKI_UPDATE_URL',
        )
        self.username = settings.FUSEKI_ADMIN_USER if username is None else username
        self.password = settings.FUSEKI_ADMIN_PASSWORD if password is None else password
        resolved_timeout = self.DEFAULT_TIMEOUT if timeout is None else timeout
        if (
            isinstance(resolved_timeout, bool)
            or not isinstance(resolved_timeout, int)
            or resolved_timeout <= 0
        ):
            raise SparqlConfigError('Timeout must be a positive integer number of seconds.')
        self.timeout = resolved_timeout

    def select(self, query: str) -> dict[str, Any]:
        """Execute a SPARQL SELECT query and return the SPARQL JSON result."""
        self._require_select(query)
        client = self._client()
        client.setQuery(query)
        client.setReturnFormat(JSON)
        client.setMethod(POST)
        if client.queryType != SELECT:
            raise SparqlQueryError('Only SELECT queries are accepted.')

        result = self._call(client, SparqlQueryError)
        try:
            payload = result.convert()
        except json.JSONDecodeError as exc:
            raise SparqlQueryError('Fuseki returned invalid JSON.') from exc
        finally:
            result.response.close()

        results = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(results, dict) or not isinstance(results.get('bindings'), list):
            raise SparqlQueryError('Fuseki did not return SPARQL JSON bindings.')
        return payload

    def update(self, query: str) -> None:
        """Execute an INSERT or DELETE update. Other SPARQL updates are rejected."""
        self._require_update(query)
        client = self._client()
        client.setQuery(query)
        client.setMethod(POST)
        if client.queryType not in _ALLOWED_UPDATES or not client.isSparqlUpdateRequest():
            raise SparqlUpdateError('Only INSERT and DELETE updates are accepted.')

        result = self._call(client, SparqlUpdateError)
        try:
            result.response.read()
        finally:
            result.response.close()

    def _require_select(self, query: str) -> None:
        if not isinstance(query, str) or not query.strip():
            raise SparqlQueryError('SPARQL query is empty.')
        forms = _top_level_forms(query)
        if not forms or any(form != 'SELECT' for form in forms):
            raise SparqlQueryError('Only SELECT queries are accepted.')

    def _require_update(self, query: str) -> None:
        if not isinstance(query, str) or not query.strip():
            raise SparqlUpdateError('SPARQL update is empty.')
        forms = _top_level_forms(query)
        if not forms or any(form not in _ALLOWED_UPDATES for form in forms):
            raise SparqlUpdateError('Only INSERT and DELETE updates are accepted.')

    def _client(self) -> SPARQLWrapper:
        client = SPARQLWrapper(
            self.query_url,
            updateEndpoint=self.update_url,
            returnFormat=JSON,
        )
        client.setTimeout(self.timeout)
        if self.username:
            client.setHTTPAuth(BASIC)
            client.setCredentials(self.username, self.password)
        return client

    def _call(
        self,
        client: SPARQLWrapper,
        error_type: type[SparqlServiceError],
    ) -> QueryResult:
        endpoint = self.update_url if error_type is SparqlUpdateError else self.query_url
        try:
            return client.query()
        except SPARQLWrapperException as exc:
            raise error_type(f'{endpoint}: {_shorten(str(exc))}') from exc
        except urllib.error.HTTPError as exc:
            raise error_type(f'{endpoint}: {_shorten(_http_error_message(exc))}') from exc
        except urllib.error.URLError as exc:
            raise error_type(f'Could not reach Fuseki at {endpoint}: {exc.reason}') from exc
        except TimeoutError as exc:
            raise error_type(f'Fuseki request to {endpoint} timed out.') from exc
