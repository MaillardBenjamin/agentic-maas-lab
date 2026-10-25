# MaaS agentique : démontrer la souplesse d’une architecture par son évolution

**Proposition de série d’articles — 25 octobre 2026**  
**Projet :** POC MaaS agentique et billettique interopérable  
**Statut :** proposition éditoriale et protocole de démonstration. Les épisodes décrivent les évolutions à réaliser au fil de la série.

## 1. L’intention de la série

L’objectif est de montrer comment une même plateforme évolue lorsque de nouveaux besoins apparaissent : ajouter un service, ouvrir un canal de vente, remplacer un fournisseur, introduire un abonnement ou reprendre une opération interrompue.

La souplesse et l’agilité constituent la thèse à éprouver. Chaque évolution permettra d’évaluer concrètement la réutilisation du socle et l’effort d’adaptation. Chaque épisode introduit une évolution concrète et montre ce qu’elle nécessite réellement : configuration, code, données, intégration, tests et exploitation.

La série suivra le même POC dans le temps. Les difficultés et les corrections d’architecture feront partie du récit. Les gains de délai, de coût ou de productivité seront documentés lorsqu’ils auront été mesurés.

**Question directrice : jusqu’où peut-on faire évoluer ce système en réutilisant son socle, et à quel prix ?**

## 2. Le point de départ

Le socle décrit dans les derniers travaux du projet comprend des interfaces Voyageur, Automate, Agence/SAV et Console ; un calcul tarifaire déterministe ; des agents Agno utilisant A2A et MCP ; FalkorDB ; Temporal ; OPA ; un paiement ponctuel Bridge sandbox ; une délivrance par le SDK Keyple sur carte simulée ; des partenaires vélo et parking fictifs avec état ; et des preuves ancrées sur Anvil local.

Un achat de 12 € par QR Bridge sandbox a été vérifié jusqu’au chargement et à la relecture de la carte simulée. Les comptes rendus existants constituent des éléments de départ, à compléter par une version reproductible et un nouvel état des lieux avant publication.

Références du dépôt :

- [Parcours de borne](automate-ihm-2026-10-24.md).
- [Paiement QR Bridge et vérifications](automate-qr-2026-10-25.md).
- [Preuve du parcours QR](evidence-automate-qr-2026-10-25.json).

Les épisodes suivants étendent ce socle aux services locaux, au contrat étudiant et au portefeuille territorial. Le fil conducteur reste la billettique et les droits d’accès.

## 3. Le plan de la série

### Article 1 — MaaS agentique : construire et expliquer le premier parcours

**Besoin :** acheter une offre comprenant transport, parking et accès au service vélo, puis délivrer les droits correspondants.

L’article présente le socle existant, ses frontières et un parcours reproductible. Il explique pourquoi les agents comprennent et coordonnent, tandis que les moteurs déterministes calculent et que les services métier autorisent et exécutent.

**Démonstration :** choisir une identité fictive, calculer le tarif, confirmer la commande, payer dans Bridge sandbox, observer la délivrance et consulter les traces.

**Preuves attendues :** architecture de haut niveau, version du dépôt, scénario rejouable, résultats des tests, traces et tableau distinguant réel, sandbox, simulé et futur.

**Question à résoudre :** quelles responsabilités sont réellement séparées, et où subsistent des dépendances fortes ?

### Article 2 — Ajouter un service local à une plateforme de mobilité

**Besoin :** intégrer un service local — théâtre, piscine, bibliothèque ou autre équipement de proximité — seul ou dans un parcours comprenant transport et parking.

L’extension ajoute une offre, un opérateur fictif, ses éventuels tarifs, ses conditions d’accès et son mode de délivrance. Les exemples possibles sont un billet de théâtre, une entrée piscine ou une inscription à la bibliothèque. Le service peut être payant ou gratuit : la réutilisation ne se limite pas au paiement. Pour garder une démonstration maîtrisée, un seul service et un seul type de droit seront retenus lors de la réalisation, sans placement en salle, créneau complexe ni gestion complète des prêts.

Le panier, le paiement, les commissions et le SAV doivent être réutilisés autant que possible. L’article suivra les composants effectivement réutilisés et les adaptations nécessaires. Le support du droit est à choisir explicitement : QR code dédié ou droit sur une carte compatible ; la compatibilité matérielle ne sera pas présumée. Une entrée piscine peut servir d’exemple concret, sans définir à elle seule le périmètre de l’article.

Un agent du partenaire local retenu peut exposer une coopération A2A et accéder au service métier par MCP. Son utilité doit être explicitée ; la disponibilité, les droits et leur utilisation restent sous contrôle déterministe du service métier.

**Preuves attendues :** diff par rapport à la version de départ, liste des composants réutilisés et modifiés, tests d’attribution ou de vente et de contrôle, vérification de la répartition par opérateur lorsque le service est payant et absence de régression sur les offres existantes.

**Question à résoudre :** l’architecture accepte-t-elle un nouveau métier, ou contient-elle encore des hypothèses propres au transport ?

### Article 3 — Une même offre, plusieurs points de vente

**Besoin :** distribuer l’offre du service local retenu dans l’article précédent depuis le site, la borne et l’agence.

L’article examine la séparation entre interfaces et fonctions métier. Les canaux partagent les règles et les services, tout en conservant une expérience, une identité vendeur, une commission et des habilitations adaptées.

**Démonstration :** effectuer des achats comparables depuis les trois canaux et expliquer les différences légitimes de présentation, de droits et de répartition financière.

**Preuves attendues :** scénarios par canal, cohérence des tarifs pour les mêmes conditions, commissions attendues, contrôles d’accès et traces de délivrance.

**Question à résoudre :** combien de logique métier a réellement été dupliquée dans les interfaces ?

### Article 4 — Changer de fournisseur sans refaire le parcours

**Besoin :** remplacer un connecteur partenaire par une seconde implémentation respectant le même contrat.

Pour garder un périmètre maîtrisé, le premier exemple peut porter sur le contrôle d’accès au service local retenu, par exemple le contrôle d’entrée d’une piscine. Deux fournisseurs fictifs peuvent utiliser des formats et des comportements différents, derrière des adaptateurs vers le même service métier. Les essais compareront les deux adaptateurs sur un même contrat d’interface.

**Démonstration :** sélectionner le second connecteur et rejouer les scénarios fonctionnels, y compris une indisponibilité et un doublon.

**Preuves attendues :** contrat d’interface, tests de conformité communs, adaptations nécessaires et inventaire des changements hors connecteur.

**Question à résoudre :** le contrat d’intégration isole-t-il réellement les particularités du fournisseur ?

### Article 5 — Passer du ticket à l’abonnement étudiant annuel

**Besoin :** souscrire un abonnement annuel étudiant assorti de douze échéances mensuelles.

L’extension introduit un cycle de vie : justificatif fictif, décision d’éligibilité contrôlée, contrat, échéancier, signature de démonstration, première échéance Bridge sandbox et échéances suivantes sur un prestataire récurrent simulé avec état.

Temporal déroule les mois en temps accéléré. Le scénario comprend un refus de paiement et une intervention du SAV. La signature du contrat, l’autorisation bancaire et l’ancrage sur Anvil sont trois fonctions distinctes.

La signature qualifiée, les vrais prélèvements, le recouvrement et la couverture exhaustive des règles contractuelles restent hors périmètre. Les capacités récurrentes de Bridge accessibles au compte doivent être établies avant de revendiquer une intégration bancaire récurrente réelle. Le choix de la solution de signature reste à arrêter.

**Preuves attendues :** états du contrat et de chaque échéance, calendrier accéléré, décisions d’habilitation, contrôle des doublons, reprises et distinction explicite entre paiements sandbox et paiements simulés.

**Question à résoudre :** comment introduire un engagement long sans coupler excessivement vente, paiement et délivrance ?

### Article 6 — Quand un partenaire tombe en panne

**Besoin :** conserver un parcours cohérent malgré les interruptions et réponses incertaines.

L’article rassemble les scénarios de panne préparés au fil de la série : service indisponible, worker redémarré, événement reçu plusieurs fois, paiement confirmé mais délivrance interrompue, réponse partenaire incertaine et ancrage blockchain retardé.

**Démonstration :** provoquer les incidents, observer les états intermédiaires, reprendre les opérations et vérifier les effets métier. Une réponse incertaine ne doit pas provoquer une nouvelle opération financière à l’aveugle.

**Preuves attendues :** chronologie des traces, compteurs de paiement et de délivrance, tests d’idempotence, états de rapprochement et intervention humaine lorsque la reprise automatique ne suffit pas.

**Question à résoudre :** la souplesse de conception se traduit-elle aussi par une capacité de reprise compréhensible et contrôlée ?

### Article 7 — Du MaaS au portefeuille territorial : une aide, plusieurs services

**Épisode prévu : portefeuille territorial multiservice.**

**Besoin :** permettre à une région d’attribuer à un habitant 300 crédits territoriaux fictifs, avec une valeur d’usage de référence de 300 €, utilisables pour le transport, la piscine et le théâtre local. Le bénéficiaire ne reçoit pas d’euros sur un compte bancaire.

Ce scénario prolonge l’ajout de services et l’abonnement étudiant : une aide peut financer tout ou partie d’un achat ou d’une échéance. L’objectif est d’évaluer la capacité du socle à accueillir un financeur et un portefeuille commun à plusieurs opérateurs, sans reconstruire les parcours de vente.

**Scénario proposé :**

1. La région fictive attribue 300 crédits à Léa, avec une date de validité et une liste de services autorisés.
2. Léa utilise 40 crédits pour le transport, 5 pour la piscine et 15 pour le théâtre. Le solde disponible devient 240 crédits.
3. Un achat partiellement financé montre séparément les crédits mobilisés et le reste à charge. Une éventuelle intégration Bridge sandbox ne concernerait que ce reste à charge ; les crédits ne seraient pas des fonds bancaires Bridge.
4. Une tentative d’utilisation hors périmètre ou après expiration est refusée avec une explication.
5. Une annulation restitue les crédits selon une règle explicite, en conservant leur provenance et les restrictions applicables.
6. L’habitant consulte son solde et ses mouvements ; le financeur suit les attributions et les consommations ; chaque opérateur consulte les opérations le concernant.

**Périmètre initial envisagé :** un financeur, trois services, des identités et des crédits entièrement fictifs, sans transfert entre habitants ni conversion en espèces. L’extension à plusieurs financeurs — commune, association, région — viendrait ensuite, avec enveloppes et règles de cumul distinctes. Le nom et l’unité d’affichage restent à choisir avant réalisation.

**Réutilisation à éprouver :** identités, interfaces, catalogue, règles tarifaires, commandes, habilitations, workflows Temporal, audit et connecteurs partenaires. Un service déterministe de portefeuille serait à ajouter pour les soldes, réservations, consommations et restitutions, avec registre de mouvements et contrôle de concurrence. Les agents IA expliqueraient les droits et coordonneraient les demandes via les interfaces A2A/MCP retenues ; ils ne décideraient pas librement des soldes. FalkorDB servirait à rechercher les dispositifs et leurs règles, sans être le registre de référence des crédits. Anvil pourrait ancrer des preuves de mouvements ; la blockchain ne serait pas indispensable au fonctionnement du portefeuille.

**Modèle économique à arrêter avant réalisation :** distinguer les droits d’accès acceptés dans le cadre d’une convention et d’un budget préalablement financé des crédits donnant droit à un remboursement ultérieur des opérateurs. Dans le second cas, les crédits peuvent simplifier le rapprochement et regrouper les règlements, mais ne suppriment pas les flux en euros. Les deux mécanismes seraient simulés dans ce futur POC si leur démonstration est retenue.

L’expression « monnaie électronique » reste une hypothèse de qualification, pas une propriété acquise de l’architecture. La valeur d’usage équivalente à l’euro et le caractère territorial ne déterminent pas seuls le cadre applicable. Toute expérimentation avec des valeurs ou services réels nécessiterait de préciser les droits attachés aux crédits, leur financement et leur acceptation. Référence de cadrage : [position de l’ACPR sur les réseaux et usages limités](https://acpr.banque-france.fr/sites/default/files/media/2023/07/26/20230726_position_2022-p-01.pdf).

**Preuves attendues :** diff d’architecture, registre de mouvements cohérent, attribution et dépenses sans doublon, refus d’une double dépense concurrente, isolation des bénéficiaires et financeurs, contrôles d’expiration et d’éligibilité, paiement partiel sans double effet, annulation avec restitution traçable et absence de régression sur les ventes existantes.

**Question à résoudre :** peut-on ajouter un financement territorial affecté et plusieurs services en réutilisant le socle, tout en conservant des soldes fiables, des règles explicables et une séparation claire des responsabilités ?

## 4. Le protocole commun à chaque article

Chaque épisode conserve la même structure :

1. **Le besoin nouveau** : acteur, déclencheur et comportement attendu.
2. **Le périmètre** : ce qui est réel, sandbox, simulé ou laissé pour plus tard.
3. **L’hypothèse d’architecture** : ce que le socle devrait permettre de réutiliser.
4. **La réalisation** : composants réutilisés, configurés, modifiés et ajoutés.
5. **La démonstration** : commandes et étapes permettant de rejouer le scénario.
6. **Les vérifications** : résultat attendu, résultat observé, tests et traces.
7. **Le bilan critique** : difficultés, couplages découverts, corrections et limites.

Un encart récurrent pourra résumer « Les acquis de cette évolution » et « Les prochaines pistes à explorer ».

## 5. Les preuves à publier

| Élément | Utilité | Limite d’interprétation |
|---|---|---|
| Version de départ et version d’arrivée | Identifier exactement les états comparés. | Un environnement non documenté peut empêcher la reproduction. |
| Diff du code, des données et de la configuration | Rendre visible l’effort de changement. | Peu de lignes modifiées ne prouve pas à lui seul une bonne architecture. |
| Inventaire des composants touchés | Repérer les couplages et la réutilisation. | Une configuration complexe reste un coût d’adaptation. |
| Tests fonctionnels et de non-régression | Vérifier la nouvelle capacité et les parcours conservés. | Les tests ne couvrent que les scénarios effectivement exécutés. |
| Traces du parcours | Montrer les appels A2A/MCP, les workflows et les frontières. | Une capture d’écran seule ne prouve pas la réalité d’un protocole. |
| Compteurs et contrôles d’idempotence | Vérifier l’absence de doubles effets dans les scénarios testés. | Ne garantit pas tous les cas de concurrence possibles. |
| Temps de réalisation, si suivi | Documenter l’expérience dans un contexte précis. | Ne constitue pas un benchmark de productivité généralisable. |
| Enseignements et interventions manuelles | Expliquer les choix et les points de progression. | Les observations sont rattachées au scénario et aux conditions de l’essai. |

Les captures, jeux de données et traces publiés doivent rester fictifs ou être nettoyés des secrets et informations sensibles.

## 6. L’organisation du dépôt

Avant le premier article, préparer un état initial reproductible : instructions de démarrage Docker, paramètres d’exemple sans secrets, jeux de données fictifs, versions des composants et commandes de vérification.

Chaque épisode disposera d’un dossier documentaire contenant le besoin, le scénario, les commandes, les résultats et les captures. Lorsque le projet sera versionné dans Git, des tags permettront de comparer les états successifs. La création et la publication du dépôt ne sont pas réalisées par ce document.

Les articles pourront renvoyer au même code original sous licence MIT. Les dépendances conserveront leurs licences propres ; l’ensemble de la pile ne doit pas être présenté comme intégralement sous MIT.

## 7. La prochaine étape recommandée

Commencer par figer le socle et rédiger le premier article à partir des preuves disponibles. Ajouter ensuite un service local — théâtre, piscine ou bibliothèque, par exemple — en tenant le journal des adaptations dès le début de l’implémentation.

L’abonnement étudiant reste un épisode ultérieur : il introduit simultanément signature, autorisation bancaire et cycle de vie contractuel. L’ajout d’un service local constitue un premier test plus ciblé de la capacité à accueillir un nouveau partenaire et un nouveau produit.

Le portefeuille territorial prolonge les premières extensions multiservices dans un épisode dédié.

Le critère d’arrêt de chaque évolution est un scénario rejouable, des résultats vérifiés et des limites documentées. L’ajout de technologies ne constitue pas un objectif en soi.
