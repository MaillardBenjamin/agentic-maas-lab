# Comprendre les parcours et les échanges

[Retour au dossier d’architecture](README.md)

Les diagrammes décrivent des parcours simplifiés du code actuel. Les variantes d’erreur et les détails HTTP sont expliqués dans les rapports d’essai liés à chaque section.

## 1. Une question tarifaire : consulter l’organisation responsable

Le voyageur demande « Peux-tu me donner le tarif du parking ? ». L’accueil transmet sa question au coordinateur Tarifs, qui consulte l’agent de l’organisation Parking via A2A. Cette consultation ne nécessite ni achat ni confirmation d’une réservation.

L’API qualifie d’abord l’intention et le service dans un plan signé. Le runtime vérifie les compétences déclarées et le périmètre avant les appels. Une commission limitée au Parking sollicite uniquement Commissions puis Parking, même si la commande contient aussi Transport et Vélo. Une demande ambiguë appelle une précision. L’historique d’achats suit un autre parcours : Accueil → Achats → outil de consultation du voyageur autorisé, sans fournisseur. Voir [les contrôles et essais](../routage-achats-preuves-2026-10-29.md).

```mermaid
sequenceDiagram
    actor V as Voyageur
    participant A as Accueil
    participant T as Coordinateur Tarifs
    participant P as Agent Parking
    participant M as MCP fournisseur
    participant S as Services métier Parking
    V->>A: Quel est le tarif du parking ?
    A->>T: A2A : question complète
    T->>P: A2A : délégation de lecture limitée à Parking
    P->>M: read_provider_context
    M->>S: Identité + délégation signée
    S->>S: Lire offres, règles et sources Parking
    S-->>P: Tarif, conditions et références via MCP
    P-->>T: Réponse de l’organisation Parking
    T-->>A: Synthèse sourcée
    A-->>V: Tarif et conditions
```

Pour une offre combinée, le coordinateur consulte chaque organisation concernée. `prepare_offer` consulte les fournisseurs puis appelle le moteur déterministe pour préparer un devis à une date explicite. Le contexte signé fixe le voyageur et le vendeur ; les produits et la date restent examinables dans l’écran Voyageur ou Agence. Le bouton « Examiner la proposition » ouvre cet écran, où le consentement doit encore être donné. Aucun achat ni réservation n’est exécuté par cette préparation.

Le SAV utilise les mêmes délégations de lecture pour consulter uniquement les lignes, réservations et usages de chaque fournisseur dans la commande sélectionnée. Le coordinateur Commissions consulte les contrats et parts de chaque fournisseur ; le relevé global reste calculé par les services métier. Une indisponibilité fournisseur n’autorise pas à présenter une réponse inventée comme confirmée.

Les consultations indépendantes des fournisseurs sont lancées en parallèle, avec au plus trois appels A2A fournisseurs en cours par consultation. La lecture du relevé global pour Commissions, ou des règles MaaS pour le SAV, démarre également sans attendre les retours fournisseurs. La synthèse attend tous les résultats ; un échec fait échouer la consultation complète. La préparation du devis et les étapes d’exécution qui dépendent de résultats précédents conservent leur ordre. Voir [la validation du parallélisme](../consultations-paralleles-2026-10-29.md).

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
    participant M as Exécution MaaS confirmée
    participant P as Opérations vélo confirmées
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

## 5. Un titre ABT : conserver le droit dans le compte

Le voyageur choisit une offre annuelle mensualisée ou un post-paiement plafonné, puis confirme les conditions et le prélèvement simulé. L’API lie le compte au bénéficiaire autorisé et conserve le contrat et les échéances dans une transaction. Aucun titre ABT n’est chargé par Keyple.

```mermaid
sequenceDiagram
    actor V as Voyageur
    participant UI as Compte mobilité
    participant API as Services métier ABT
    participant DB as PostgreSQL
    participant W as Worker
    V->>UI: Offre, date et consentement
    UI->>API: Souscription avec clé d’idempotence
    API->>DB: Compte, contrat et échéancier atomiques
    API-->>UI: Droit et échéances
    V->>UI: Simuler un trajet
    UI->>API: Identité du passage et horodatage
    API->>DB: Vérifier le droit, dédupliquer et plafonner
    W->>API: Traitement périodique de facturation
    API->>DB: Échéances exigibles et prélèvements simulés
    UI->>API: Actualiser le compte
    API-->>UI: Usages, factures et état du droit
```

Un impayé suspend le droit ; une régularisation simulée peut le réactiver si aucun autre impayé ne subsiste et si la validité le permet. Le journal ABT reste hors chaîne. Les achats classiques rattachés au même compte conservent leur support carte et leur propre cycle de preuves. Voir [les règles ABT](../abt-transport-2026-10-29.md) et [l’audit des tests](../audit-tests-abt-2026-10-29.md).
