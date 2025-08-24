# LDLS &mdash; Linked Data Language Server

This is an LSP-based [language server](https://langserver.org) for editing [RDF](https://en.wikipedia.org/wiki/Resource_Description_Framework)-based [Linked Data](https://en.wikipedia.org/wiki/Linked_data) (mainly [Turtle](https://www.w3.org/TR/turtle/), [TriG](https://www.w3.org/TR/trig/) and [JSON-LD](https://www.w3.org/TR/json-ld/)).

It uses [TRLD](https://github.com/niklasl/trld) for parsing RDF and [pygls](https://pygls.readthedocs.io/en/latest/) for serving the LSP protocol.

## Installation

Installing this as a Python package (globally or in a virtualenv) will add the `ldls` command to the `$PATH` of the target environment. Then add the approriate LSP configuration to your `$EDITOR` of choice.

(For comprehensive examples of configuring a language server, see the [ruff server editor setup](https://docs.astral.sh/ruff/editors/setup/).)

## RDF Data Configuration

This tool will cache RDF prefixes and vocabulary data as Turtle files in `$HOME/.cache/rdf-graph-cache/` (and honors `$XDG_CACHE_HOME` if present). It looks up prefixes using <https://prefix.cc/>.
