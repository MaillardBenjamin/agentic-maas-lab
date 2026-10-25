# Principes, bénéfices et compromis

[Retour au dossier d’architecture](README.md)

## 1. Séparer compréhension et décision métier

Un agent IA comprend une question, recherche des éléments et propose une explication. Il peut choisir un outil autorisé ou déléguer à un agent spécialisé. Un modèle de langage produit des réponses variables : il ne constitue pas une source fiable pour tenir un solde ou calculer une commission.

Le prix, les réductions, les arrondis, les transitions d’état et les droits sont donc contrôlés par du code métier déterministe. Pour les mêmes données et règles, ce code doit produire le même résultat. L’interface recueille les confirmations nécessaires avant exécution.

**Bénéfice :** pouvoir faire évoluer le modèle ou les consignes des agents sans lui transférer les garanties financières et métier. **Limite :** une réponse IA peut encore être inexacte ; le résultat du service métier reste la référence.

## 2. Distinguer trois formes de coordination

| Mécanisme | Question à laquelle il répond | Exemple |
|---|---|---|
| **A2A — Agent-to-Agent** | À quel agent spécialisé déléguer cette demande ? | L’accueil demande une explication à l’agent tarifaire. |
| **MCP — Model Context Protocol** | Quel outil peut être appelé, avec quelles entrées et quel résultat ? | L’agent tarifaire consulte le catalogue par un outil de lecture. |
| **Temporal — workflow durable** | Où en est l’opération et comment reprendre après une interruption ? | Attendre la confirmation bancaire puis reprendre la délivrance. |

Le [chapitre Temporal](temporal.md) définit workflow, activité, worker, file de tâches, signal, minuterie, historique et reprise.

Ces mécanismes se complètent. Un échange A2A ou un appel MCP ne garantit pas à lui seul une opération durable, une autorisation ou l’absence de doublon.

## 3. Partager le socle entre les canaux

Le site, l’affichage responsive sur mobile, la borne simulée et l’agence appellent les mêmes services métier. La présentation change selon le contexte : une borne gère notamment une session courte et un retour à l’accueil, tandis qu’un espace voyageur expose l’historique accessible à cette identité.

**Bénéfice :** ajouter un point de vente sans recopier les règles tarifaires. **Compromis :** les droits, les moyens de paiement et la délivrance restent à adapter à chaque canal. Le projet ne fournit pas aujourd’hui une application mobile native ni un automate matériel certifié.

## 4. Encadrer les effets et les reprises

L’API contrôle le voyageur et son organisation. OPA décide des habilitations SAV selon une politique explicite. Une opération partenaire reçoit une autorisation temporaire liée à son action, sa commande et son partenaire ; le modèle ne peut pas changer ces paramètres.

Temporal conserve les attentes et les reprises. Une clé d’idempotence identifie une opération pour qu’un nouvel essai retrouve son effet précédent plutôt que de le répéter. Les écritures et contraintes de base complètent cette protection.

**Bénéfice :** rendre les interruptions observables et récupérables. **Limite :** une réponse bancaire incertaine peut nécessiter un rapprochement humain. Rejouer une activité ne suffit pas à garantir un effet unique : le service appelé doit aussi gérer les répétitions.

## 5. Affecter un rôle clair à chaque stockage

PostgreSQL conserve les états métier, paiements de test, stocks partenaires et audits. FalkorDB relie acteurs, grilles, produits et passages documentaires pour la recherche et l’explication. Le simulateur carte possède un état SQLite distinct pour tester une réponse de délivrance perdue.

Le catalogue structuré du dépôt alimente les calculs et sa projection dans le graphe. Les devis conservent une version et les conditions retenues. Le graphe ne remplace pas le moteur tarifaire.

**Bénéfice :** retrouver la source d’une explication sans rendre le calcul dépendant d’un texte généré. **Compromis :** la cohérence entre catalogue et projection doit être maintenue ; l’outil de chargement est nécessaire après une évolution du catalogue.

## 6. Utiliser les événements et les preuves hors du chemin de validation

Une fin de location ou une validation est un événement. CloudEvents fournit une enveloppe commune ; le contenu métier et les règles d’acceptation restent définis par le projet. Les doublons et contradictions sont contrôlés par le service.

Un lot d’événements peut ensuite être résumé dans un manifeste signé Ed25519, dont l’empreinte est ancrée sur la blockchain Ethereum locale **Anvil**, par Temporal. L’ancrage ne conditionne pas l’acceptation d’une validation.

**Bénéfice :** disposer d’une référence pour détecter l’altération d’un lot. Dans une architecture cible partagée entre opérateurs indépendants, un registre commun pourrait aussi faciliter la comparaison de leurs preuves et les rapprochements. Le [chapitre blockchain](blockchain-et-anvil.md) distingue ces bénéfices attendus de ce que démontre Anvil local. **Limite :** cela ne prouve ni la réalité d’un passage ni l’identité d’un voyageur. Une chaîne locale réinitialisable n’offre pas les garanties d’un registre gouverné par plusieurs acteurs indépendants.

## Ce que la souplesse et l’agilité apporteraient

| Évolution | Socle que l’on cherche à réutiliser | Travail qui resterait nécessaire |
|---|---|---|
| Ajouter un service local : théâtre, piscine, bibliothèque… | Catalogue, droits, suivi et, si le service est payant, vente, devis, paiement et commissions. | Offre, règles d’accès, opérateur, délivrance et contrôle adapté au service. |
| Remplacer un partenaire | Interface de coopération et service métier. | Adaptateur, erreurs propres au fournisseur et tests de conformité. |
| Changer de modèle IA | Services et règles métier. | Compatibilité des outils, qualité des réponses, coûts et délais. |
| Ajouter un abonnement | Identités, commandes, paiement et Temporal. | Contrat, échéancier, autorisation récurrente et gestion des incidents. |
| Ajouter des crédits territoriaux | Catalogue, canaux, habilitations et traces. | Registre de crédits, financement, restrictions, dépenses et restitutions. |

La **souplesse** consiste ici à limiter la propagation d’un changement. L’**agilité** consiste à pouvoir développer et vérifier une évolution par étapes courtes, avec des services simulés lorsque le partenaire réel manque. Ce sont des bénéfices attendus à mesurer, pas des gains chiffrés déjà établis.

## Les contreparties à assumer

- **Plus de composants à exploiter :** davantage de configuration, de journaux, de versions et de modes de panne.
- **Des échanges supplémentaires :** A2A, outils et inférences peuvent augmenter la latence et le coût ; une fonction simple n’a pas systématiquement besoin d’un agent.
- **Une intégration à valider :** un protocole commun ne fournit pas automatiquement une sémantique métier commune ni la compatibilité de tous les partenaires.
- **Un démonstrateur à durcir :** identité de démo, schéma PostgreSQL générique, migrations et exploitation Linux à compléter ; aucune préparation à la production n’est revendiquée.
- **Des dépendances aux conditions distinctes :** le code original est MIT, mais les composants tiers conservent leurs licences, notamment FalkorDB serveur et Keyple. Voir les [notices](../../THIRD_PARTY_NOTICES.md).

La série d’articles évaluera ces choix par les adaptations réellement nécessaires, les tests, les traces et les pannes provoquées. Aucun diagramme ne suffit à démontrer la souplesse.
