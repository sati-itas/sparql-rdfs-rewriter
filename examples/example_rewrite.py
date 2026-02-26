from sparql_rdfs_rewriter import RDFSRewriter
from sparql_rdfs_rewriter import SPARQLParser
from rdflib import Graph

tbox = Graph()
tbox.parse('examples/example.ttl', format='turtle')

query_str = """PREFIX ex: <http://example.org/>
            SELECT ?s ?o
            WHERE {
                ?s ex:memberOf ?o .
            }
            """

rewriter = RDFSRewriter(tbox)
rewritten_queries = rewriter.rewrite_query_str(query_str)
parser = SPARQLParser()
# algebra translate to SPARQL-String
rewritten_query_string = parser.get_sparql_string(rewritten_queries)

print("Original query:")
print(query_str)
print("\nRewritten queries:")
print(rewritten_query_string)

