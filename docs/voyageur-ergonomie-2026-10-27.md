# Voyageur — connexion, panier et espace client

La vue Voyageur simule un espace client web/mobile. Les profils, paiements locaux, cartes et services restent ceux du POC. L’authentification est une sélection explicite de compte fictif, sans mot de passe et sans nouvelle intégration d’identité.

## Parcours

1. Choisir Léa ou Alex et cliquer sur **Se connecter en démonstration**.
2. Dans **Acheter**, ajouter les produits souhaités. Le panier démarre vide ; l’offre transport + parking + vélo n’est plus imposée.
3. Dans **Panier**, retirer des produits, choisir la date d’utilisation, consulter les réductions et le montant calculés par le serveur. L’usage du vélo reste distinct du prépaiement.
4. Choisir la simulation locale ou Bridge Demo Bank si la sandbox est configurée. Accepter explicitement le contenu et le prix avant **Confirmer ma commande**.
5. Effectuer le paiement depuis le suivi de la commande. Le chargement est suivi automatiquement ; le succès attend le paiement et la relecture vérifiée de la carte stub.
6. **Mes titres** réunit les commandes du site et de la borne pour le compte connecté. **Mes services** présente les accès vélo/parking délivrés. **Aide** donne accès à l’assistant, avec contexte de commande optionnel.
7. La déconnexion efface panier et données de session à l’écran ; les commandes restent dans PostgreSQL. Une nouvelle connexion retrouve uniquement les commandes autorisées du profil choisi.

Les prix publics du catalogue ne sont pas des prix personnalisés. Le devis `/api/quotes` utilise les produits sélectionnés, la date choisie et le vendeur `app` (commission 2 %). Une modification du panier ou de la date invalide le devis et son consentement. Les réglages de commission, la pause technique et les traces d’implémentation ne font plus partie de l’achat Voyageur.

Les quantités restent limitées au modèle métier existant : un accès par type de produit pour le voyageur connecté. Le panier et la session sont en mémoire ; recharger la page revient à la connexion. Il ne s’agit pas d’une session client persistante ni d’un panier stocké côté serveur.

## Vérifications effectuées

- Construction Docker du frontal : TypeScript et Vite réussis.
- Tests du frontal : **17 réussis** (12 tests borne existants et 5 tests Voyageur). Les nouveaux contrôles couvrent le devis d’un autre panier, profil, vendeur ou date, les sélections vides/dupliquées et la délivrance avec paiement et relecture confirmés.
- Inspection visuelle à 320 px dans le navigateur intégré et à 1 512 px dans Chrome : connexion, catalogue, panier, suivi et espace client.
- Connexion Léa, ajout des trois produits et affichage du devis de 12 €.
- Confirmation cochée, retrait du parking : ancien devis et consentement invalidés. Date passée au 1er septembre 2027 : droit étudiant expiré, règle moins de 26 ans appliquée, transport à 8 €. Retour au 27 octobre 2026 : transport à 7 €.
- Achat depuis le navigateur de transport + vélo, **7 € prépayés**, paiement local simulé et succès affiché automatiquement. Commande `order-2b28d859377c73939e6a38690ef55e0c` : canal `web`, vendeur `app`, état `fulfilled`, `payment_count=1`, `load_count=1`, `verified_read_after_write=true`, contrôlés également côté API.
- Achat vélo seul pour Alex : commande `order-faf1c8672f7f8d4291a04484efc81ea3`, prépaiement à 0 €, mode local, état `fulfilled`, un chargement et relecture confirmée. Aucun virement à zéro créé.
- Accès à Mes services pour la commande Léa : accès vélo présent, action de réservation soumise à confirmation. Aucun nouvel appel au modèle n’a été nécessaire à ce contrôle.
- Navigation vers Automate et Agence/SAV : écrans existants accessibles, sans démarrage d’un autre achat par ces écrans.
- Déconnexion puis connexion Alex : panier vide et commandes propres à Alex, sans affichage de la nouvelle commande Léa.

Aucun nouveau paiement Bridge ni appel OpenAI n’a été effectué pour cette refonte. La réception des notifications bancaires et la voix conservent leurs limites documentées. Les erreurs de réseau, l’expiration de session et les confirmations incertaines disposent de traitements dans le code ; ces incidents n’ont pas tous été provoqués dans le navigateur durant cette vérification.

Captures : [connexion ordinateur](ihm-voyageur-login-2026-10-27.jpg), [panier ordinateur](ihm-voyageur-panier-2026-10-27.jpg).
