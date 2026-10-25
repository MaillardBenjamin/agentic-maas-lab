# Comprendre les parcours et les échanges

[Retour au dossier d’architecture](README.md)

Les diagrammes décrivent des parcours simplifiés du code actuel. Les variantes d’erreur et les détails HTTP sont expliqués dans les rapports d’essai liés à chaque section.

## 1. Une question tarifaire : comprendre, déléguer, consulter

Le voyageur demande pourquoi le transport étudiant coûte 7 €. L’accueil délègue à l’agent tarifaire par A2A. Celui-ci utilise MCP pour consulter le catalogue et rechercher les sources. Les outils reviennent aux API métier avec l’identité du demandeur.

```mermaid
sequenceDiagram
    actor V as Voyageur
    participant UI as Interface
    participant API as API métier
    participant A as Agent accueil
    participant T as Agent tarifs
    participant M as Serveur MCP
    participant G as FalkorDB
    V->>UI: Pourquoi le tarif étudiant est-il de 7 euros ?
    UI->>API: Demande authentifiée
    API->>A: A2A : message à l’accueil
    A->>T: A2A : délégation tarifaire
    T->>M: MCP : lire le catalogue
    M->>API: API : catalogue structuré
    API-->>M: Produits et règles versionnés
    M-->>T: Résultat outil
    T->>M: MCP : rechercher les sources
    M->>API: API : recherche documentaire
    API->>G: Recherche et liens du graphe
    G-->>API: Passages et références
    API-->>M: Sources retrouvées
    M-->>T: Résultat outil
    T-->>A: Explication et références
    A-->>API: Réponse à la demande
    API-->>UI: Texte et outils observés
    UI-->>V: Affichage de l’explication
```

Le dialogue explique l’offre ; les contrôles métier de l’interface permettent ensuite d’obtenir le devis et de confirmer la commande. Dans le catalogue fictif, le moteur choisit la meilleure réduction admissible sans cumuler les remises.

**À retenir :** A2A sert à déléguer ; MCP sert à consulter ; le moteur métier reste responsable du montant.

## 2. Un paiement QR sur la borne : attendre une preuve bancaire

La borne crée une commande à partir du devis confirmé. L’API démarre le workflow d’achat. Un lien Bridge sandbox est ensuite créé et présenté sous forme de QR code. La confirmation du virement a lieu sur la page bancaire, dans une session distincte.

```mermaid
sequenceDiagram
    actor V as Voyageur
    participant B as Borne simulée
    participant API as API métier
    participant T as Temporal et worker
    participant BK as Bridge Demo Bank
    participant C as Simulateur et Keyple stub
    V->>B: Confirmer devis et mode Bridge
    B->>API: Créer la commande
    API->>T: Démarrer PurchaseAndIssue
    Note over T: Attend le signal de paiement
    B->>API: Demander le lien Bridge
    API->>BK: Créer un paiement sandbox
    BK-->>API: Lien public
    API->>T: Démarrer BankPaymentWatch
    API-->>B: Lien encodé en QR
    V->>BK: Ouvrir le lien et autoriser le virement fictif
    loop Suivi borné à 15 minutes
        T->>API: Activité de contrôle bancaire
        API->>BK: Relire le statut côté serveur
        BK-->>API: Statut et transaction
    end
    Note over API: ACSC + montant + EUR + référence concordants
    API->>API: Persister un paiement unique
    API->>T: Signaler payment_confirmed
    T->>C: Charger avec une identité d’opération stable
    C-->>T: Écriture et relecture vérifiées
    T->>API: Enregistrer la délivrance
    B->>API: Lire l’état de la commande
    API-->>B: Commande délivrée
    B-->>V: Carte simulée prête
```

Le lien de borne expire après 10 minutes ; la surveillance serveur possède une fenêtre de 15 minutes. Après cette fenêtre, un contrôle manuel est nécessaire. Une réponse bancaire incertaine n’autorise pas à recréer aveuglément un paiement.

La borne peut fermer son écran sans effacer la commande ni arrêter le workflow. Aucun appel d’agent IA n’est requis pour confirmer ce paiement. Le terminal CB proposé comme autre mode reste une simulation locale distincte.

**À retenir :** ouvrir un QR ou revenir sur une page de succès ne suffit pas ; seule la vérification bancaire déclenche la délivrance. Voir [le test complet du parcours](../automate-qr-2026-10-25.md).

## 3. Réserver un vélo : coopérer avec un partenaire

Après délivrance de la commande, le voyageur confirme une opération dans l’interface. Le service crée une opération durable. Pendant son traitement, il fournit une autorisation temporaire limitée à cette action.

```mermaid
sequenceDiagram
    actor V as Voyageur
    participant API as API métier
    participant T as Temporal et worker
    participant M as Agent coordination MaaS
    participant P as Agent partenaire vélo
    participant MCP as MCP partenaire
    participant S as Service partenaire simulé
    V->>API: Confirmer la réservation
    API->>API: Vérifier les droits et enregistrer l’opération
    API->>T: Démarrer PartnerInteraction
    T->>API: Activité de délégation
    API->>M: A2A avec autorisation temporaire
    M->>P: A2A : déléguer au partenaire
    P->>MCP: MCP : consulter la disponibilité
    MCP->>S: API : lecture du stock fictif
    S-->>MCP: Disponibilité
    MCP-->>P: Résultat outil
    P->>MCP: MCP : appliquer l’action confirmée
    MCP->>S: API : vérifier autorisation et transition
    S->>S: Transaction : stock et reçu
    S-->>MCP: Résultat métier persistant
    MCP-->>P: Reçu
    P-->>M: Résultat de délégation
    M-->>API: Réponse A2A
    API-->>T: État métier vérifié
    V->>API: Consulter le résultat
    API-->>V: Réservation confirmée ou refusée
```

Le runtime impose une consultation de disponibilité avant l’écriture, même si le modèle omet cet appel. Les paramètres d’action sont fixés par le service, pas par le texte du modèle. Le stock détermine l’acceptation de la réservation ; le reçu enregistré constitue la confirmation affichée.

Lors d’une fin d’usage, le service produit aussi un événement CloudEvents dans la transaction métier. Les agents coopèrent en A2A ; les remontées de validation utilisent le flux d’événements.

Voir [les cycles partenaires, la concurrence et les reprises](../partenaires-a2a-2026-10-24.md).

## 4. Après les validations : constituer une preuve

Les événements acceptés sont conservés dans PostgreSQL. Une demande d’ancrage constitue un manifeste de lot contenant types, dates et empreintes métier. Le POC signe ce manifeste en Ed25519. Temporal fait ensuite inscrire son empreinte SHA-256 dans le contrat local ProofRegistry sur Anvil.

Le manifeste reste hors chaîne. La console montre l’empreinte, le bloc, le réseau local et l’instance de déploiement ; la date du bloc est affichée en heure de Paris lorsqu’elle est disponible. Une comparaison ultérieure permet de détecter un manifeste modifié. Les contrôles métier vérifient les conditions d’acceptation ; l’ancrage permet de vérifier l’intégrité du lot conservé.

Une panne d’Anvil ne doit pas empêcher le traitement des validations : le workflow d’ancrage peut être repris séparément.
