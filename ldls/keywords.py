LANG_KEYWORDS = {}

LANG_KEYWORDS['turtle'] = ['a', 'prefix', 'base', 'PREFIX', 'BASE']
LANG_KEYWORDS['trig'] = LANG_KEYWORDS['turtle'] + ['graph']

sparql11_kws = "BASE PREFIX SELECT DISTINCT REDUCED AS CONSTRUCT WHERE DESCRIBE ASK FROM NAMED GROUP BY HAVING ORDER ASC DESC LIMIT OFFSET VALUES LOAD SILENT INTO CLEAR DROP CREATE ADD TO MOVE COPY WITH DELETE INSERT USING DEFAULT GRAPH ALL OPTIONAL SERVICE BIND AS UNDEF MINUS UNION FILTER a IN NOT EXISTS SEPARATOR true false".split()
sparql11_funcs = "STR LANG LANGMATCHES DATATYPE BOUND IRI URI BNODE RAND ABS CEIL FLOOR ROUND CONCAT STRLEN UCASE LCASE ENCODE_FOR_URI CONTAINS STRSTARTS STRENDS STRBEFORE STRAFTER YEAR MONTH DAY HOURS MINUTES SECONDS TIMEZONE TZ NOW UUID STRUUID MD5 SHA1 SHA256 SHA384 SHA512 COALESCE IF STRLANG STRDT sameTerm isIRI isURI isBLANK isLITERAL isNUMERIC REGEX SUBSTR REPLACE COUNT SUM MIN MAX AVG SAMPLE GROUP_CONCAT".split() + ['GROUP BY', 'ORDER BY', 'NOT IN', 'NOT EXISTS']
sparql12_funcs = "hasLANG hasLANGDIR STRLANGDIR isTRIPLE TRIPLE SUBJECT PREDICATE OBJECT".split()

sparql_kws = sparql11_kws + sparql11_funcs + sparql12_funcs

LANG_KEYWORDS['sparql'] = sparql_kws + [kw.lower() for kw in sparql_kws if kw.isupper()]

LANG_KEYWORDS['jsonld'] = [
    '@context',
    '@vocab',
    '@base',
    '@id',
    '@type',
    '@language',
    '@container',
    '@list',
    '@set',
    '@index',
]

# TODO: add the rdf-prefixed ones to the ns complete (they're not in the vocab
# but part of the syntax)
LANG_KEYWORDS['rdf'] = [
    'rdf:Description',
    'rdf:RDF',
    'rdf:about',
    'rdf:ID',
    'rdf:resource',
    'rdf:datatype',
    'xmlns',
    'xml:lang',
]
