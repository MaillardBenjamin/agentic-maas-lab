# Borne : QR Bridge sandbox et terminal CB simulé

## Parcours réalisé

La borne propose avant création de la commande deux modes explicites :

- **QR Bridge sandbox** : un lien Pay by Link public ouvre la Demo Bank sur le téléphone. La passerelle initie un virement, sans acquisition CB et sans argent réel.
- **Terminal CB simulé** : acquittement local du paiement fictif, sans PSP ni appel bancaire. Le terminal dessiné reste décoratif.

Les commandes sans prépaiement (vélo seul) utilisent une confirmation explicite à 0 €, sans création d’un virement à zéro.

Le QR est encodé côté navigateur avec qrcode.react 4.2.0. Seules les URL HTTPS du domaine exact `pay.bridgeapi.io`, sans identifiants intégrés, sont affichées. Le QR ne contient aucun secret API, JWT ou adresse locale du Mac. Pour une commande automate, le callback localhost est omis : le téléphone reste sur la confirmation Bridge publique.

Le lien expire après 10 minutes. Pendant sa validité, la session d’écran reste ouverte, avec possibilité de fermeture volontaire. La fermeture ne supprime ni la commande ni un virement engagé. Les autres écrans reviennent à l’accueil après deux minutes d’inactivité.

## Confirmation et reprise

`BankPaymentWatch`, identifié par `bank-watch-{order_id}`, consulte la banque via une activité Temporal et un endpoint interne authentifié. La surveillance démarre après persistance du lien et reprend après redémarrage du worker. Le bouton de reprise réutilise ce lien et ce workflow ; il ne recrée pas une demande bancaire incertaine.

Le statut de la banque et l’heure du dernier contrôle sont persistés. Seul `ACSC`, avec référence de commande, montant exact, devise EUR et transaction unique concordants, enregistre un paiement et signale le workflow de délivrance. Un QR scanné, un lien marqué terminé, un retour navigateur ou un bouton de contrôle ne remplacent pas ce règlement. L’endpoint de paiement local refuse une commande Bridge.

La surveillance est bornée à une fenêtre de 15 minutes, avec contrôles espacés de cinq secondes et reprises bornées des erreurs transitoires. Un refus arrête le suivi automatique. Un règlement tardif après la fenêtre nécessite un contrôle manuel dans le dossier de la vue Voyageur ; le dossier est également accessible à l’agence selon ses habilitations. Aucun nouveau virement ne doit être créé pour remplacer une tentative incertaine. Cette surveillance est prévue pour le démonstrateur, sans webhook public connecté.

## Vérifications du 25 octobre 2026

- 76 tests Python (dont 3 décisions du workflow bancaire), 12 tests d’état du frontal ; compilation TypeScript et build Vite.
- Achat depuis les contrôles visibles de la borne : Léa, transport + parking + vélo, 12 €.
- QR réellement affiché puis décodé depuis sa capture par un décodeur indépendant (`zxing-cpp`, conteneur temporaire). Résultat identique au lien Bridge. Pas de test avec une caméra de téléphone physique.
- Page publique Bridge : même montant, environnement de test. Validation dans un onglet bancaire distinct, avec identifiants et code SMS fictifs Demo Bank ; acceptation des conditions explicitement autorisée par l’utilisateur pour cet essai.
- Avant règlement : `CREA`, puis `ACTC`, aucun paiement enregistré, aucune carte délivrée. Paiement simulé refusé pour cette commande ; endpoint interne inaccessible sans authentification de service.
- Redémarrage du worker pendant l’attente : reprise des contrôles, puis statut `ACSC`, commande `fulfilled`, un paiement, un chargement, relecture Keyple vérifiée. La borne a affiché le succès automatiquement, sans action sur « Vérifier le statut bancaire ».
- Téléphone : la confirmation reste sur Bridge ; aucune redirection vers localhost. Ce comportement a été vérifié dans l’onglet bancaire, pas sur un appareil physique.

Commande : `order-4d9c89fbe1168ce086a2f38f52d317dc`.

Preuves : [état métier](evidence-automate-qr-2026-10-25.json), [écran QR](ihm-automate-qr-2026-10-25.png), [succès](ihm-automate-qr-succes-2026-10-25.png).

Le bénéficiaire « Your Company » et la marque « Oenotrac App » proviennent de l’application sandbox existante. Aucun paramètre de ce compte n’a été modifié. Cartes, lecteurs et terminal physique restent simulés. Le nouveau mode CB n’a pas fait l’objet d’un second achat visuel complet ce jour ; le parcours local antérieur est documenté dans [le rapport de la borne](automate-ihm-2026-10-24.md).

Références : [Bridge : premier paiement et callback facultatif](https://docs.bridgeapi.io/docs/create-your-first-payment-api), [tests Demo Bank](https://docs.bridgeapi.io/docs/testing-your-payment-flow), [qrcode.react](https://github.com/zpao/qrcode.react).
