# sparql-rdfs-rewriter

A lightweight Python library for **SPARQL query rewriting**, implementing RDFS entailment (subclass, subproperty, domain) based on RDFLib algebra–level. Designed for **dynamic DL-Lite–style systems**, it expands queries on-the-fly without materializing triples.

---

## Overview

This project implements a **query rewriting–based RDFS entailment** purely in Python. Instead of materializing inferred triples, it transforms SPARQL algebra before execution:

```
Query → Parse → Rewrite → Execute
```

---

**Supported RDFS Fragment**

* `rdfs:subClassOf` (transitive closure)
* `rdfs:subPropertyOf` (transitive closure)
* `rdfs:domain`

Rewriting operates on triple patterns and basic graph patterns according to schema entailments.

---

**Description**

* Simple RDFS entailment via **query rewriting**
* Avoids materialization-based reasoning
* Pruning technics for UNION explosion
    - remove duplicates
    - Prune combinations that are dominated by others
* Suitable for **dynamic, frequently updated datasets**

> Note: Does not provide full reasoning.
