"""Demonstrates CASE 1 (rdf:type) rewriting with domain AND range expansion.

A `(?x rdf:type C)` pattern is rewritten into a UNION of:
  - `(?x rdf:type C')`   for every subclass C' of C (transitive)
  - `(?x p ?fresh)`      for every property p with domain(p) subclassOf C
                         -> p-edge OUT of ?x implies ?x is of the domain class
  - `(?fresh p ?x)`      for every property p with range(p)  subclassOf C
                         -> p-edge INTO ?x implies ?x is of the range class

The `?fresh` (`__rwN`) variables are the new existential variables introduced
by the domain/range reformulation in CASE 1.
"""

from sparql_rdfs_rewriter import RDFSRewriter
from sparql_rdfs_rewriter import SPARQLParser
from rdflib import Graph

tbox = Graph()
tbox.parse('examples/example_domain_range.ttl', format='turtle')

# ABox: NO explicit rdf:type except carol. Membership of the others is only
# RDFS-entailed via domain/range, so a plain (non-rewritten) query misses them
# unless the graph is materialized. The rewriter recovers them.
abox_ttl = """
@prefix ex: <http://example.org/> .

ex:alice ex:worksFor  ex:acme .    # alice -> Employee (domain) => Person
ex:acme  ex:employs   ex:bob .     # bob   -> Person   (range)
ex:acme  ex:locatedIn ex:berlin .  # acme  -> Company  (domain)
ex:carol a ex:Manager .            # explicit Manager => Person
"""
data = Graph()
data.parse(data=abox_ttl, format='turtle')

rewriter = RDFSRewriter(tbox)
parser = SPARQLParser()


def _rows(graph, query):
    """Run a query (str or Query) against graph, return sorted local names."""
    res = graph.query(query)
    out = set()
    for row in res:
        for term in row:
            if term is not None:
                out.add(term.split('/')[-1])
    return sorted(out)


def show(title, query_str):
    rewritten = rewriter.rewrite_query_str(query_str)
    rewritten_str = parser.get_sparql_string(rewritten)
    print(f'=== {title} ===')
    print('Original:')
    print(query_str.strip())
    print('\nRewritten:')
    print(rewritten_str)
    print(f'\nResult original  : {_rows(data, query_str)}')
    print(f'Result rewritten : {_rows(data, rewritten_str)}')
    print()


# Query 1: ask for Persons.
#   subclasses Person/Employee/Manager
#   domain:  worksFor (domain Employee subClassOf Person) -> (?s worksFor ?fresh)
#   range:   employs  (range  Person)                     -> (?fresh employs ?s)
show(
    'Persons (subclass + domain + range)',
    """PREFIX ex: <http://example.org/>
    SELECT ?s WHERE { ?s a ex:Person . }
    """,
)

# Query 2: ask for Companies.
#   no subclasses
#   domain:  employs, locatedIn (domain Company) -> (?s employs ?f), (?s locatedIn ?f)
#   range:   worksFor (range Company)            -> (?fresh worksFor ?s)
show(
    'Companies (domain x2 + range)',
    """PREFIX ex: <http://example.org/>
    SELECT ?s WHERE { ?s a ex:Company . }
    """,
)
