"""Hybrid retrieval without paid APIs. Local vectors encode words, not semantic embeddings."""
import hashlib
import math
import os
import re
import unicodedata
from falkordb import FalkorDB

DIMENSION = 96


def terms(text):
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    stop = {"les", "des", "une", "pour", "est", "avec", "dans", "qui", "que", "comment", "sur"}
    return [t for t in re.findall(r"[a-z0-9]+", normalized) if len(t) > 2 and t not in stop]


def lexical_vector(text):
    vector = [0.0] * DIMENSION
    for term in terms(text):
        index = int.from_bytes(hashlib.sha256(term.encode()).digest()[:4], "big") % DIMENSION
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else None


def graph():
    return FalkorDB(host=os.environ.get("FALKOR_HOST", "falkor"), port=6379).select_graph("maas_demo")


def search_sources(text):
    g = graph()
    tokens = terms(text)
    vector = lexical_vector(text)
    if not tokens:
        return []
    lexical = g.query("CALL db.idx.fulltext.queryNodes('Passage', $query) YIELD node, score RETURN node.id ORDER BY score DESC LIMIT 5", {"query": "|".join(tokens)}).result_set
    semantic = g.query("CALL db.idx.vector.queryNodes('Passage', 'lexical_vector', 5, vecf32($v)) YIELD node, score RETURN node.id ORDER BY score ASC", {"v": vector}).result_set
    # Reciprocal rank fusion. No comparison of incomparable lexical/distance scores.
    ranks = {}
    for rows in (lexical, semantic):
        for i, row in enumerate(rows):
            ranks[row[0]] = ranks.get(row[0], 0) + 1 / (60 + i + 1)
    ids = sorted(ranks, key=ranks.get, reverse=True)[:4]
    if not ids:
        return []
    rows = g.query("MATCH (p:Passage)-[:FROM]->(d:Document) WHERE p.id IN $ids OPTIONAL MATCH (p)-[:APPLIES_TO]->(product:Product)-[:SOLD_BY]->(actor:Actor) RETURN d.id, d.title, p.text, d.version, d.digest, collect(DISTINCT actor.id)", {"ids": ids}).result_set
    found = [{"id": r[0], "title": r[1], "text": r[2], "version": r[3], "digest": r[4], "actors": r[5], "retrieval_score": ranks[r[0]]} for r in rows]
    return sorted(found, key=lambda s: s["retrieval_score"], reverse=True)
