# Documentation d’Alizé Lab

État du dépôt au **29 octobre 2026**. Le [cadre du projet](../README.md) précise les données de démonstration, les équipements simulés et les services externes utilisés.

## Commencer

| Besoin | Document |
|---|---|
| Installer et démarrer | [README du projet](../README.md#démarrer) |
| Voir les parcours en vidéo | [Démonstration commentée en français, 3 min 04](videos/README.md) |
| Présenter les parcours dans l’interface | [Guide de démonstration](guide-demonstration.md) |
| Mettre à jour, configurer et vérifier | [Exploitation et vérifications](exploitation-et-verification.md) |
| Comprendre les responsabilités et les échanges | [Dossier d’architecture](architecture/README.md) |
| Distinguer ce qui est testé et ce qui reste à qualifier | [Audit ABT](audit-tests-abt-2026-10-29.md) et [audit des autres domaines](audit-tests-hors-abt-2026-10-29.md) |

## Parcours et choix d’implémentation

| Domaine | Référence |
|---|---|
| Connexion fictive, panier, commandes et titres | [Voyageur](voyageur-ergonomie-2026-10-27.md) |
| Poste de vente et de relation client | [Agence en gare et CRC](poste-agence-crc-2026-10-28.md) |
| Compte, abonnement annuel mensualisé et post-paiement | [Compte mobilité ABT](abt-transport-2026-10-29.md) |
| Sélection des agents, historique et preuves de commande | [Routage, achats et preuves](routage-achats-preuves-2026-10-29.md) |
| Tarifs, disponibilité et proposition combinée | [Coopération entre organisations](cooperation-organisations-2026-10-28.md) |
| Consultations simultanées et limite de concurrence | [Parallélisme des consultations](consultations-paralleles-2026-10-29.md) |
| Activité A2A et MCP pendant l’exécution | [Échanges en direct](echanges-agents-direct-2026-10-28.md) |
| Capture webcam, traitement local et audio OpenAI facultatif | [Parcours webcam et audio](webcam-audio-local-2026-10-28.md) |
| Ressources et résultats du modèle audiovisuel | [mWhisper-Flamingo](perception-whisper-flamingo-2026-10-28.md) |
| Borne et paiement QR | [Interface automate](automate-ihm-2026-10-24.md), [QR Bridge](automate-qr-2026-10-25.md) |
| Réservation et usage Vélo/Parking | [Partenaires A2A/MCP](partenaires-a2a-2026-10-24.md) |

## Rapports et preuves

Les rapports datés décrivent leurs essais à cette date. Leurs comptes de tests et leurs captures sont des instantanés ; les guides ci-dessus donnent le parcours courant. Ainsi, les essais historiques du modèle labial avec un fichier ne décrivent pas un import disponible dans l’interface actuelle, qui utilise uniquement la webcam.

- [Première validation du socle](validation-2026-10-24.md), [modèles locaux et cloud](tests-ia-locale-et-acces-2026-10-24.md), [paiement Bridge sandbox](test-paiement-bridge-2026-10-24.md).
- Résultats structurés : [coopération](evidence-cooperation-organisations-2026-10-28.json), [chevauchement A2A](evidence-consultations-paralleles-2026-10-29.json), [audit hors ABT](evidence-audit-hors-abt-2026-10-29.json).
- Les sorties de nouveaux essais restent dans `data/` ou `artifacts/`, exclus de Git. Les fichiers explicitement conservés dans `docs/` constituent les preuves publiées avec le dépôt.

Les [articles en préparation](articles/01-maas-agentique/README.md), la [série envisagée](serie-articles-souplesse-maas-agentique.md) et le [plan cible](../plan-implementation-poc.md) ne constituent pas un inventaire des fonctions livrées.
