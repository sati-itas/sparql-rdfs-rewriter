from rdflib.namespace import RDF
from rdflib.namespace import RDFS
from rdflib.term import Variable

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

        self._fresh_counter = 0

        self.parser = SPARQLParser()

    def _fresh_var(self):
        """Fresh existential variable for domain/range reformulation."""
        self._fresh_counter += 1
        return Variable(f'__rw{self._fresh_counter}')

    def rewrite_query_str(self, query: str) -> Query:
        """Rewrites the given SPARQL query based on implicit schema graph and returns the rewritten Query object."""
        q = self.parser.parse(query)

        #
        bgp = self.extract_bgp(q)
        rewritten = self.rewrite_bgp(bgp, self.idx)
        union_set = self.build_union_ast(rewritten)
        q = self.inject_union(q, union_set)

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
        idx = {
            'subClass': {},     # class -> transitive subclasses
            'subProperty': {},  # prop  -> transitive subproperties
            'domain': {},       # prop  -> domain class
            'range': {},        # prop  -> range class
            'domainOf': {},     # class -> props with that exact domain
            'rangeOf': {},      # class -> props with that exact range
        }

        # direct parent -> children edges
        sub_class_direct = {}
        for s, _, o in schema_graph.triples((None, RDFS.subClassOf, None)):
            sub_class_direct.setdefault(o, set()).add(s)

        sub_prop_direct = {}
        for s, _, o in schema_graph.triples((None, RDFS.subPropertyOf, None)):
            sub_prop_direct.setdefault(o, set()).add(s)

        # transitive closure so e.g. Manager (sub Employee sub Person) is found
        # when expanding Person
        idx['subClass'] = self._transitive_closure(sub_class_direct)
        idx['subProperty'] = self._transitive_closure(sub_prop_direct)

        for s, _, o in schema_graph.triples((None, RDFS.domain, None)):
            idx['domain'][s] = o
            idx['domainOf'].setdefault(o, set()).add(s)

        for s, _, o in schema_graph.triples((None, RDFS.range, None)):
            idx['range'][s] = o
            idx['rangeOf'].setdefault(o, set()).add(s)

        return idx

    def _transitive_closure(self, direct):
        """direct: node -> set(direct descendants). Returns node -> set(all
        transitive descendants)."""
        closure = {}
        for node in direct:
            seen = set()
            stack = list(direct[node])
            while stack:
                d = stack.pop()
                if d in seen:
                    continue
                seen.add(d)
                stack.extend(direct.get(d, ()))
            closure[node] = seen
        return closure

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
        # A (s rdf:type C) answer is entailed by:
        #   - (s rdf:type C') for any subclass C' of C
        #   - (s p _) for any property p whose domain is C (or a subclass of C)
        #   - (_ p s) for any property p whose range  is C (or a subclass of C)
        if p == RDF.type:
            classes = idx['subClass'].get(o, set()) | {o}
            for c in classes:
                alts.add((s, RDF.type, c))

                # DOMAIN: property edge from s implies s is of the domain class
                for pr in idx['domainOf'].get(c, ()):
                    alts.add((s, pr, self._fresh_var()))

                # RANGE: property edge into s implies s is of the range class
                for pr in idx['rangeOf'].get(c, ()):
                    alts.add((self._fresh_var(), pr, s))

        # CASE 2: Property
        # A (s p o) answer is entailed only by (s p' o) for subproperties p' of
        # p. Domain/range do NOT generate new p-edges, so expanding them here is
        # unsound (broadens the pattern, drops the o-constraint) -> handled in
        # CASE 1 instead.
        else:
            props = idx['subProperty'].get(p, set()) | {p}
            for pr in props:
                alts.add((s, pr, o))

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

        # All BGPs to a *balanced* Union tree. A left-deep chain
        # (Union(Union(Union(...)))) makes rdflib's evalUnion recurse once per
        # node when evaluating, so a large cartesian product (e.g. many
        # domain-expanded triples -> 2^n combinations) overflows Python's
        # recursion limit. A balanced tree keeps eval depth at O(log n).
        if not bgps:
            return None

        nodes = bgps
        while len(nodes) > 1:
            nodes = [
                Union(nodes[i], nodes[i + 1]) if i + 1 < len(nodes) else nodes[i]
                for i in range(0, len(nodes), 2)
            ]
        return nodes[0]

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