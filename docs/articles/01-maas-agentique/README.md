# Épisode 1 — Dossier éditorial

**Destination :** blog de Benjamin Maillard, puis annonce LinkedIn.
**Statut :** textes préparés pour relecture ; intégration au blog et diffusion LinkedIn à effectuer après validation éditoriale.

## Livrables

- [Article complet](article.md) : parcours de Léa, architecture expliquée, résultats et projection vers les prochains épisodes.
- [Post LinkedIn](linkedin.md) : annonce à diffuser après mise en ligne de l’article.
- [Métadonnées](metadata.json) : titre, extrait, catégorie, slug et temps de lecture estimé.

## Le fil éditorial

L’article établit un socle observable pour une série consacrée à la souplesse de l’architecture. Il part du parcours actuel, explique la répartition des responsabilités et projette les évolutions : services locaux, connecteur partenaire, abonnement étudiant, portefeuille territorial et scénarios de reprise.

La finalité est un parcours cohérent pour l’habitant, avec des droits et échanges explicites entre vendeurs, opérateurs et financeurs. La réutilisation des composants sera évaluée dans les épisodes suivants par les adaptations réalisées et les essais.

Le cadrage POC est donné une seule fois au début de chacun des deux textes. Les résultats observés sont distingués des évolutions prévues dans le récit.

## Intégration dans benjamin-maillard.fr

La structure locale du blog a été consultée en lecture : les articles français sont déclarés dans `Front/src/cvData.ts`, avec les champs `title`, `excerpt`, `date`, `category`, `readTime`, `slug`, `ogImage` et `content`. Le rendu prend en charge les blocs Mermaid et les images HTML utilisés dans l’article.

Lors de l’intégration :

1. Importer le contenu Markdown comme texte brut avec Vite, ou l’insérer dans le champ `content` selon la convention retenue dans le site.
2. Reprendre les métadonnées et renseigner la date effective de publication. Le champ `date` est laissé à `null` dans ce dossier pour éviter de confondre préparation et publication.
3. Vérifier le rendu des deux schémas, des deux captures, des liens et de l’aperçu de partage, puis construire le site.
4. Mettre en ligne l’article et vérifier son URL avant de diffuser le post LinkedIn.

**URL prévue :** `https://benjamin-maillard.fr/?article=maas-agentique-billettique-interoperable`. Elle suit le routage actuel du blog. Le post utilise cette URL prévue : elle devra correspondre à l’article effectivement intégré avant diffusion.

Les images sont déjà disponibles dans le dépôt GitHub ; leurs URL brutes sont utilisées dans le texte. Elles peuvent aussi être copiées dans les ressources publiques du site, en adaptant leurs chemins. Aucune modification du projet CV ni aucune publication externe n’a été effectuée pour préparer ces textes.

## Revue des affirmations

| Affirmation | Appui vérifié |
|---|---|
| Paiement de 12 €, commande délivrée, un paiement, un chargement et relecture vérifiée | [État enregistré](../../evidence-automate-qr-2026-10-25.json) et [rapport QR](../../automate-qr-2026-10-25.md). |
| Redémarrage du worker pendant l’attente bancaire et reprise | [Rapport QR](../../automate-qr-2026-10-25.md). |
| Cycles partenaires A2A/MCP avec Ollama | [Rapport partenaires](../../partenaires-a2a-2026-10-24.md) et [résultats Ollama](../../evidence-partenaires-ollama-2026-10-24.json). |
| Trois demandes pour deux vélos : deux réservations et un refus | [Résultats de concurrence](../../evidence-partenaires-concurrence-2026-10-24.json), avec modèle déterministe de test. |
| 76 tests Python et 12 tests d’état du frontal | Résultats documentés au 25 octobre dans le [rapport QR](../../automate-qr-2026-10-25.md). |
| Rôles des agents, règles, Temporal, OPA et graphe | [Dossier d’architecture](../../architecture/README.md) et sources de code qui y sont référencées. |
| Services locaux, abonnement annuel et portefeuille territorial | [Plan de la série](../../serie-articles-souplesse-maas-agentique.md), présentés comme épisodes à venir. |

La revue porte sur les textes et les pièces déjà conservées dans le dépôt ; les essais du logiciel n’ont pas été relancés pour cette préparation éditoriale. Les noms, montants et scénarios sont ceux du démonstrateur. Aucun gain chiffré de coût, délai ou productivité n’est avancé.
