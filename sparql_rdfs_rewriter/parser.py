from rdflib.plugins.sparql import algebra, parser

class SPARQLParser:
    def parse(self, sparql: str):
        parsed = parser.parseQuery(sparql)
        return algebra.translateQuery(parsed)

    def get_sparql_string(self, query) -> str:
        return algebra.translateAlgebra(query)
