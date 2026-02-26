from rdflib.namespace import RDF
from rdflib.namespace import RDFS

from rdflib.plugins.sparql import algebra
from rdflib.plugins.sparql.algebra import BGP
from rdflib.plugins.sparql.algebra import Union
from rdflib.plugins.sparql.sparql import Query

from sparql_rdfs_rewriter.parser import SPARQLParser
from itertools import product

class RDFSRewriter:
    """RDFS Query Rewriter for SPARQL queries based on a schema graph."""

    # https://titan.dcs.bbk.ac.uk/~michael/sw15/slides/SPARQL.pdf
    # https://doi.org/10.1007/s13218-020-00671-w

    def __init__(self, schema_graph):
        self.idx = self.build_rdfs_index(schema_graph)

        self.parser = SPARQLParser()

    def rewrite_query_str(self, query: str) -> Query:
        """Rewrites the given SPARQL query based on implicit schema graph and returns the rewritten Query object."""
        q = self.parser.parse(query)

        #
        bgp = self.extract_bgp(q)
        rewritten = self.rewrite_bgp(bgp, self.idx)
        union_set = self.build_union_ast(rewritten)
        q = self.inject_union(q, union_set)

        # algebra translate to SPARQL-String
        rewritten_query = self.parser.get_sparql_string(q)

        return q

    def rewrite_query(self, query: Query) -> str:
        """Rewrites the given SPARQL query based on implicit schema graph and returns the rewritten SPARQL string."""
        if isinstance(query, Query):
            q = query
        else:
            raise ValueError("Input must be a Query object")

        #
        bgp = self.extract_bgp(q)
        rewritten = self.rewrite_bgp(bgp, self.idx)
        union_set = self.build_union_ast(rewritten)
        q = self.inject_union(q, union_set)

        return q

    def build_rdfs_index(self, schema_graph):
        idx = {'subClass': {}, 'subProperty': {}, 'domain': {}, 'range': {}}

        for s, _, o in schema_graph.triples((None, RDFS.subClassOf, None)):
            idx['subClass'].setdefault(o, set()).add(s)

        for s, _, o in schema_graph.triples((None, RDFS.subPropertyOf, None)):
            idx['subProperty'].setdefault(o, set()).add(s)

        for s, _, o in schema_graph.triples((None, RDFS.domain, None)):
            idx['domain'][s] = o

        for s, _, o in schema_graph.triples((None, RDFS.range, None)):
            idx['range'][s] = o

        return idx

    def rewrite_bgp(self, patterns, idx):
        """Basic Graph Pattern rewriting"""
        rewritten = []

        for s, p, o in patterns:
            alts = self.rewrite_triple(s, p, o, idx)
            rewritten.append(alts)

        return rewritten

    def rewrite_triple(self, s, p, o, idx):
        alts = set()

        # CASE 1: rdf:type C
        if p == RDF.type:
            classes = idx['subClass'].get(o, set()) | {o}
            for c in classes:
                alts.add((s, RDF.type, c))

        # CASE 2: Property
        else:
            props = idx['subProperty'].get(p, set()) | {p}
            for pr in props:
                alts.add((s, pr, o))

                # DOMAIN
                if pr in idx['domain']:
                    alts.add((s, RDF.type, idx['domain'][pr]))

                # # RANGE
                # if pr in idx["range"]:
                #     alts.add((o, RDF.type, idx["range"][pr]))

        return alts

    def prune_combinations(
        self, combos
    ):  # Prune combinations that are dominated by others (i.e., subsets)
        pruned = []

        for c in combos:
            c_set = set(c)
            dominated = False

            for other in combos:
                if c != other and c_set.issuperset(set(other)):
                    dominated = True
                    break

            if not dominated:
                pruned.append(c)

        return pruned

    def build_union_ast(self, alternatives_per_triple):
        """
        alternatives_per_triple = [
            [(s,p,o), (s,p,o2)],   # Triple 1 alternatives
            [(s2,p2,o2)],          # Triple 2 alternatives
        ]
        """

        all_combinations = list(product(*alternatives_per_triple))

        # Prune combinations that are dominated by others
        all_combinations = self.prune_combinations(all_combinations)

        seen = set()
        bgps = []
        ## remove duplicates
        for combo in all_combinations:
            canon = tuple(sorted(combo))  # canonical form
            if canon not in seen:
                seen.add(canon)
                bgps.append(BGP(list(combo)))

        # All BGPs to a nested Union
        if not bgps:
            return None

        u = bgps[0]
        for b in bgps[1:]:
            u = Union(u, b)
        return u

    def extract_bgp(self, q):
        """Extracts triples from the WHERE clause of a SPARQL query."""
        bgps = []

        def finder(node):
            # algebra nodes have .name
            if hasattr(node, 'name') and node.name == 'BGP':
                bgps.append(node.triples)
            return None  # keep everything else

        algebra.traverse(q.algebra, finder)
        if not bgps:
            raise ValueError('No BGP found')
        elif len(bgps) == 1:
            return bgps[0]
        else:
            # merge multiple BGPs
            merged = []
            for b in bgps:
                merged.extend(b)
            return merged

    def inject_union(self, q, union_node):
        """Injects the union node into the query algebra, replacing the original BGP."""

        def updater(node):
            # algebra nodes have .name
            if hasattr(node, 'name') and node.name == 'BGP':
                return union_node  # replace BGP
            return None  # keep everything else

        q.algebra = algebra.traverse(q.algebra, updater)
        return q