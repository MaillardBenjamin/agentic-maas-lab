import os
import json
from falkordb import FalkorDB
from maas.domain import CATALOG, digest
from maas.knowledge import lexical_vector

graph = FalkorDB(host=os.environ.get("FALKOR_HOST", "falkor")).select_graph("maas_demo")
for source in CATALOG["sources"]:
    graph.query("MERGE (d:Document {id:$id}) SET d.title=$title, d.version=$version, d.digest=$digest MERGE (p:Passage {id:$id}) SET p.text=$text, p.lexical_vector=vecf32($vector) MERGE (p)-[:FROM]->(d)", {**source, "version": CATALOG["version"], "digest": digest(source), "vector": lexical_vector(source["text"])})
for product in CATALOG["products"]:
    graph.query("MERGE (p:Product {id:$id}) SET p.name=$name, p.actor=$actor, p.price_cents=$price, p.version=$version MERGE (a:Actor {id:$actor}) MERGE (p)-[:SOLD_BY]->(a) MERGE (t:TariffGrid {id:$grid}) SET t.version=$version MERGE (a)-[:PUBLISHES]->(t) MERGE (t)-[:CONTAINS]->(p)", {"id": product["id"], "name": product["name"], "actor": product["actor"], "price": product["price_cents"], "version": CATALOG["version"], "grid": product["actor"] + ":" + CATALOG["version"]})
for source, product in [("tariff-1", "transport"), ("parking-1", "parking"), ("bike-1", "bike")]:
    graph.query("MATCH (p:Passage {id:$source}), (product:Product {id:$product}) MERGE (p)-[:APPLIES_TO]->(product)", {"source": source, "product": product})
for actor in {product["actor"] for product in CATALOG["products"]}:
    grid = {"version": CATALOG["version"], "currency": CATALOG["currency"], "products": [p for p in CATALOG["products"] if p["actor"] == actor]}
    graph.query("MATCH (t:TariffGrid {id:$id}) SET t.rules_json=$rules, t.digest=$digest", {"id": actor + ":" + CATALOG["version"], "rules": json.dumps(grid, ensure_ascii=False), "digest": digest(grid)})
indexes = graph.query("CALL db.indexes()").result_set
if not any(row[0] == "Passage" and "text" in row[1] for row in indexes):
    graph.query("CALL db.idx.fulltext.createNodeIndex('Passage', 'text')")
if not any(row[0] == "Passage" and "lexical_vector" in row[1] for row in indexes):
    graph.query("CREATE VECTOR INDEX FOR (p:Passage) ON (p.lexical_vector) OPTIONS {dimension:96, similarityFunction:'cosine'}")
print("Corpus fictif ingéré : acteurs, grilles versionnées, sources, index textuel et vectoriel lexical local.")
