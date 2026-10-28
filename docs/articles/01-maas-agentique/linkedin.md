Ajouter un théâtre, une piscine ou une bibliothèque à une plateforme de mobilité : quelle part du système faut-il réellement modifier ?

J’ouvre une série d’articles pour explorer cette question à partir d’un projet open source : Alizé Lab.

Le premier parcours est en place : une voyageuse compose son offre transport + parking + vélo, obtient son tarif étudiant, paie 12 € via Bridge sandbox et reçoit ses droits avec Keyple.

Le projet est un POC personnel, avec des données et équipements de démonstration.

Sa règle d’architecture : les agents IA comprennent et coordonnent ; les services métier calculent, autorisent et exécutent.

A2A permet aux agents de se déléguer une demande. MCP leur donne accès à des outils définis. Temporal conserve la progression des opérations et organise les reprises. Un graphe relie les offres aux sources qui les expliquent.

Les essais documentent aussi un redémarrage du worker pendant l’attente du paiement, puis une délivrance avec un seul paiement et un seul chargement.

Ce premier article pose le socle. Les suivants observeront ce qu’il faut adapter pour :

• intégrer un service local et le distribuer sur plusieurs canaux ;
• remplacer un connecteur partenaire ;
• introduire un abonnement étudiant annuel ;
• explorer un portefeuille d’aides territoriales.

La finalité : construire des parcours cohérents pour l’habitant, tout en rendant les règles et les échanges entre opérateurs et financeurs explicites.

Je partagerai les évolutions du code, les composants réutilisés et les résultats des essais pour évaluer la souplesse de l’architecture.

Article : https://benjamin-maillard.fr/?article=maas-agentique-billettique-interoperable
Code et architecture : https://github.com/MaillardBenjamin/agentic-maas-lab

#Architecture #IA #Mobilité
