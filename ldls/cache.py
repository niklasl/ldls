from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Iterable, NamedTuple, cast
from urllib.parse import quote

from trld.api import parse_rdf, serialize_rdf, text_input
from trld.jsonld.base import JsonMap, as_list
from trld.jsonld.compaction import compact
from trld.jsonld.context import get_context
from trld.jsonld.docloader import any_document_loader, set_document_loader
from trld.jsonld.expansion import expand
from trld.jsonld.extras.frameblanks import frameblanks
from trld.jsonld.flattening import flatten
from trld.jsonld.keys import CONTEXT, GRAPH, ID, LANGUAGE, TYPE, VALUE, VOCAB
from trld.trig.parser import (NotationError, ParserError, ParserState,
                              ReadPrefix, ReadSymbol, ReadTerm)

from . import Err, TermInfo
from .utils import split_iri

logger = logging.getLogger(__name__)


class GraphCache:

    cachedir: Path
    mtime_map: dict[str, float]
    vocab_source_map: dict[str, str]
    prefixes: PrefixCache
    _terms_cache: dict[str, set[str]]

    def __init__(self, cachedir: Path | str, vocab_source_map: dict[str, str] | None):
        self.cachedir = Path(cachedir)
        self.mtime_map = {}
        self.vocab_source_map = vocab_source_map or {}
        self.prefixes = PrefixCache(self.cachedir / 'prefixes.ttl')

        self._terms_cache = {}
        self._monkeypatch_parser()

    def collect_vocab_terms(self, ns: str) -> dict[str, TermInfo]:
        data = self._load(ns)
        ctx = cast(dict, data.get(CONTEXT)) or {}

        terms: dict[str, TermInfo] = {}

        for desc in as_list(data[GRAPH]):
            if ID not in desc:
                continue

            if TYPE not in desc or 'rdfs:isDefinedBy' not in desc:
                continue

            uri, leaf = split_iri(desc[ID])
            uri = ctx.get(uri.removesuffix(':'), uri)

            if uri != ns or not leaf:
                continue

            rtype: str | None = None
            rcomment: str | None = None

            for rtype in desc.get(TYPE):
                break

            for res_comment in as_list(desc.get('rdfs:comment')):
                if isinstance(res_comment, str):
                    rcomment = res_comment
                elif isinstance(res_comment, dict):
                    # TODO: $LANG or 'en_us' or 'en_gb' or 'en'
                    rcomment = str(res_comment.get(VALUE))
                    break

            terms[leaf] = TermInfo(rtype, rcomment)

        if ns not in self._terms_cache:
            self._terms_cache[ns] = set(terms)

        return terms  # TODO: OrderedDict

    def _load(self, url: str) -> JsonMap:
        src = self.vocab_source_map.get(str(url), url)

        if os.path.isfile(url):
            last_vocab_mtime = self.mtime_map.get(url)
            vocab_mtime = os.stat(url).st_mtime

            if not last_vocab_mtime or last_vocab_mtime < vocab_mtime:
                logger.debug("Parse file: '%s'", url)
                self.mtime_map[url] = vocab_mtime
                return self._read(src)

        cache_path = self._get_fs_path(url)

        if cache_path.exists() and cache_path.stat().st_size > 0:
            logger.debug("Load local copy of <%s> from '%s'", url, cache_path)
            return self._read(cache_path)
        else:  # Fetch and add serialized Turtle to cache
            logger.debug("Fetching <%s> to '%s'", url, cache_path)
            data = self._read(url)
            recompact(data, self.prefixes._ns_by_prefix)

            serialize_rdf(data, 'turtle', cache_path)

            return data

    def _read(self, src: str | Path, fmt: str | None = None) -> JsonMap:
        data = parse_rdf(str(src))
        return data

    def _get_fs_path(self, url: str) -> Path:
        return self.cachedir / (quote(url, safe="") + '.ttl')

    def check_data(self, data: str, fmt: str | None) -> Err | None:
        try:
            # TODO: io wrapper to iterate over buffer directly?
            _ = parse_rdf(text_input(data), fmt)
        except ParserError as e:
            return Err(e.lno - 1, e.cno - 1, str(e.error))
        else:
            return None

    def _monkeypatch_parser(self):
        _real_ReadTerm_pop = ReadTerm.pop

        graphcache = self

        def _monkey_ReadTerm_pop(self: ReadTerm):
            value = _real_ReadTerm_pop(self)

            parent: ParserState | None = self.parent
            while parent:
                if isinstance(parent, ReadPrefix):
                    return value
                parent = getattr(parent, 'parent', None)

            if isinstance(self, ReadSymbol) and ':' in value:
                pfx, local = value.split(':', 1)
                ns = self.context.get(pfx or VOCAB)

                if ns is None:
                    raise NotationError(f"Undeclared prefix for {value}")

                terms = graphcache._terms_cache.get(ns)
                if terms and local not in terms:
                    raise NotationError(f"Term {value} is not defined in <{ns}>")

            return value

        ReadTerm.pop = _monkey_ReadTerm_pop  # type: ignore[method-assign]


class PrefixCache:

    PREFIX_URI_TEMPLATE = 'https://prefix.cc/{pfx}.file.ttl'
    # TODO: occasionally fetch <https://prefix.cc/context.jsonld> to 'prefix-cc-context.jsonld'?

    _prefix_file: Path

    _ns_by_prefix: dict[str, str]
    _prefix_by_ns: dict[str, str]

    def __init__(self, prefix_file: Path):
        self._ns_by_prefix = {}
        self._prefix_by_ns = {}
        self._prefix_file = prefix_file
        if prefix_file.is_file():
            self._load_prefixes(prefix_file)

    def _load_prefixes(self, src: str | Path) -> None:
        data = parse_rdf(str(src))
        if CONTEXT in data:
            for k, v in cast(dict, data[CONTEXT]).items():
                if isinstance(v, str):
                    self._ns_by_prefix[k] = v
                    self._prefix_by_ns[v] = k

    def compact(self, iri: str) -> str:
        ns, local = split_iri(iri)
        if pfx := self._prefix_by_ns.get(ns):
            return f"{pfx}:{local}"
        return iri

    def lookup(self, pfx: str) -> str | None:
        ns = self._ns_by_prefix.get(pfx)
        return ns or self._fetch_ns(pfx)

    def namespaces(self) -> Iterable[tuple[str, str]]:
        yield from self._ns_by_prefix.items()

    def _fetch_ns(self, pfx: str) -> str | None:
        url = self.PREFIX_URI_TEMPLATE.format(pfx=pfx)
        logger.debug("Fetching <%s>", url)
        try:
            self._load_prefixes(url)
        except:  # not found or syntax error...
            logger.debug("Could not read <%s>", url)

        if self._prefix_file:
            logger.debug("Saving prefixes to '%s'", self._prefix_file)
            with self._prefix_file.open('w') as f:
                for pfx, ns in self._ns_by_prefix.items():
                    print(f"PREFIX {pfx}: <{ns}>", file=f)

        return self._ns_by_prefix.get(pfx)


def recompact(data: dict, prefixes: dict) -> dict:
    context = {CONTEXT: prefixes}
    base_iri = ""
    ordered = True

    items = expand(data, base_iri, None, ordered=ordered)
    flat = flatten(items, ordered=ordered)
    compacted = compact(context, flat, base_iri, ordered=ordered)
    result = frameblanks(compacted)

    return cast(dict, result)
