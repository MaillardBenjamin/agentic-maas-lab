# Guide de démonstration

Parcours du **29 octobre 2026**, après [démarrage et chargement du catalogue](../README.md#démarrer). Ouvrir [Alizé Lab](http://127.0.0.1:5190). Les montants ci-dessous sont ceux du catalogue de démonstration ; les écrans recalculent les conditions selon le profil et la date.

## 1. Voyageur : acheter et retrouver ses titres

1. Choisir **Voyageur**, puis Léa ou Alex et **Se connecter en démonstration**. Aucun mot de passe personnel n’est nécessaire.
2. Dans **Acheter**, ajouter Transport, Parking ou Vélo. Dans **Panier**, vérifier les produits, la date et le détail du prix. Pour Léa avec un droit étudiant valide, Transport et Parking donnent 7 € + 5 € à payer ; le Vélo est facturé après usage.
3. Choisir la simulation locale ou Bridge Demo Bank lorsque ce connecteur est configuré. Accepter le récapitulatif et confirmer. La commande existe alors ; elle n’est pas encore payée.
4. Effectuer le paiement sur l’écran suivant. Pour Bridge, c’est la relecture du statut bancaire par le serveur qui confirme le règlement. Attendre la délivrance et sa relecture sur carte stub.
5. Dans **Mes titres**, retrouver les commandes et leur état, y compris celles du même voyageur effectuées sur d’autres canaux. Dans **Mes services**, confirmer séparément chaque réservation, démarrage ou fin d’usage Vélo/Parking.

Une commande en attente, un paiement confirmé et un titre délivré sont trois états distincts. Si une confirmation reste incertaine, utiliser l’action de reprise affichée pour retrouver la même opération.

## 2. Aide : consulter, préparer une offre et vérifier ses achats

Dans **Aide**, sélectionner éventuellement une commande, puis envoyer une question. Les agents texte nécessitent un fournisseur activé, [Ollama ou OpenAI](exploitation-et-verification.md#options-de-dialogue-et-de-perception).

| Exemple de demande | Ce que l’on peut montrer |
|---|---|
| « Peux-tu me donner le tarif du parking ? » | Routage vers Tarifs puis Parking, sans commande préalable. |
| « Y a-t-il une place disponible au parking ? » | Consultation de disponibilité ; elle ne réserve pas la place. |
| « Prépare une proposition transport, parking et vélo pour le 2026-11-01. » | Consultation des fournisseurs puis devis calculé. Adapter la date à celle de la démonstration. |
| « Mes achats » | Historique limité au voyageur autorisé. |
| « Mon compte mobilité » | Lecture du compte ABT et de ses échéances via l’outil dédié. |
| « Vérifie les preuves de ma commande » avec une commande sélectionnée | Consultation des sources métier, signature et chaîne locale active. |

Pour une offre, **Examiner la proposition** ouvre le parcours métier : vérifier les produits et la date, puis confirmer dans cet écran. Le dialogue ne réalise ni achat, ni prélèvement, ni remboursement.

Le panneau **Échanges en direct** montre les échanges réellement observés : appel A2A, lecture MCP, début, fin et durée. Plusieurs fournisseurs peuvent être consultés en parallèle ; la synthèse attend les résultats. Les scénarios de protocole déclarent explicitement leur double de modèle. Une question ambiguë peut demander une précision avant tout appel.

Une preuve vérifiée atteste l’intégrité du contenu enregistré. Elle ne remplace pas la confirmation du paiement. Une ancienne commande sans preuve, une preuve en attente ou une chaîne indisponible doivent rester présentées avec cet état. Voir [le détail des contrôles](routage-achats-preuves-2026-10-29.md).

## 3. Compte mobilité : abonnement et post-paiement ABT

Ouvrir **Compte mobilité** dans Voyageur. Les achats classiques identifiés sont rattachés au compte ; leur support carte et leurs conditions restent conservés.

| Offre transport ABT | Conditions de démonstration |
|---|---|
| Abonnement annuel | 600 €, douze mensualités de 50 €, trajets inclus pendant un an. |
| Post-paiement | 2 € par trajet, plafond de 60 € par mois civil UTC, facturation du mois clos le mois suivant. |

Choisir une offre et une date de début, relire les conditions et cocher l’accord au prélèvement simulé. Confirmer la souscription, puis consulter le droit et les échéances. Deux contrats transport ABT ne peuvent pas se chevaucher ; les offres transport unitaires et les services partenaires restent séparés.

**Simuler un trajet** vérifie le droit du compte et enregistre un usage. Le worker traite les échéances exigibles et les mois clos ; **Actualiser mon compte** relit les résultats. Une échéance échouée peut proposer une régularisation simulée. Ne pas avancer l’horloge de la machine pour présenter les mois futurs : les scénarios calendaires dédiés le font en environnement de test isolé.

Les nouveaux droits ABT restent sur le compte, sans chargement Keyple. Les mensualités et encaissements ABT sont simulés. Le journal ABT reste hors chaîne ; les preuves du cycle de vie décrites pour les commandes classiques ne constituent pas une preuve blockchain de ces prélèvements. Voir [les règles ABT et leurs limites](abt-transport-2026-10-29.md).

## 4. Agence en gare ou centre de relation client

Ouvrir **Agence & SAV** et choisir le contexte gare ou CRC et le profil conseiller disponible. Rechercher un voyageur ou une référence, puis sélectionner le dossier. La consultation et la vente doivent porter sur ce bénéficiaire, même lorsque le conseiller agit.

Présenter une vente accompagnée, les commandes et titres, puis un dossier de contact : motif, notes et fermeture. Pour une régularisation, vérifier la commande payée, le montant restant et l’habilitation ; le conseiller dispose d’une limite de 5 € dans la politique actuelle. Un refus ne produit aucun effet financier. Le CRC utilise le même poste avec son contexte de relation client. Voir [le parcours détaillé](poste-agence-crc-2026-10-28.md).

## 5. Automate et console

**Automate** démarre par une présentation de carte fictive. Choisir les produits, examiner le devis, payer par QR Bridge sandbox ou terminal simulé, attendre le chargement et récupérer la carte. L’historique des autres achats n’est pas affiché sur la borne.

**Console** permet d’examiner les états techniques, les événements, les commissions et les lots de preuves. Les montants prépayés, régularisations et créances après usage restent distincts. Après `make proofs`, les lots peuvent être ancrés dans Anvil ; la vente et la validation n’attendent pas cet ancrage.

## 6. Webcam et audio facultatif

Dans l’assistant, ouvrir **Webcam et reconnaissance labiale**. Choisir Audio + lèvres ou Lèvres seules, puis démarrer la webcam et autoriser les appareils dans le navigateur. L’analyse locale traite une courte phrase, avec un résultat différé à relire et corriger avant envoi.

L’option **Ajouter l’audio OpenAI en direct** est décochée par défaut. Après accord explicite, elle transmet le son et les textes nécessaires au dialogue ; aucune image n’est envoyée à OpenAI. L’interface n’offre aucun import de fichier vidéo. La lecture labiale seule reste imprécise dans l’essai public documenté ; les tests de transport ne constituent pas une validation de précision avec un micro et une webcam physiques. Voir [le parcours et les vérifications](webcam-audio-local-2026-10-28.md).
