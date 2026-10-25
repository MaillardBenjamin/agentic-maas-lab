# Glossaire pour découvrir la pile

[Retour au dossier d’architecture](README.md)

| Notion | Explication et place dans ce projet |
|---|---|
| **MaaS** | *Mobility as a Service* : réunir plusieurs mobilités dans un même parcours. Le POC se concentre sur la billettique. |
| **Billettique** | Ensemble des fonctions d’offre, vente, délivrance, utilisation et contrôle des titres et droits d’accès. |
| **DSP** | Délégation de service public. Dans les plans du projet, désigne les acteurs et contrats d’exploitation concernés ; ce n’est pas un protocole informatique. |
| **Agent IA** | Logiciel associant un modèle, des instructions et des outils pour traiter une demande. Un agent n’est ni une autorité juridique ni un moteur de calcul exact. |
| **LLM / modèle de langage** | Modèle qui génère ou interprète du texte et peut proposer des appels d’outils. Ollama et OpenAI permettent ici d’en utiliser selon deux modes d’hébergement. |
| **Agno / AgentOS** | Framework de construction d’agents et couche qui les expose comme services. Leur présence ne remplace pas Temporal pour les opérations durables. |
| **API** | Interface d’appel d’un logiciel. Une demande structurée à l’API métier déclenche un traitement dont les entrées et droits sont contrôlés. |
| **A2A** | *Agent-to-Agent* : protocole permettant à un agent de découvrir ou solliciter un autre agent et d’échanger messages et résultats. Exemple : l’accueil délègue une question tarifaire. Ce n’est pas une permission d’agir. |
| **Agent Card** | Description publiée par un agent pour présenter ses capacités et son point d’accès. Elle ne prouve pas à elle seule l’identité ou la fiabilité de son éditeur. |
| **MCP** | *Model Context Protocol* : protocole qui décrit et expose des outils et ressources aux applications IA. Exemple : consulter le catalogue. MCP ne remplace ni les règles métier ni l’autorisation. |
| **A2A ou MCP ?** | A2A : « demande à cet agent spécialisé ». MCP : « appelle cet outil avec cette interface ». Un agent partenaire peut recevoir une demande A2A puis utiliser des outils MCP. |
| **GraphRAG** | Recherche de sources à l’aide d’un graphe pour alimenter une réponse générée. Le graphe représente des liens ; il ne rend pas automatiquement la réponse correcte. Ici, les vecteurs de recherche sont lexicaux locaux. |
| **Embedding** | Représentation numérique d’un contenu. Les embeddings sémantiques cherchent à représenter son sens ; ils ne sont pas utilisés dans la recherche actuelle, qui encode des mots. |
| **Moteur déterministe** | Code qui applique des règles explicites et reproductibles. Ici : prix, réductions, commissions, transitions et contrôles. |
| **OPA** | *Open Policy Agent* : moteur évaluant des politiques d’autorisation. Dans le POC, il décide si une régularisation SAV est permise. |
| **JWT** | Jeton signé transportant des informations d’identité et de périmètre. Le serveur doit vérifier sa signature et sa validité. Signé ne signifie pas chiffré : un JWT n’est pas un coffre à secrets. |
| **Workflow durable** | Processus dont la progression et les attentes sont conservées pour permettre une reprise après interruption. Temporal fournit cette capacité. |
| **Temporal** | Moteur d’orchestration durable : coordonne les étapes et conserve un historique permettant de reprendre un processus interrompu. Voir [le chapitre dédié](temporal.md). |
| **Workflow / exécution** | Le workflow définit le déroulement d’un processus ; une exécution est un cas concret, par exemple l’achat d’une commande identifiée. |
| **Worker** | Processus applicatif qui récupère des tâches Temporal et exécute le code des workflows et des activités. |
| **Activité** | Tâche effectuant une opération, notamment un appel API ou une écriture externe. Elle peut être réessayée ; son effet métier doit être protégé contre les doublons. |
| **File de tâches** | Point de distribution des tâches aux workers. Dans ce POC : `maas-ticketing`. Ce n’est pas un bus d’événements métier. |
| **Signal / query** | Un signal transmet une information au workflow, par exemple « paiement confirmé ». Une query interroge son état sans le modifier ; elle ne constitue pas un événement de l’historique. |
| **Minuterie durable** | Attente gérée par Temporal, conservée malgré l’arrêt du worker. Exemple : espacer les contrôles de statut bancaire. |
| **Historique / replay** | Temporal conserve les événements d’exécution. Le worker peut rejouer le code avec cet historique pour reconstruire l’état ; les résultats d’activités déjà enregistrés sont réutilisés. |
| **Retry / timeout** | Retry : nouvelle tentative selon une politique ; timeout : délai maximal applicable à une tentative ou une attente. Ils ne remplacent pas le rapprochement d’une opération incertaine. |
| **Idempotence** | Propriété permettant de répéter une demande identifiée sans répéter son effet métier. Exemple : retrouver le même chargement après une réponse perdue. |
| **CloudEvents** | Format commun pour l’enveloppe d’un événement : identité, source, type, date et données. Il ne définit pas le sens d’une validation ni une infrastructure de transport des messages. |
| **Sandbox** | Environnement d’essai d’un prestataire. Bridge Demo Bank reproduit un parcours bancaire sans argent réel. |
| **Stub / simulateur avec état** | Substitut logiciel à un équipement ou partenaire. « Avec état » signifie qu’il mémorise par exemple un stock, une réservation ou un chargement ; il ne renvoie pas toujours une réponse fixe. |
| **Open banking** | Dans ce POC, accès à un parcours d’initiation de virement bancaire via Bridge. À distinguer du paiement carte bancaire. |
| **Open payment EMV** | Dans le contexte transport, utilisation d’un support bancaire compatible EMV pour voyager. Ce parcours n’est pas réalisé ici. |
| **Prépayé / postpayé** | Paiement avant utilisation / facturation après utilisation. Ici, le vélo produit une créance simulée après usage, sans encaissement postpayé connecté. |
| **ACSC** | Statut de règlement attendu dans l’intégration Bridge. Le service vérifie aussi montant, devise et référence ; la lecture de ce seul mot dans une page ne suffit pas. |
| **Keyple / Calypso / SAM** | Keyple est un SDK d’accès aux cartes et lecteurs ; Calypso est une technologie de billettique. Un SAM est un module de sécurité pour les opérations cryptographiques. Le POC utilise une carte stub sans SAM réel. |
| **Blockchain** | Registre de transactions organisées en blocs reliés cryptographiquement. Un réseau et sa gouvernance peuvent permettre à plusieurs acteurs de vérifier des enregistrements communs. Cela ne garantit pas la vérité des données déposées. |
| **Anvil** | Logiciel qui fait fonctionner notre blockchain Ethereum locale de développement. Il démontre les transactions et l’ancrage, pas une gouvernance entre opérateurs indépendants. |
| **Ancrage** | Inscription d’une empreinte sur la blockchain pour disposer d’une référence de comparaison ; le document original reste ici hors chaîne. |
| **Smart contract** | Programme exécuté sur la blockchain. ProofRegistry conserve des empreintes ; le mot « contrat » ne désigne pas ici une signature d’abonnement par un étudiant. |
| **SHA-256 / empreinte** | Fonction produisant une empreinte à partir d’un contenu. Elle permet de comparer des versions ; elle ne chiffre pas le contenu et ne garantit pas sa véracité. |
| **Ed25519 / signature** | Algorithme de signature à clé privée, vérifiable avec la clé publique. Ici, il signe les manifestes du POC ; ce n’est pas un parcours de signature électronique qualifiée. |
| **OpenTelemetry / trace / Jaeger** | OpenTelemetry instrumente et transmet les traces ; une trace relie des étapes d’un traitement ; Jaeger permet de les consulter. La couverture du POC est partielle. |
| **Harness²** | Projet Google Research utilisé dans un laboratoire isolé de ce dépôt. Les expériences actuelles emploient des éditeurs déterministes et ne démontrent pas une amélioration de modèle. |
| **Docker Compose** | Description et lancement des services et volumes du démonstrateur. Démarrer les conteneurs ne suffit pas à qualifier un déploiement de production. |

Ces définitions donnent le sens retenu dans le dépôt. Les possibilités générales des produits ne doivent pas être confondues avec les fonctions effectivement intégrées.
