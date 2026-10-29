# Les composants et leur rôle

[Retour au dossier d’architecture](README.md)

Les noms entre parenthèses correspondent aux services de [Docker Compose](../../compose.yaml). Plusieurs services partagent le même code, organisé en modules métier.

## Interfaces et cœur métier

| Composant | Responsabilité |
|---|---|
| **React / TypeScript** (`web`) | Affiche le parcours voyageur, la borne simulée, l’agence/SAV et la console. Recueille les confirmations. Affiche les prix et états confirmés par les services métier. |
| **FastAPI / Python** (`api`) | Expose les API métier, vérifie les accès, calcule les devis, conserve les commandes, traite les paiements de test, événements et actions partenaires. Les domaines métier sont regroupés dans une application modulaire. |
| **PostgreSQL** (`postgres`) | Conserve les commandes, devis, paiements de test, audits, événements, stocks et opérations partenaires. Les enregistrements métier utilisent une table générique. Temporal utilise également PostgreSQL pour son historique, dans sa base dédiée. |
| **OPA — Open Policy Agent** (`opa`) | Évalue des règles d’habilitation exécutables. Aujourd’hui, il contrôle les régularisations SAV : rôle, organisation et montant. Les autres contrôles d’accès sont réalisés dans les services métier. |

Sources principales : [API](../../services/api/maas/api.py), [règles tarifaires](../../services/api/maas/domain.py), [politiques SAV](../../policies/maas.rego).

Le module [ABT](../../services/api/maas/abt.py) conserve les comptes, contrats, usages et factures simulées dans PostgreSQL. Les achats classiques d’un voyageur connu sont rattachés au même compte sans changement de support ; les nouveaux droits ABT sont contrôlés côté serveur, sans chargement Keyple. Le worker appelle périodiquement la facturation et le rattrapage idempotent. Ce traitement n’est pas un workflow Temporal d’abonnement. Voir [les règles du compte mobilité](../abt-transport-2026-10-29.md).

## Agents, modèles et outils

**Agno** construit les agents et les relie aux modèles et outils. **AgentOS** les expose comme services, notamment via A2A. Le planificateur AgentOS est désactivé : les opérations durables relèvent de Temporal.

| Agent | Rôle dans le POC |
|---|---|
| Accueil conversationnel | Délègue au coordinateur autorisé par le plan signé : Tarifs, SAV, Commissions, MaaS ou Achats. |
| Achats et preuves | Recherche les commandes du voyageur autorisé et vérifie les preuves avec les services métier et la chaîne active. |
| Coordination Tarifs | Consulte via A2A les organisations concernées ; rassemble les tarifs sourcés. |
| Coordination SAV | Consulte le périmètre du dossier propre à chaque fournisseur et prépare la réponse du conseiller. |
| Coordination Commissions | Consulte les contrats et parts des fournisseurs ; explique le relevé déterministe. |
| Coordination commerciale MaaS | Consulte les disponibilités et prépare un devis à examiner avant confirmation. |
| Transport, Parking et Vélo | Représentent chacun une organisation ; consultent leurs offres, sources, stocks et lignes du dossier sélectionné. |
| Exécution MaaS et opérations Vélo/Parking | Points d’entrée distincts, accessibles uniquement avec une action confirmée et une autorisation signée. |

Les coordinateurs sont exposés par `agents`, les agents d’organisation par `partners`. Les compétences sont regroupées dans deux runtimes ; leur identité et leurs droits restent distincts. Le registre publié dans `fixtures/catalog.json` relie fournisseur, organisation, produits, agent et graphe documentaire. `org` désigne le distributeur MaaS, `provider_org` le fournisseur : ces identités ne sont pas interchangeables.

La sélection croise intention, services et compétences déclarées avant tout appel. Une liste vide du modèle reprend le plan validé sans élargissement. Un fournisseur hors plan ou un coordinateur incompatible est refusé. Voir [la politique et les validations](../routage-achats-preuves-2026-10-29.md).

Les lectures indépendantes de plusieurs fournisseurs s’exécutent en parallèle, avec une limite de trois appels A2A fournisseurs par consultation. Les lectures de relevé ou de règles MaaS indépendantes démarrent dans le même groupe. La synthèse attend la fin de toutes les lectures ; leur ordre de présentation reste stable et aucun succès partiel n’est présenté comme complet. Les autorisations et le suivi sont transmis à chaque tâche. Les étapes métier dépendantes conservent leur ordre.

Le fournisseur de modèle peut être **Ollama**, avec une inférence sur le Mac, ou **OpenAI**, via une API cloud. Les tests de protocole peuvent employer un double de modèle déterministe pour isoler les tests de protocole. Les identités et droits métier sont vérifiés par les services.

**FastMCP** expose des outils aux droits distincts :

- `mcp` : catalogue publié, règles MaaS, commande, relevé et préparation d’un devis sans achat. Le voyageur et le vendeur de ce devis viennent du contexte de session signé.
- `partner-mcp` : `read_provider_context` consulte uniquement l’organisation désignée par une délégation de lecture signée : offres, sources GraphRAG, disponibilité observée, contrats et, si sélectionné, lignes de commande, usages et relevé de ce fournisseur.
- Les quatre outils d’exécution vélo/parking restent liés à une opération confirmée. Un jeton de consultation ne peut pas les autoriser.

Une consultation de prix ou de disponibilité ne nécessite aucune commande existante. Pour une action d’usage, le droit délivré reste obligatoire. Le devis ne garantit pas une réservation. Les API métier contrôlent les accès ; les calculs et reçus persistent indépendamment du texte produit par le modèle. Sources : [agents](../../services/agents/main.py), [consultation fournisseur](../../services/api/maas/providers.py), [délégations](../../services/api/maas/organizations.py).

## Recherche et connaissance

**FalkorDB** (`falkor`) sépare les corpus `maas_demo`, `transport_demo`, `parking_demo` et `mobilites_demo` (vélo). Le serveur choisit le graphe depuis le fournisseur autorisé ; le modèle ne choisit pas librement un graphe. Chaque corpus fournisseur contient ses acteurs, grilles, produits et sources documentaires. Il aide à retrouver les règles applicables et leurs liens.

Le POC combine recherche textuelle, vecteurs lexicaux locaux de 96 dimensions et traversée du graphe. Les vecteurs représentent les mots présents dans les sources. Ce mécanisme sert de base à une démarche GraphRAG : retrouver des sources reliées avant de produire une réponse. Les références retrouvées permettent de relier l’explication aux sources.

Chaque ligne de devis conserve son fournisseur et un instantané du contrat de distribution. Le relevé ventile prix net, régularisation, commission et part fournisseur ; les anciennes commandes conservent leurs conditions. Une régularisation peut cibler un produit ; sinon elle est ventilée au prorata des montants restants, avec conservation des centimes.

Le tarif est calculé à partir du [catalogue structuré](../../fixtures/catalog.json), projeté dans le graphe par le chargement initial. Sources : [recherche](../../services/api/maas/knowledge.py), [chargement](../../scripts/seed.py).

## Orchestration, banque et carte

**Temporal** est le moteur d’orchestration durable : il coordonne les étapes d’un processus et conserve leur progression pour permettre une reprise après interruption. Le service `temporal` conserve l’historique et distribue les tâches ; `temporal-ui` permet de consulter leur exécution. Le **worker** (`worker`) exécute le code des workflows et les activités, notamment les appels à l’API ou à un adaptateur. Voir [l’explication des concepts et de la reprise](temporal.md). Les workflows de cette version sont :

| Workflow | Fonction |
|---|---|
| `PurchaseAndIssue` | Attendre le paiement, éventuellement une reprise manuelle, puis délivrer le droit sur carte simulée. |
| `BankPaymentWatch` | Sur la borne, contrôler le statut Bridge pendant une fenêtre de 15 minutes, avec reprises après interruption. |
| `PartnerInteraction` | Déléguer une opération vélo/parking confirmée et conserver son résultat ou son échec. |
| `ProofAnchoring` | Réessayer l’ancrage d’un lot indépendamment du parcours de validation. |

**Bridge** est un service externe de paiement. L’intégration actuelle utilise sa sandbox et Demo Bank pour un virement ponctuel. Le QR de la borne contient le lien public Bridge, pas une clé ni le jeton utilisateur. Le serveur vérifie le règlement ; le retour du navigateur ne constitue jamais la confirmation bancaire.

Le service **simulateur** (`simulator`) conserve dans SQLite l’identité de l’opération de chargement. Il permet notamment de provoquer une réponse perdue après écriture. L’adaptateur Java **Keyple** (`keyple`) utilise réellement les SDK Keyple/Keypop pour sélectionner, écrire et relire une carte Calypso stub.

Sources : [workflows](../../services/worker/main.py), [connecteur Bridge](../../services/api/maas/bridge.py), [simulateur](../../services/api/maas/simulator.py), [adaptateur Java](../../services/keyple/src/main/java/org/alize/demo/CardServer.java).

## Événements, preuves et visibilité

**CloudEvents** définit l’enveloppe commune des événements. Les événements passent par les API et les transactions métier. Leur source, leur type et leur identité sont contrôlés ; une répétition ne doit pas produire un nouvel effet. Les sources X/Y de validation sont des fabricants fictifs.

**Anvil** (`anvil`, profil `proofs`) fait fonctionner la **blockchain Ethereum locale de développement** du POC. Une blockchain est un registre de transactions regroupées en blocs reliés cryptographiquement. Voir [le mécanisme et ses bénéfices](blockchain-et-anvil.md). Le contrat Solidity **ProofRegistry** conserve l’empreinte SHA-256 d’un manifeste de lot. Le manifeste est conservé hors chaîne et signé en **Ed25519** par une clé du POC. La signature authentifie le manifeste ; la transaction blockchain enregistre son empreinte. La date affichée provient du bloc local.

**OpenTelemetry** instrumente l’API et les workflows/activités Temporal. Le collecteur `otel` transmet les traces à **Jaeger** (`jaeger`) pour les consulter. La couverture actuelle relie l’API aux workflows et activités ; la propagation aux agents constitue une extension identifiée. Les corps des demandes et secrets n’ont pas vocation à être exportés.

Sources : [événements](../../services/api/maas/events.py), [preuves](../../services/api/maas/proofs.py), [contrat](../../contracts/proofs/src/ProofRegistry.sol), [instrumentation](../../services/api/maas/observability.py).

## Laboratoire et déploiement

**Harness² de Google Research** (`harness2`, profil `lab`) exécute des expériences séparées sur deux rapprochements comptables fictifs, avec des éditeurs déterministes. Ses expériences sont séparées du parcours de vente. [Adaptation locale](../../lab/harness2/run.py).

**Docker Compose** assemble les services et volumes sur le Mac. Les profils `tests`, `proofs` et `lab` activent des services supplémentaires. Les ports exposés sont liés à `127.0.0.1`. Les paramètres d’accès local sont détaillés dans le [guide de démarrage](../../README.md#démarrer).
