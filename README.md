# sparql-rdfs-rewriter

A lightweight Python library for **SPARQL algebra–level query rewriting**, implementing RDFS entailment (subclass, subproperty, domain) on RDFLib. Designed for **dynamic DL-Lite–style systems**, it expands queries on-the-fly without materializing triples.

---

## Overview

This project implements a **query rewriting–based RDFS entailment regime** purely in Python. Instead of materializing inferred triples, it transforms SPARQL algebra before execution:

```
Query → Parse → Rewrite → Execute
```

The base RDF graph remains unchanged.

---

## Supported RDFS Fragment

* `rdfs:subClassOf` (transitive closure)
* `rdfs:subPropertyOf` (transitive closure)
* `rdfs:domain`

Rewriting operates on triple patterns and basic graph patterns according to schema entailments.

---

## Features

* Lightweight RDFS entailment via **query rewriting**
* Avoids materialization-based reasoning
* Pruning technics for UNION explosion
    - remove duplicates
    - Prune combinations that are dominated by others
* Suitable for **dynamic, frequently updated datasets**

> Note: Does not provide full OWL reasoning.