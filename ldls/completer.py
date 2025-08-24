from __future__ import annotations

import os
import re
from itertools import chain
from os.path import expanduser
from pathlib import Path
from typing import Iterable

from . import Completion, Err, TermInfo
from .cache import GraphCache
from .keywords import LANG_KEYWORDS
from .utils import get_term_at

MAX_LINE_SCAN = 80
MATCH_NS_DECL = re.compile(
    r'''(?:@prefix\s+|xmlns:?|vocab|prefix\s+|PREFIX\s+|")(?:@vocab|(\w*))"?[:=]\s*[<"'"](.+?)[>"']'''
)

VOCAB_SOURCE_MAP = {
    "https://schema.org/": "https://schema.org/version/latest/schemaorg-current-https.ttl",
    "http://schema.org/": "https://schema.org/version/latest/schemaorg-current-http.ttl",
    # "http://www.w3.org/2001/XMLSchema#": "./xsd.ttl",
}

XDG_CACHE_HOME = os.environ.get('XDG_CACHE_HOME', expanduser('~/.cache'))

DEFAULT_RDF_GRAPH_CACHE_DIR = XDG_CACHE_HOME + '/rdf-graph-cache/'
RDF_GRAPH_CACHE_DIRS = [
    os.environ.get('RDF_GRAPH_CACHE', expanduser('~/.rdf-graph-cache')),
    DEFAULT_RDF_GRAPH_CACHE_DIR,
    '/usr/local/share/rdf-graph-cache/',
]


Lines = list[str]


def find_rdf_graph_cache_dir() -> Path:
    for fpath in RDF_GRAPH_CACHE_DIRS:
        if os.path.isdir(fpath):
            return Path(fpath)

    default_cachedir = Path(DEFAULT_RDF_GRAPH_CACHE_DIR)
    if not default_cachedir.exists():
        default_cachedir.mkdir(exist_ok=True, parents=True)
    else:
        assert default_cachedir.is_dir()

    return default_cachedir


def get_pfxns(line: str) -> Iterable[tuple[str, str]]:
    return MATCH_NS_DECL.findall(line)


def get_pfxns_map(buffer: Lines) -> dict[str, str]:
    return {pfx: ns for line in buffer[:MAX_LINE_SCAN] for pfx, ns in get_pfxns(line)}


class RdfCompleter:
    graphcache: GraphCache
    _terms_by_ns: dict[str, dict[str, TermInfo] | None]

    def __init__(self, cachedir=None):
        if cachedir is None:
            cachedir = find_rdf_graph_cache_dir()
        self.graphcache = GraphCache(cachedir, VOCAB_SOURCE_MAP)
        self._terms_by_ns = {}
        self._keywords = LANG_KEYWORDS

    def get_vocab_terms(self, ns: str | None) -> dict[str, TermInfo]:
        if ns is None:
            return {}

        if ns not in self._terms_by_ns:
            self._terms_by_ns[ns] = self.graphcache.collect_vocab_terms(ns)

        return self._terms_by_ns.get(ns) or {}

    def get_completions(
        self, buffer: Lines, line: str, col: int, lang: str | None = None
    ) -> list[Completion]:
        term = get_term_at(line, col - 1)
        assert term is not None
        pfx, cln, trail = term.partition(':')

        prefixdecl = line.split(':')[0].strip()
        pfx_fmt = (
            '%s: <%s>'
            if prefixdecl.startswith(('PREFIX', 'prefix', '@prefix'))
            else '%s="%s"' if prefixdecl == 'xmlns' else None
        )

        ns: str | None
        results: Iterable[str]
        if pfx_fmt:
            if term.endswith(':'):
                ns = self.graphcache.prefixes.lookup(term[:-1])
                results = [" <%s>" % ns] if ns else []
            else:
                results = self._get_pfx_declarations(pfx_fmt, trail)
        else:
            pfxns = get_pfxns_map(buffer)
            ns = pfxns.get(pfx)
            terms = self.get_vocab_terms(ns)
            if terms and ':' in term:
                return sorted(
                    Completion(key, res_type, res_comment)
                    for key, (res_type, res_comment) in terms.items()
                    if key.startswith(trail)
                )

            keywords = self._keywords.get(lang, [])
            curies = chain((pfx + ':' for pfx in sorted(pfxns)), terms, keywords)
            results = (curie for curie in curies if curie.startswith(trail))

        return [Completion(value) for value in results]

    def expand_pfx(self, buffer: Lines, pfx: str) -> str | None:
        return get_pfxns_map(buffer).get(pfx)

    def to_pfx(self, buffer: Lines, uri: str) -> str | None:
        for pfx, ns in get_pfxns_map(buffer).items():
            if ns == uri:
                return pfx
        return None

    def _get_pfx_declarations(self, pfx_fmt, base):
        return [
            pfx_fmt % (pfx, ns)
            for pfx, ns in self.graphcache.prefixes.namespaces()
            if pfx.startswith(base)
        ]

    def get_term(
        self, buffer: Lines, line: str, col: int, lang: str | None = None
    ) -> tuple[str | None, str]:
        term = get_term_at(line, col)
        if not term:
            return None, ''

        if ':' not in term:  # OK in RDF/XML and JSON-LD (and special in RDFa)
            return None, ''

        pfx, lname = term.split(':', 1)
        ns = self.expand_pfx(buffer, pfx)

        return ns, lname or ''

    def get_fs_path(self, url: str) -> Path:
        return self.graphcache._get_fs_path(url)

    def find_term_definition(
        self, lines: Lines, ns: str, lname: str
    ) -> tuple[int, int]:
        prefixes: dict[str, str] = {}
        expanded_term = f"<{ns}{lname}>"
        col = -1
        for at_line, l in enumerate(lines):
            if at_line < MAX_LINE_SCAN:
                for def_pfx, def_ns in get_pfxns(l):
                    if def_ns not in prefixes:
                        prefixes[def_ns] = def_pfx

            dpfx = prefixes.get(ns)
            defterm = f"{dpfx}:{lname}" if dpfx is not None else expanded_term

            m = re.search(fr"^{re.escape(defterm)}\b", l)
            if m:
                col = 0
                break
        else:
            at_line = 0
            col = 0

        return at_line, col

    def check(self, buffer: Lines, lang: str | None = None) -> Iterable[Err]:
        if lang == 'sparql':
            return

        data = ''.join(buffer)
        if err := self.graphcache.check_data(data, lang):
            yield err


if __name__ == '__main__':

    import logging

    from .cache import logger

    rootlogger = logger  # logging.getLogger()
    rootlogger.addHandler(logging.StreamHandler())
    rootlogger.setLevel(logging.DEBUG)

    import sys

    args = sys.argv[1:]
    pfx = args.pop(0) if args else 'schema'

    rdfcompleter = RdfCompleter()

    if pfx == '-':
        lines = sys.stdin.readlines()
        for err in rdfcompleter.check(lines):
            print(err)
    elif ':' in pfx:
        pfx, lname = pfx.rsplit(':', 1)
        ns = rdfcompleter.graphcache.prefixes.lookup(pfx)
        if ns:
            fpath = rdfcompleter.graphcache._get_fs_path(ns)
            with fpath.open() as f:
                lines = f.readlines()
            lno, col = rdfcompleter.find_term_definition(lines, ns, lname)
            print(f"{fpath}@{lno},{col}:\n\t{lines[lno]!r}")
    else:
        ns = rdfcompleter.graphcache.prefixes.lookup(pfx)
        print("%s: %s" % (pfx, ns))
        for t in rdfcompleter.get_vocab_terms(ns):
            print("    %s" % t)
