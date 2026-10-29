# Sélection des agents, achats et preuves — 29 octobre 2026

## Sélection avant les appels

L’API qualifie la demande avec une politique explicite (`maas/routing.py`) : intention, coordinateur, services concernés. Ce plan est signé avec le contexte de session. L’Accueil utilise `delegate_request`, sans choisir librement le coordinateur. Le runtime refuse aussi un appel direct à un coordinateur incompatible.

Avant tout appel fournisseur, le code croise la sélection avec les compétences publiées dans `fixtures/catalog.json`, les organisations autorisées et, pour SAV/Commissions, les fournisseurs de la commande sélectionnée. Un fournisseur ajouté par le modèle hors du plan fait échouer la consultation avant le premier appel. Une liste vide reprend uniquement la sélection validée du plan ; elle n’élargit jamais la demande à tous les fournisseurs.

Exemples vérifiés :

| Demande | Parcours autorisé |
|---|---|
| Tarif du parking | Accueil → Tarifs → Parking |
| Commission Parking sur une commande transport/parking/vélo | Accueil → Commissions → Parking |
| Répartition par fournisseur de ma commande | Accueil → Commissions → fournisseurs de cette commande |
| Quelle commission ? | Précision demandée avant toute inférence ou délégation |
| Mes achats | Accueil → Achats → MCP `list_purchases` |

Les lectures indépendantes sont parallélisées **après** cette validation, avec au plus trois fournisseurs en cours par consultation. Les contrôles portent sur une qualification déterministe des expressions métier prises en charge. Une formulation non reconnue demande une précision ; élargir le vocabulaire doit s’accompagner de cas de non-régression. Cette politique ne constitue pas une compréhension universelle du langage naturel.

## Historique accessible aux agents

L’agent `history` dispose de `list_purchases`, `read_order` (via MCP `read_purchase`) et `verify_purchase_proofs`. Les API dédiées exigent une session et un contexte de consultation signé :

- Voyageur : ses propres commandes seulement.
- Conseiller : le voyageur sélectionné et autorisé dans son organisation.
- Pagination bornée, total et indication de page suivante.
- Commande en attente de paiement distinguée d’un achat payé.

Une incapacité d’outil ne doit plus être présentée comme un refus d’accès. Les tests vérifient la lecture Léa/conseiller et le refus Alex → Léa avant consultation de la chaîne.

## Preuves du cycle de vie

La transaction métier conserve une preuve en attente dans PostgreSQL lors de la création de commande, de la confirmation de paiement, de la délivrance, de chaque usage accepté et de chaque régularisation. La répétition d’une même source ne crée pas de preuve supplémentaire. Le worker distribue ensuite les preuves à `ProofAnchoring`, avec reprises Temporal. Ni signature ni appel blockchain n’est requis dans la transaction de vente.

Le manifeste de version 2 contient une référence opaque de commande, le type d’étape, la date d’enregistrement et l’empreinte du contenu métier. Les détails d’achat, identités et instantanés restent hors chaîne. `ProofRegistry` conserve l’empreinte du manifeste et sa version.

`verify_purchase_proofs` compare l’instantané au contenu métier actuel, vérifie la signature et relit le contrat de l’instance locale active. Il ne se fie jamais à un ancien `verified: true`. Une couverture incomplète, une source altérée, une chaîne inaccessible ou un changement de déploiement restent visibles. Chaque usage et chaque régularisation doivent être couverts pour déclarer le dossier entièrement vérifié.

Les commandes antérieures restent consultables. Elles portent `not_available` lorsqu’aucune preuve de ce type n’existe : aucun ancrage rétroactif n’est présenté comme une preuve contemporaine de l’achat. La chaîne atteste l’intégrité du contenu enregistré ; la confirmation d’encaissement relève du service métier et du connecteur bancaire.

## Validation locale

- Tests API, droits, sélection, atomicité et couverture des preuves : `tests/test_routing.py`, `tests/test_purchase_history.py` et suite API.
- Tests du runtime : périmètre Parking malgré une liste vide, refus d’un fournisseur ajouté avant appel, vérification obligatoire des preuves, concurrence et annulation.
- A2A/MCP réels avec modèle de test explicitement simulé : `scripts/history_routing_smoke.py` et `scripts/cooperation_smoke.py fixture`.
- Essai avec Ollama : commission Parking → `clearing, parking` ; historique → `history`, outil `list_purchases`, sans fournisseur.
- Cycle de test local : achat, paiement simulé, délivrance sur carte stub, deux usages et régularisation ; six preuves vérifiées sur Anvil, couvrant les cinq types d’étape.

Les fichiers `data/cooperation-evidence/history-routing-{fixture,live}.json` conservent les résultats locaux détaillés. Le script accepte `--proof-order <référence>` pour vérifier le cycle complet d’une commande de test, et `--live` pour employer le modèle configuré.
