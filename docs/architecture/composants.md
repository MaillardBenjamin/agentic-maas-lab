# Les composants et leur rôle

[Retour au dossier d’architecture](README.md)

Les noms entre parenthèses correspondent aux services de [Docker Compose](../../compose.yaml). Plusieurs services partagent le même code et ne constituent pas tous des applications métier indépendantes.

## Interfaces et cœur métier

| Composant | Responsabilité et limites |
|---|---|
| **React / TypeScript** (`web`) | Affiche le parcours voyageur, la borne simulée, l’agence/SAV et la console. Recueille les confirmations. Ne constitue pas l’autorité sur les prix ni les paiements. |
| **FastAPI / Python** (`api`) | Expose les API métier, vérifie les accès, calcule les devis, conserve les commandes, traite les paiements de test, événements et actions partenaires. C’est une application modulaire ; les domaines métier ne sont pas tous déployés comme des microservices séparés. |
| **PostgreSQL** (`postgres`) | Conserve les commandes, devis, paiements de test, audits, événements, stocks et opérations partenaires. Les enregistrements métier utilisent actuellement une table générique ; ce n’est pas encore un modèle comptable de production. Temporal utilise également PostgreSQL pour son historique, dans sa base dédiée. |
| **OPA — Open Policy Agent** (`opa`) | Évalue des règles d’habilitation exécutables. Aujourd’hui, il contrôle les régularisations SAV : rôle, organisation et montant. Il ne contrôle pas encore toutes les autorisations du système ; d’autres vérifications sont codées dans les services. |

Sources principales : [API](../../services/api/maas/api.py), [règles tarifaires](../../services/api/maas/domain.py), [politiques SAV](../../policies/maas.rego).

## Agents, modèles et outils

**Agno** construit les agents et les relie aux modèles et outils. **AgentOS** les expose comme services, notamment via A2A. Le planificateur AgentOS est désactivé : les opérations durables relèvent de Temporal.

| Agent | Rôle dans le POC |
|---|---|
| Accueil conversationnel | Comprend la demande et délègue les questions tarifaires. |
| Tarifs | Consulte catalogue et sources pour expliquer les montants. |
| Assistance SAV | Consulte le dossier, les règles et le relevé ; ne rembourse pas directement. |
| Commissions | Explique les calculs fournis par les services. |
| Coordination MaaS | Délègue une opération partenaire déjà confirmée. |
| Vélo et parking | Sur le runtime partenaire séparé, consultent la disponibilité et appellent l’outil de l’action autorisée. Les partenaires restent fictifs. |

Les cinq premiers sont exposés par `agents`, les deux derniers par `partners`. Leur séparation démontre une coopération distante entre services ; elle ne représente pas sept organisations indépendantes.

Le fournisseur de modèle peut être **Ollama**, avec une inférence sur le Mac, ou **OpenAI**, via une API cloud. Les tests de protocole peuvent employer un double de modèle déterministe qui ne produit aucune inférence IA. Les identités et droits métier ne sont pas fournis librement par le modèle.

**FastMCP** expose deux familles d’outils :

- `mcp` : quatre lectures — catalogue, sources, commande et relevé — avec le jeton utilisateur délégué.
- `partner-mcp` : disponibilité et action pour chacun des partenaires vélo et parking. Les actions sont limitées par une autorisation signée de courte durée, préparée après confirmation dans l’interface.

Les outils appellent les API métier ; ils ne donnent pas aux modèles un accès direct aux bases. Sources : [agents et AgentOS](../../services/agents/main.py), [MCP de lecture](../../services/agents/mcp_server.py), [MCP partenaire](../../services/agents/partner_mcp_server.py).

## Recherche et connaissance

**FalkorDB** (`falkor`) stocke le graphe des acteurs, grilles, produits et sources documentaires. Il aide à retrouver les règles applicables et leurs liens.

Le POC combine recherche textuelle, vecteurs lexicaux locaux de 96 dimensions et traversée du graphe. Les vecteurs représentent des mots ; ils ne sont pas des embeddings sémantiques OpenAI. Ce mécanisme sert de base à une démarche GraphRAG : retrouver des sources reliées avant de produire une réponse. Il ne vérifie pas à lui seul toutes les affirmations d’un agent.

Le tarif est calculé à partir du [catalogue structuré](../../fixtures/catalog.json), projeté dans le graphe par le chargement initial. Sources : [recherche](../../services/api/maas/knowledge.py), [chargement](../../scripts/seed.py).

## Orchestration, banque et carte

**Temporal** est le moteur d’orchestration durable : il coordonne les étapes d’un processus et conserve leur progression pour permettre une reprise après interruption. Le service `temporal` conserve l’historique et distribue les tâches ; `temporal-ui` permet de consulter leur exécution. Le **worker** (`worker`) exécute le code des workflows et les activités, notamment les appels à l’API ou à un adaptateur. Voir [l’explication des concepts et de la reprise](temporal.md). Les workflows de cette version sont :

| Workflow | Fonction |
|---|---|
| `PurchaseAndIssue` | Attendre le paiement, éventuellement une reprise manuelle, puis délivrer le droit sur carte simulée. |
| `BankPaymentWatch` | Sur la borne, contrôler le statut Bridge pendant une fenêtre de 15 minutes, avec reprises après interruption. |
| `PartnerInteraction` | Déléguer une opération vélo/parking confirmée et conserver son résultat ou son échec. |
| `ProofAnchoring` | Réessayer l’ancrage d’un lot indépendamment du parcours de validation. |

**Bridge** est un service externe de paiement. L’intégration actuelle utilise sa sandbox et Demo Bank pour un virement ponctuel. Le QR de la borne contient le lien public Bridge, pas une clé ni le jeton utilisateur. Le serveur vérifie le règlement ; le retour du navigateur ne constitue jamais la confirmation bancaire. Aucun paiement CB acquis par Bridge, remboursement bancaire ou prélèvement mensuel n’est implémenté.

Le service **simulateur** (`simulator`) conserve dans SQLite l’identité de l’opération de chargement. Il permet notamment de provoquer une réponse perdue après écriture. L’adaptateur Java **Keyple** (`keyple`) utilise réellement les SDK Keyple/Keypop pour sélectionner, écrire et relire une carte Calypso stub. Cela ne vaut ni intégration matérielle ni certification.

Sources : [workflows](../../services/worker/main.py), [connecteur Bridge](../../services/api/maas/bridge.py), [simulateur](../../services/api/maas/simulator.py), [adaptateur Java](../../services/keyple/src/main/java/org/alize/demo/CardServer.java).

## Événements, preuves et visibilité

**CloudEvents** est un format d’enveloppe, pas un serveur de messages déployé dans cette pile. Les événements passent par les API et les transactions métier. Leur source, leur type et leur identité sont contrôlés ; une répétition ne doit pas produire un nouvel effet. Les sources X/Y de validation sont des fabricants fictifs.

**Anvil** (`anvil`, profil `proofs`) fait fonctionner la **blockchain Ethereum locale de développement** du POC. Une blockchain est un registre de transactions regroupées en blocs reliés cryptographiquement. Voir [le mécanisme, les bénéfices et les limites](blockchain-et-anvil.md). Le contrat Solidity **ProofRegistry** conserve l’empreinte SHA-256 d’un manifeste de lot. Le manifeste est conservé hors chaîne et signé en **Ed25519** par une clé du POC. Cette signature est distincte de la transaction Ethereum et ne signe pas un contrat d’abonnement pour un voyageur. Une date de bloc est un horodatage de la chaîne locale, pas un horodatage qualifié indépendant.

**OpenTelemetry** instrumente l’API et les workflows/activités Temporal. Le collecteur `otel` transmet les traces à **Jaeger** (`jaeger`) pour les consulter. La propagation complète à travers les agents reste à compléter ; la console ne constitue pas une preuve de traçage exhaustif de tous les appels. Les corps des demandes et secrets n’ont pas vocation à être exportés.

Sources : [événements](../../services/api/maas/events.py), [preuves](../../services/api/maas/proofs.py), [contrat](../../contracts/proofs/src/ProofRegistry.sol), [instrumentation](../../services/api/maas/observability.py).

## Laboratoire et déploiement

**Harness² de Google Research** (`harness2`, profil `lab`) exécute des expériences séparées sur deux rapprochements comptables fictifs, avec des éditeurs déterministes. Il ne décide d’aucune vente et ne démontre pas encore une amélioration d’agent IA. [Adaptation locale](../../lab/harness2/run.py).

**Docker Compose** assemble les services et volumes sur le Mac. Les profils `tests`, `proofs` et `lab` activent des services supplémentaires. Les ports exposés sont liés à `127.0.0.1`. Les identités de démonstration et secrets par défaut imposent de garder cette configuration locale ; ce dossier ne décrit pas un déploiement sécurisé en production.
