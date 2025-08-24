import re

NOT_TERM_CHAR = re.compile(r'[^:A-Za-z0-9-_]|$')

# NOTE: Same tokens as trld.jsonld.base.PREFIX_DELIMS
# (from <https://tools.ietf.org/html/rfc3986#section-2.2>).
IRI_LOCAL = re.compile(r'([^:/?#\[\]@]*)$')


def get_term_at(line: str, i: int) -> str | None:
    """
    >>> get_term_at('some rdf:term here', 7)
    'rdf:term'
    >>> get_term_at('some rdf:term here', 12)
    'rdf:term'
    >>> get_term_at('some rdf:term here', 17)
    'here'
    >>> get_term_at('<> a bibo:Article', 16)
    'bibo:Article'
    """
    m = NOT_TERM_CHAR.search(line[i:])
    if not m:
        return None
    front = m.span()[0]

    m = NOT_TERM_CHAR.search(line[i::-1])
    if not m:
        return None
    back = m.span()[0]

    return line[i - back + 1 : i + front]


def split_iri(iri: str) -> tuple[str, str]:
    """
    >>> split_iri('http://example.org/ns#term')
    ('http://example.org/ns#', 'term')
    >>> split_iri('http://example.org/ns/term')
    ('http://example.org/ns/', 'term')
    >>> split_iri('urn:x-test:a')
    ('urn:x-test:', 'a')
    """
    ns, local, empty = IRI_LOCAL.split(iri, maxsplit=1)
    return ns, local


if __name__ == '__main__':
    import doctest

    doctest.testmod()
