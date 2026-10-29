# Audit de complétude des tests ABT — 29 octobre 2026

## Conclusion

Le contrôle a porté sur les derniers ajouts : compte ABT, rattachement des achats connus, abonnement annuel mensualisé, post-paiement et lecture par les agents. Il ne constitue pas une certification de complétude de tous les modules du POC.

La suite initiale vérifiait les parcours principaux, mais ne permettait pas de conclure à leur exhaustivité. Elle mélangeait une date de facturation simulée et une horloge de validation réelle ; le scénario concurrent pouvait simplement rejouer des usages déjà présents. Les tests d’interface existants ne comportent pas de parcours automatisé dédié au composant ABT.

## Compléments réalisés et résultats

| Domaine | Contrôles présents et exécutés |
|---|---|
| Compte et identité | Lecture propre compte, conseiller lié au voyageur, jeton signé lié à son acteur, refus inter-voyageurs et inter-organisations, accès sans authentification, voyageur inconnu. |
| Achat connu | Création réelle via les fonctions HTTP de l’API en environnement isolé, trois canaux web/automate/agence, rattachement au bénéficiaire plutôt qu’au conseiller, confirmation répétée sans seconde commande. |
| Reprise des données | Commandes historiques des trois canaux, conservation de l’état, absence de rattachement des voyageurs inconnus ou d’une autre organisation, reprise des contrats et échéances ABT sans identifiant de compte. |
| Souscription | Consentement, refus rétroactif, même clé/même résultat, clé réutilisée avec contenu différent refusée, chevauchement refusé, période suivante adjacente admise, atomicité contrat/compte/douze échéances. |
| Calendrier | Fin de mois, février bissextile, changement d’année, début inclus et fin exclue, heure future refusée, début de validité futur, expiration, date unique simulée pour les validations et la facturation. |
| Abonnement annuel | Total de 600 €, douze mensualités, trajets inclus à zéro, absence de prélèvement anticipé, rattrapage des douze échéances après indisponibilité sans répétition d’un paiement réussi. |
| Post-paiement | Plafond de 60 €, déduplication et contradiction, conversion UTC autour du changement de mois, remise à zéro mensuelle du cumul, mois sans usage, clôture unique, passage tardif refusé après facturation, conservation des tarifs acceptés après changement du catalogue. |
| Impayés | Suspension, régularisation, plusieurs impayés empêchant une réactivation prématurée, historique des tentatives, aucune répétition d’un prélèvement réussi, fin de validité prioritaire sur la suspension. |
| Transactions et reprise | Échec injecté pendant la création de l’échéancier et pendant une facturation : rollback intégral puis reprise sans double effet. Échec HTTP d’un des deux traitements du worker : l’autre reste appelé, puis les deux sont retentés. |
| Concurrence PostgreSQL | Schéma neuf à chaque exécution : huit souscriptions identiques simultanées → un contrat ; souscriptions concurrentes incompatibles refusées ; 70 livraisons → **35 nouveaux usages** et 6 000 centimes ; quatre clôtures simultanées → une facture et un prélèvement ; huit régularisations simultanées → une tentative réussie persistée. |
| Agents | Une demande de compte ABT ne peut être synthétisée depuis le seul historique d’achats : l’outil `read_abt_account` est requis. Les autres gardes de périmètre et de parallélisation restent validées. |

Résultats finaux : **161 tests API réussis**, dont **31 tests ABT/worker**, **16 tests de garde du runtime agents**, **37 tests d’état/interface existants**. Les **cinq scénarios PostgreSQL** supplémentaires sont passés. Les appels HTTP des tests isolés passent par FastAPI TestClient ; la base et les verrous PostgreSQL sont réels. Le schéma de test est supprimé à la fin, sans modifier les comptes de démonstration.

Les 37 tests web concernent les fonctions déjà testées du frontal ; ils ne sont pas présentés comme 37 tests du composant ABT.

## Défaut corrigé

Un prélèvement échoué après la fin du contrat pouvait remettre le statut à `suspended` au lieu de conserver `expired`. Le calcul donne désormais priorité à la fin de validité ; un test couvre cette régression. Le correctif a été construit et chargé dans l’API et le worker locaux.

## Mesure des lignes exécutées

La mesure utilise le traceur standard Python, y compris les threads des appels HTTP. Sur `services/api/maas/abt.py` : **177 lignes exécutées sur 179, soit 98,9 %**.

Cette mesure porte sur les lignes exécutables du module ABT, pas sur les branches, toutes les combinaisons métier, le frontal ou le dépôt entier. Les deux lignes non exécutées par cette mesure sont la lecture de l’horloge réelle — volontairement remplacée dans les tests calendaires — et le retour de secours en cas d’`IntegrityError` de souscription. La concurrence ordinaire est testée sur PostgreSQL, mais ne force pas cette exception de secours.

## Points restant hors couverture exhaustive

- Parcours navigateur ABT automatisés : consentement, chargement, perte de réponse, rechargement, changement de profil et régularisation. La vérification visuelle précédente reste une vérification manuelle.
- Arrêt brutal d’un processus worker pendant une facturation ABT, au-delà du rollback et de la reprise déjà testés en isolation.
- Campagne de robustesse du nouveau dialogue ABT avec différents modèles réels. Les gardes et le parcours de protocole utilisent un modèle de test déclaré.
- Prélèvements bancaires récurrents réels, lecteur physique ABT, résiliation, rapprochement des passages tardifs : ces extensions ne sont pas encore implémentées ; leurs tests d’acceptation restent à définir avec l’intégration.
- Tests de charge prolongée et objectifs de latence : 70 livraisons concurrentes ne constituent pas une qualification de capacité.

## Rejouer

Après reconstruction des images :

- `make test` : ensemble API, tests web et politiques OPA.
- `make test-abt` : ABT/worker/routage puis concurrence PostgreSQL dans un schéma neuf.
- `make audit-abt` : mesure des lignes exécutées à partir des sources montées, sans installation d’une dépendance de couverture.
- `make test-cooperation` : gardes des agents et échanges A2A/MCP avec modèle de test.
- `make test-abt-demo` : parcours local sur les comptes de démonstration existants ; son rejeu idempotent ne remplace pas l’essai PostgreSQL neuf pour établir la concurrence.
