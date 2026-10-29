# Audit des tests hors ABT — 29 octobre 2026

## Conclusion

Les fonctions principales du POC disposent de tests automatisés et de scripts d’intégration, mais leur couverture reste **inégale**. Une suite verte ne permet pas de conclure à la complétude du produit, des interfaces, de la sécurité ou de la résilience.

Cet audit étend l’audit ABT aux autres domaines. Il a relu le code et les assertions, exécuté les suites locales ci-dessous et ajouté **13 tests Python hors ABT**, deux tests Solidity et un scénario PostgreSQL du budget IA.

## Résultats effectivement rejoués

- **174 tests Python API**, dont **143 hors ABT** et 31 ABT/worker, réussis.
- **37 tests web** de fonctions d’état, capture et rendu Markdown, réussis : ce ne sont pas 37 parcours navigateur complets.
- **16 gardes du runtime agents**, dont la garde ABT, réussies.
- **5 tests OPA**, réussis.
- **6 tests Solidity ProofRegistry**, réussis.
- Cartes A2A/MCP : neuf cartes consultées, quatorze outils découverts, échange de protocole réussi avec modèle de test déclaré.
- Achat local : devis, commande répétée, paiement répété, émission unique, événements dupliqués, régularisations concurrentes, refus et commissions réussis.
- Agence/CRC : vente, délivrance relue sur stub, dossier de contact, dépassement de délégation refusé, régularisation répétée sans nouvel effet et fermeture du dossier réussis.
- Partenaires : six opérations A2A/MCP réserve/démarre/termine pour Vélo et Parking ; stock restauré, événements rejoués sans seconde facturation, outils hors périmètre refusés.
- Concurrence partenaires : trois réservations pour deux vélos, deux succès, un refus, libération puis reprise de la demande refusée, stock final restauré.
- Consultations : tarif Parking, disponibilité, préparation combinée, SAV et commissions ; invariance de l’ensemble des commandes et de leurs états.
- Reprise après **arrêt brutal réel du worker** : signal durable, réponse carte perdue après écriture, un paiement et un chargement après reprise.
- Sécurité : accès inter-organisations, webhook non signé, session absente et consentement audio refusés ; arrêt réel d’OPA, régularisation refusée sans effet, puis redémarrage.
- Blockchain : redémarrage réel d’Anvil, **48 preuves persistées**, versions 1 et 2 relues sans nouvelle transaction.
- Budget IA : PostgreSQL dans un schéma neuf et supprimé en fin de test ; dix réservations concurrentes de 30 centimes pour un plafond de 100, trois admises et sept refusées ; solde exact de 100 autorisé, dépassement refusé sans incrément.

API, worker, OPA et Anvil ont été laissés démarrés après les essais.

## Matrice par domaine

Les pourcentages concernent exclusivement les **lignes exécutées par pytest**, pas les branches ni les scripts d’intégration externes. Ils aident à repérer où les tests se concentrent ; ils ne constituent pas un score de qualité fonctionnelle. Les traces et les comptes par module figurent dans [les résultats structurés](evidence-audit-hors-abt-2026-10-29.json).

| Domaine | Ce qui est couvert | Limites ou compléments prioritaires |
|---|---|---|
| Tarifs et commissions | Moteur à 96 % des lignes ; droits étudiant/âge, non-cumul, vendeur, arrondis par ligne, conservation des centimes et des conditions acceptées, régularisation ciblée/proportionnelle, absence de commission encaissée sur impayé. | Tests génératifs sur une grande variété de paniers et ventilations, évolutions/versionnement de grilles. |
| Vente et API métier | Achat réel local, répétition, droits, rattachement au bénéficiaire et transactions testées. `api.py` reste à 42,7 % dans pytest. | Transformer davantage de parcours de scripts en régressions isolées des routes ; couvrir les combinaisons d’états et les pannes à chaque transition. |
| Paiement Bridge | 21 tests de connecteur, sept nouveaux tests d’orchestration ; signature, statut, référence, montant et devise, lien distinct d’un règlement, intention persistée avant appel, absence de second POST après réponse incertaine, répétition du polling, reprise du signal Temporal. `integrations.py` passe de 44,7 % à 73,3 %. | Les nouvelles réponses bancaires sont simulées. Pas de nouveau règlement bancaire externe pendant cet audit ; compléter les notifications tardives/désordonnées et le rapprochement manuel. |
| Carte et délivrance | Quatre nouveaux tests du simulateur, 98,2 % des lignes : chargement répété, clé contradictoire, réponse perdue après commit, panne SDK puis reprise, accès de service. Test réel de reprise worker + SDK sur carte stub. | Deux tests Java sont présents et exécutés à la construction Keyple, mais n’ont pas été rejoués comme suite Java séparée ici. Pas de lecteur/carte/SAM physiques. |
| SAV et agence | Cinq tests de dossier, OPA et parcours HTTP réel ; rôles, organisation, révisions, notes, répétition, refus de dépassement. Module agence à 92,5 %. | Régularisations financières simulées ; remboursement bancaire réel non implémenté. Davantage de concurrence sur les mises à jour et parcours navigateur à automatiser. |
| Vélo/Parking | Dix-sept tests de domaine partenaire, neuf de coopération fournisseur ; cycles, stock, confirmation et délégation limitée, prix acceptés, accès voyageur, reprise et concurrence réelles. Module partenaires à 55,1 % dans pytest, complété par les scripts A2A/Temporal. | Une partie des scripts dépend des stocks du démonstrateur partagé : isoler leurs données. Étendre la matrice de pannes réseau et de callbacks retardés. |
| Routage et agents | Dix-huit tests de routage, gardes obligatoires avant réponse, sélection par demande/service/compétences, liste vide contrôlée, propagation du contexte, parallélisme borné, échec et annulation drainés. Routage à 93,2 %. | Aucun corpus large de formulations, fautes et demandes multi-intentions. Les tests de protocole ne prouvent pas la robustesse d’un modèle réel ni une faible latence. |
| Historique et preuves métier | Pagination, identité et autorisation avant chaîne, atomicité, couverture de chaque source, signature et vérification actuelle, altération, instance changée et chaîne inaccessible. Historique à 77,7 %, production des preuves à 92 %. | Reprise des échecs définitifs de distribution, migrations de schémas et réancrage après réinitialisation complète à approfondir. |
| Blockchain | Six tests de contrat ; signature concurrente ; rejet d’altération, publication non autorisée, empreinte vide et version contradictoire ; persistance de 48 preuves après redémarrage. | Réseau Anvil local, pas une qualification d’un réseau partagé ni de sa gouvernance. Le redémarrage ne remplace pas un test de restauration après perte du volume. |
| Budget IA | Plafond et verrou consultatif testés sur PostgreSQL sous concurrence. Le 33,3 % de pytest exclut ce scénario séparé. | Changement de mois, erreurs de configuration et rapprochement avec la facture du fournisseur restent à compléter. Une réservation interne n’est pas une dépense mesurée. |
| Recherche documentaire | Trois tests de normalisation/vecteurs, recherche réelle utilisée dans les scripts de coopération ; 50 % dans pytest. | Corpus d’évaluation pertinence/rappel/citations, absence de résultat et panne du graphe insuffisamment systématisés. Les vecteurs lexicaux ne sont pas une validation d’une compréhension sémantique. |
| Audio, webcam et perception | Consentement, session, limites, propriété des résultats, absence de vidéo envoyée au cloud, états de capture et annulation. Modules API audio/perception à 97,7 %/98,1 %. | Ces chiffres concernent les contrôles et réponses simulées, pas la qualité de reconnaissance. Pas de corpus accents/bruit/lecture labiale ni de campagne micro/caméra réels rejouée ici. |
| Suivi des agents et observabilité | Quatre tests d’activité API, trois tests web de suivi ; visibilité limitée à la session et conservation des échanges vérifiées. | Mesurer la propagation des traces et la visibilité sous charge/déconnexion, définir des objectifs de latence et de disponibilité. |
| Interfaces | Tests de fonctions pour borne, panier, agence, activité, audio et webcam. | Absence de suite navigateur complète couvrant vente → paiement → titre → service → SAV sur différents profils et formats d’écran ; accessibilité et navigation clavier à systématiser. |

## Défauts du dispositif de test corrigés

1. **Versions de preuves.** Le script de redémarrage et celui de rejeu utilisaient implicitement le schéma 1. Ils transmettent désormais la version conservée dans le manifeste. Le test attend aussi, de façon bornée, la fin des ancrages asynchrones avant de fixer son état de référence.
2. **Audio et fournisseur des agents.** Le contrôle de sécurité déduisait à tort la disponibilité audio du mode OpenAI des agents. Il lit maintenant `/api/voice/status` et contrôle un refus de consentement si l’audio est activé, sans demander de jeton cloud.
3. **Sortie sensible en cas d’échec.** Le diagnostic de test masque la réponse de création de session audio. Deux tests de non-régression vérifient l’absence de création cloud dans le contrôle de sécurité et la non-divulgation d’un jeton inattendu.
4. **Commande d’ensemble.** `make verify` inclut désormais les intégrations historique/routage, ABT, agence et budget concurrent qui manquaient à sa liste. **La commande complète `make verify` n’a pas été lancée intégralement dans cet audit** : les suites rejouées sont celles listées plus haut. Les options cloud, perception complète, expériences de laboratoire et matériel restent distinctes.

### Incident du premier rejeu audio

Le premier rejeu du contrôle obsolète, après ajout du consentement requis, a créé un jeton éphémère et une **réservation applicative de 300 centimes**. Aucune connexion audio n’a été ouverte. Cette réservation conservatrice est laissée dans le registre ; elle ne mesure pas une facture fournisseur. Les rejeux après correction n’ajoutent plus de réservation. La valeur du jeton n’est pas conservée dans ce rapport.

## Priorités proposées après l’audit

1. Automatiser les parcours navigateur et les variations de profil, contexte et retour tardif.
2. Isoler les données de tous les scénarios d’intégration, comme les scénarios PostgreSQL ABT et budget.
3. Construire un corpus de routage et de recherche, incluant les demandes multi-intentions et des formulations adverses.
4. Étendre les tests de pannes aux frontières des paiements, partenaires, migrations, ancrages et restaurations.
5. Qualifier la charge, la latence, la précision de perception et les intégrations externes sur leurs environnements dédiés.

Reproduction : `make audit-tests` produit l’inventaire pytest et les résultats JUnit dans `data/test-audit/`. Les autres contrôles disposent de cibles séparées dans le Makefile, notamment `test-cooperation`, `test-partners`, `test-partners-concurrency`, `test-agency`, `security`, `resilience`, `chain-restart` et `test-budget-concurrency`.
