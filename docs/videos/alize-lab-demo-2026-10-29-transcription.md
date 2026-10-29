# Démonstration Alizé Lab

Captures réelles du 29 octobre 2026, voix de synthèse locale française, montage avec attentes raccourcies. Données et opérations de démonstration.

## Bienvenue dans Alizé Lab

Alizé Lab réunit les parcours du voyageur, de la borne et du conseiller. Ce prototype de billettique utilise des données fictives, des paiements de démonstration et des équipements simulés.

## Composer son panier

Le voyageur choisit son profil de démonstration. Il retrouve le transport, le parking et le vélo dans un même espace, puis compose son panier.

## Un prix calculé par les règles métier

Le tarif est recalculé selon le profil et la date. Pour Léa, le transport étudiant revient à sept euros. Avec le parking, le montant à payer est de douze euros. Le voyageur confirme le récapitulatif.

## Commande, paiement, délivrance

La commande est enregistrée. Le paiement constitue une étape séparée. Pour cette démonstration, nous utilisons la simulation locale, sans débit bancaire.

## Un titre chargé et relu

Après confirmation du paiement, Temporal pilote la délivrance. Le service Keyple charge la carte simulée et la relit. L’écran confirme alors que les titres sont disponibles.

## Le compte mobilité ABT

Le compte mobilité rassemble aussi les droits conservés côté serveur. Deux offres transport sont proposées : un abonnement annuel à six cents euros, ou un post-paiement à deux euros par trajet, plafonné à soixante euros par mois.

## Droits et échéances visibles

Le compte affiche les achats rattachés, la validité du droit et les échéances. Ici, l’abonnement annuel comporte douze mensualités de cinquante euros. Les prélèvements sont simulés et restent distincts d’un encaissement bancaire réel.

## Poser une question aux agents

Dans Aide, le voyageur pose sa question. Nous demandons le tarif du parking. Le système sélectionne le coordinateur et l’organisation compétente avant de les consulter.

## Voir les échanges pendant l’exécution

Le panneau Échanges en direct expose les appels réellement observés. L’accueil délègue au coordinateur Tarifs, qui consulte l’agent Parking. Celui-ci appelle son outil métier. Cette séquence utilise le modèle local Ollama.

## Une réponse issue des outils métier

La réponse revient dans l’assistant avec ses références. Les agents expliquent et coordonnent. Les services métier restent responsables des prix, des droits et des opérations confirmées.

## Un poste conseiller en gare

Le poste Agence et service après-vente permet de rechercher un voyageur, retrouver ses commandes et accompagner une vente. Le conseiller agit sur le bénéficiaire sélectionné, dans le cadre de ses habilitations.

## Le même dossier au centre de relation client

Le contexte centre de relation client donne accès au suivi de la demande, aux dossiers de contact et aux notes. Le conseiller dispose ainsi d’un poste de relation client, au-delà d’un simple assistant conversationnel.

## Un parcours dédié à la borne

La borne conserve son propre parcours : présenter une carte fictive, choisir ses produits, payer dans l’environnement de test, puis attendre la délivrance avant de récupérer sa carte.

## Webcam locale, audio facultatif

La capture vidéo utilise uniquement la webcam. La reconnaissance audiovisuelle est locale et son texte doit être relu. OpenAI peut aider pour le dialogue audio, après activation explicite ; aucune image ne lui est transmise.

## Des parcours réunis, des responsabilités claires

Alizé Lab relie les interfaces, la coopération entre agents et les traitements métier. Les guides et rapports de tests du dépôt précisent les fonctions vérifiées et les limites à qualifier.