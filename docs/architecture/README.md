# Comprendre l’architecture d’Alizé Lab

**Dossier d’architecture de haut niveau — 25 octobre 2026**

Ce dossier s’adresse aux lecteurs qui découvrent le projet et ses technologies. Il présente les choix de conception et les relie aux parcours et résultats documentés.

## Le problème traité

Un voyageur achète une offre auprès d’un vendeur, paie, reçoit un droit de transport et utilise des services partenaires. Le vendeur, les opérateurs et l’agence de service après-vente doivent retrouver des montants et des états cohérents, même si une opération est interrompue.

**MaaS** signifie *Mobility as a Service* : réunir plusieurs services de mobilité dans un même parcours. Ici, le POC se concentre sur la **billettique** — offres, vente, paiement, délivrance de droits, usages et SAV. Le calcul d’itinéraire et l’information voyageurs sont hors périmètre.

Le qualificatif **agentique** désigne l’intervention d’agents IA spécialisés, capables de consulter des outils et de déléguer une demande à un autre agent. Les services métier calculent les prix et autorisent les opérations ; les agents accompagnent et coordonnent le parcours.

## Lecture du dossier

| Document | Ce qu’il explique |
|---|---|
| [Principes et bénéfices](principes-et-benefices.md) | Pourquoi séparer compréhension, calcul, exécution et reprise ; bénéfices attendus et contreparties. |
| [Composants et responsabilités](composants.md) | Le rôle de chaque logiciel et les données qu’il porte. |
| [Parcours et échanges](parcours.md) | Comment une demande circule entre interface, agents, outils, paiement et délivrance. |
| [Temporal : coordonner et reprendre](temporal.md) | Les workflows, activités, workers, signaux, délais et reprises, à partir du paiement du POC. |
| [Blockchain et Anvil : conserver des preuves](blockchain-et-anvil.md) | Le mécanisme d’ancrage et ses bénéfices pour la coopération entre partenaires. |
| [Glossaire](glossaire.md) | A2A, MCP, API, GraphRAG, workflow, idempotence, blockchain et autres notions. |

Pour une première lecture : commencer par la vue ci-dessous, puis les principes. Les détails de déploiement restent dans le [README du projet](../../README.md).

## La vue d’ensemble

Ce schéma regroupe les fonctions pour rester lisible. Les blocs regroupent les responsabilités ; leur déploiement est détaillé dans les composants. Les flèches représentent les échanges principaux, pas tous les appels techniques.

```mermaid
flowchart TB
    UI["Interfaces<br/>Voyageur, borne, agence, console"] --> API["Services métier / API<br/>Tarifs, commandes, droits, SAV"]
    API <-->|"A2A : demandes<br/>MCP : outils via API"| IA["Agents IA Agno / AgentOS<br/>MaaS et partenaires vélo / parking"]
    API --> DATA[("Données<br/>PostgreSQL : états et audit<br/>FalkorDB : offres et sources")]
    API --> OPA["OPA<br/>Autorisations SAV"]
    API --> T["Temporal et worker<br/>Orchestration durable et reprises"]
    T --> EXT["Intégrations via API / adaptateurs<br/>Bridge sandbox<br/>Keyple sur carte simulée"]
    API -->|"Lien et statut bancaire"| EXT
    T --> PROOF["Preuves via API interne<br/>Blockchain Ethereum locale : Anvil"]
    API -.-> OBS["OpenTelemetry / Jaeger<br/>Traces techniques"]
    T -.-> OBS
```

**A2A relie des agents ; MCP relie un agent à des outils ; les API métier gardent la responsabilité des effets exécutés.** Temporal mémorise et fait progresser les opérations qui doivent survivre à une interruption.

Les appels partenaires du schéma exécutent une action confirmée dans l’interface. Les outils d’action sont liés à cette opération. Les autres outils IA du POC sont en lecture seule.

## Les capacités à explorer

| Parcours | Composants mobilisés |
|---|---|
| Comprendre une offre | Agents Agno, délégation A2A, outils MCP et recherche FalkorDB. |
| Acheter et délivrer | Services métier, paiement Bridge sandbox, Temporal et SDK Keyple sur carte stub. |
| Utiliser un service partenaire | Agents vélo/parking, outils MCP, stock et réservations persistés. |
| Traiter une validation et un dossier SAV | CloudEvents, PostgreSQL, habilitations OPA et journal des opérations. |
| Conserver et consulter des preuves | Manifestes signés, ancrage blockchain Anvil et traces OpenTelemetry/Jaeger. |
| Éprouver des variantes | Modèles Ollama ou OpenAI, doubles déterministes de test et laboratoire Harness². |

Les extensions vers les services locaux, l’abonnement étudiant et les crédits territoriaux sont présentées dans la [série d’articles](../serie-articles-souplesse-maas-agentique.md).

## Où vérifier les affirmations

- [Parcours partenaires et essais A2A/MCP](../partenaires-a2a-2026-10-24.md).
- [Paiement QR Bridge, reprise et limites](../automate-qr-2026-10-25.md).
- [Essais des fournisseurs IA](../tests-ia-locale-et-acces-2026-10-24.md).
- [Première validation du socle](../validation-2026-10-24.md), à lire avec les rapports complémentaires plus récents.
- [Série d’articles et futurs POC](../serie-articles-souplesse-maas-agentique.md).

Le [plan d’implémentation cible](../../plan-implementation-poc.md) et le [plan d’article initial](../../plan-maas-agentique.md) couvrent un périmètre plus large que le code actuel. La série d’articles suit le passage de ces objectifs aux réalisations successives.
