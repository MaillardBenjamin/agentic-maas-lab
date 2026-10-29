# Compte mobilité et titres transport ABT

Implémentation locale du 29 octobre 2026. Les tarifs retenus sont des tarifs de démonstration ; les prélèvements et valideurs de ce parcours sont simulés.

## Un compte par voyageur connu

Dès la confirmation d’un achat avec un voyageur identifié, l’API rattache la commande au compte ABT de ce voyageur et de son organisation, dans la même transaction. Cela couvre les commandes classiques transport, parking et vélo, depuis le site, la borne ou l’agence. Le rapprochement porte sur le voyageur bénéficiaire, même lorsque le conseiller effectue la vente. Le client ne choisit pas librement un identifiant de compte.

Le worker rattache également les commandes existantes dont le voyageur est connu. La reprise est idempotente. Les commandes carte existantes gardent leur délivrance sur carte ; leur rattachement au compte ne change pas leur support ni leurs conditions. Les nouveaux titres ABT ont, eux, un droit conservé dans le compte, sans chargement de titre Keyple.

Les commandes, contrats, échéances et usages ABT portent le même `account_id`. Les achats classiques restent visibles dans « Mes titres » et sont également résumés dans « Compte mobilité ».

## Deux offres complémentaires à la gamme

| Offre | Tarif | Droit et facturation |
|---|---|---|
| Abonnement annuel | 600 €, douze mensualités de 50 € | Trajets inclus sur la période annuelle ; échéancier établi à la souscription, première échéance à la date de début. |
| Post-paiement | 2 € par trajet, plafond de 60 € par mois civil UTC | Chaque passage accepté produit une charge bornée ; les usages du mois clos sont facturés au début du mois suivant. |

Ces deux offres sont alternatives sur une même période transport : le serveur refuse un chevauchement pour éviter une double facturation. La validité de cette première gamme est d’un an, sans renouvellement automatique. Les tarifs sont modifiables dans `fixtures/catalog.json`, rubrique `abt_products`, et chaque contrat conserve les conditions acceptées. Les réductions du titre unitaire ne s’appliquent pas automatiquement à cette gamme.

## Achat, usage et impayé

Dans Voyageur → Compte mobilité : choisir un titre et une date, consulter le tarif, puis accepter les conditions et le prélèvement simulé. La confirmation est idempotente. Les souscriptions rétroactives sont refusées.

Le bouton « Simuler un trajet » interroge un droit du compte : propriétaire autorisé, état actif, date dans la période et absence d’impayé suspendant. Les passages sont dédupliqués par compte de contrat et identité métier. Un même passage avec un contenu contradictoire est refusé. Les traitements concurrents verrouillent le contrat avant calcul du cumul et du plafond. Une période facturée ne peut plus recevoir de passage tardif automatiquement : elle nécessite un rapprochement.

Le worker traite automatiquement les échéances exigibles et les mois clos. Il conserve le statut `paid_simulated`, les tentatives et leurs résultats. Un échec suspend le droit ; une régularisation simulée le réactive si aucun autre impayé ne subsiste et si la validité le permet. Les échéances futures restent impayables avant leur date. Un redémarrage reprend les données persistées sans recréer les échéances ni répéter les paiements simulés réussis.

## Interfaces et agents

| Interface | Usage |
|---|---|
| `GET /api/abt` | Compte du voyageur connecté ; conseiller avec voyageur explicite et autorisé. |
| `POST /api/abt/subscriptions` | Souscription avec consentement, produit, date et clé d’idempotence. |
| `POST /api/demo/abt/{id}/validate` | Passage du valideur simulé. |
| `POST /api/demo/abt/invoices/{id}/collect` | Essai ou régularisation du prélèvement simulé. |
| `POST /internal/abt/billing` | Traitement automatique réservé aux services. |
| `GET /api/assistant/abt` | Lecture liée au voyageur du contexte signé. |
| MCP `read_abt_account` | Consultation des droits, achats rattachés, usages et factures par l’agent Achats. |

L’agent Transport expose les offres ABT publiées. Une demande sur « mon compte », « mes titres » ou « mes mensualités » passe par l’agent de consultation des achats et le nouvel outil de lecture ; aucun outil agent ne souscrit ou ne prélève.

## Vérifications et périmètre

`tests/test_abt.py` couvre calendrier de mensualités, montant annuel, consentement, identité, rattachement des anciens achats, trajets inclus, plafonnement, doublons, clôture mensuelle, impayé, reprise, droits futurs et expiration. Les tests calendaires avancent une date de test, sans modifier l’horloge du service local.

`scripts/abt_smoke.py` teste les services et PostgreSQL réels : douze mensualités, premier prélèvement simulé automatique, 70 livraisons concurrentes pour 35 trajets et 60 € de charges, isolation Léa/Alex, rattachement des commandes connues et consultation A2A/MCP avec modèle de test déclaré.

Un connecteur de prélèvement récurrent bancaire, des identifiants de support de validation physique, les annulations contractuelles et le rapprochement des passages tardifs restent des extensions. Bridge demeure utilisé pour les paiements ponctuels existants. Les commissions et les preuves blockchain de commandes existantes restent inchangées ; le nouveau journal de facturation ABT est persisté hors chaîne et ne constitue pas un encaissement bancaire réel.

Validation finale locale : **136 tests API**, **15 tests de garde des agents** et **37 tests d’interface** réussis ; construction TypeScript/Vite réussie. Les essais HTTP d’achat classique avec `account_id`, ABT concurrent et A2A/MCP sont passés. La page Compte mobilité a été vérifiée dans le navigateur : achats rattachés, tarifs, consentement et échéancier chronologique visibles.

Un [audit de complétude](audit-tests-abt-2026-10-29.md) a ensuite complété la couverture, corrigé un état d’expiration et précisé les limites : 161 tests API, 16 gardes du runtime, 37 tests web et cinq scénarios de concurrence PostgreSQL réussis.
