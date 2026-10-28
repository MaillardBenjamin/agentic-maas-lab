import os
import json
from falkordb import FalkorDB
from maas.domain import CATALOG, digest
from maas.knowledge import lexical_vector

graphs = {"maas_demo": "maas", **{o["graph"]: o["id"] for o in CATALOG["organizations"]}}
for graph_name, provider in graphs.items():
    graph = FalkorDB(host=os.environ.get("FALKOR_HOST", "falkor")).select_graph(graph_name)
    # The old maas_demo contained all suppliers. Remove those published projections
    # before seeding the now-scoped corpus. These nodes are reproducible fixtures.
    if graph_name == "maas_demo":
        graph.query("MATCH (n) WHERE n:Passage OR n:Document OR n:Product OR n:TariffGrid OR n:Actor DETACH DELETE n")
    for source in (s for s in CATALOG["sources"] if s["provider"] == provider):
        graph.query("MERGE (d:Document {id:$id}) SET d.title=$title, d.version=$version, d.digest=$digest MERGE (p:Passage {id:$id}) SET p.text=$text, p.lexical_vector=vecf32($vector) MERGE (p)-[:FROM]->(d)", {**source, "version": CATALOG["version"], "digest": digest(source), "vector": lexical_vector(source["text"])})
    for product in (p for p in CATALOG["products"] if p["provider"] == provider):
        graph.query("MERGE (p:Product {id:$id}) SET p.name=$name, p.actor=$actor, p.price_cents=$price, p.version=$version MERGE (a:Actor {id:$actor}) MERGE (p)-[:SOLD_BY]->(a) MERGE (t:TariffGrid {id:$grid}) SET t.version=$version MERGE (a)-[:PUBLISHES]->(t) MERGE (t)-[:CONTAINS]->(p)", {"id": product["id"], "name": product["name"], "actor": product["actor"], "price": product["price_cents"], "version": CATALOG["version"], "grid": product["actor"] + ":" + CATALOG["version"]})
        graph.query("MATCH (p:Passage {id:$source}), (product:Product {id:$product}) MERGE (p)-[:APPLIES_TO]->(product)", {"source": product["source"], "product": product["id"]})
        grid = {"version": CATALOG["version"], "currency": CATALOG["currency"], "products": [product]}
        graph.query("MATCH (t:TariffGrid {id:$id}) SET t.rules_json=$rules, t.digest=$digest", {"id": product["actor"] + ":" + CATALOG["version"], "rules": json.dumps(grid, ensure_ascii=False), "digest": digest(grid)})
    indexes = graph.query("CALL db.indexes()").result_set
    if not any(row[0] == "Passage" and "text" in row[1] for row in indexes):
        graph.query("CALL db.idx.fulltext.createNodeIndex('Passage', 'text')")
    if not any(row[0] == "Passage" and "lexical_vector" in row[1] for row in indexes):
        graph.query("CREATE VECTOR INDEX FOR (p:Passage) ON (p.lexical_vector) OPTIONS {dimension:96, similarityFunction:'cosine'}")
print("Corpus fictif ingéré dans les graphes autorisés par organisation.")
