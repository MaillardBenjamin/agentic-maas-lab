# Vérifications locales — 24 octobre 2026

> État du premier socle avant activation des modèles. Les vérifications effectuées ensuite avec OpenAI, Bridge et Ollama sont dans le [rapport complémentaire](tests-ia-locale-et-acces-2026-10-24.md).

Première version exécutable du POC Alizé, sur Docker Desktop aarch64 / Mac Apple Silicon. Les résultats ci-dessous sont des observations locales, pas des résultats de production ni des mesures de qualité d'un modèle IA.

## Tests et parcours exécutés

| Vérification | Résultat observé |
|---|---|
| Tests Python | 34 réussis : tarifs, âge, droits expirés, arrondis, plafonds, commissions, encaissement absent, conditions postpayées acceptées, normalisation des recherches, contrôles Bridge, signatures Ed25519 et première création concurrente de clé |
| Politiques OPA | 5 tests réussis, dont dépassement de délégation et organisation différente |
| Contrat Solidity | 4 tests réussis : ancrage, lecture, répétition, conflit et appel non autorisé regroupés dans ces cas |
| Keyple / Java | 2 tests réussis lors de la construction Maven : sélection, écriture, relecture sur carte stub ; longueur de données invalide |
| Frontend | Compilation TypeScript et construction Vite réussies ; 214,88 kB JS / 67,68 kB gzip sur le dernier build observé |
| Achat de bout en bout | Réussi sur les services réels PostgreSQL, OPA, Temporal, Keyple et FalkorDB ; banque et carte physique simulées |
| Idempotence / concurrence | Paiement répété, commandes répétées, remboursements HTTP simultanés et doublons inter-fabricants sans second effet ; événements contradictoires refusés |
| Worker Temporal | Arrêt SIGKILL réel, signal reçu pendant son absence, redémarrage, première réponse de chargement volontairement perdue : paiement = 1, chargement = 1, rapprochement confirmé |
| A2A / MCP | Quatre Agent Cards, accueil Agno → agent tarifaire par A2A → outil MCP → API métier ; le modèle est un double déterministe explicitement étiqueté sans LLM |
| Ancrage | Manifeste signé Ed25519, vérification de l'empreinte, ancrage via Temporal et lecture du registre Anvil ; répétition sans nouvelle transaction ; manifeste altéré refusé |
| Redémarrage Anvil | Deux preuves persistées après redémarrage ; mêmes blocs de registre relus sans transaction supplémentaire |
| Sécurité | JWT absent, autre voyageur, autre organisation, remboursement non habilité, webhook non signé, OpenAI et Bridge désactivés : refus attendus ; panne réelle d'OPA : refus sans effet financier |
| OpenTelemetry | Trace `6a645a32cd34c15618891e091163af6f` observée dans Jaeger avec API et Worker dans une même trace ; absence des attributs sensibles interdits par le test |
| Harness² | Code officiel au commit `1cfe254e8d25b15f37048c3730134686abe60335`, deux tâches comptables fictives, modes parallèle et séquentiel ; éditeurs déterministes et aucune inférence de modèle |
| Interface | Présentation responsive inspectée ; devis étudiant de 12 €, confirmation, paiement simulé, pause puis délivrance vérifiés depuis le navigateur ; console et formulaire SAV consultés |
| Secrets | Scanner des sources réussi ; `.env` local en mode 0600, sans clés OpenAI ni identifiants Bridge renseignés lors du contrôle |

Total des tests Python, Rego, Solidity et Java : **45**, auxquels s'ajoutent les scénarios d'intégration ci-dessus. Un avertissement de dépréciation de `websockets.legacy` est remonté par une dépendance Python ; la suite reste réussie.

## Incident détecté et corrigé

Le premier redémarrage d'Anvil a révélé un volume root non inscriptible par l'utilisateur 1000 du nœud. Les ancrages initiaux avaient réellement été exécutés, mais le registre local n'avait pas été sauvegardé. La configuration a été corrigée pour ce nœud de développement isolé. Les anciennes références ont été conservées hors chaîne et les manifestes vérifiés puis réancrés ; la console distingue cette remise à zéro d'un simple redémarrage.

Instance de reprise observée : `72929acb7bbe45af9ab76b44af6ffe9e`. Le registre persisté a ensuite été vérifié après un nouveau redémarrage, avec deux preuves et sans nouvelles transactions. Les snapshots Anvil ne sont pas présentés comme une archive exhaustive de toutes les transactions Ethereum.

## Limites de ces résultats

Aucun appel OpenAI payant, aucun parcours bancaire Bridge et aucun mouvement d'argent réel. La voix, la génération de réponses par modèle, les embeddings sémantiques OpenAI, les justificatifs réels, l'identité numérique nationale et la propagation des traces aux agents restent à valider ou à compléter. Les identités et partenaires sont fictifs. Aucun SAM, valideur physique, automate matériel ni titre utilisable sur un réseau réel.

Le laboratoire Harness² prouve l'exécution de son mécanisme avec des éditeurs scriptés ; il ne démontre aucune amélioration mesurée d'agent IA. La définition GitHub Actions est fournie, mais n'a pas été exécutée sur GitHub ; Linux reste à tester.

Les commandes pour reproduire les scénarios sont dans le [README](../README.md) et le [Makefile](../Makefile). Les derniers résultats de laboratoire sont générés localement dans `artifacts/harness2/maas-report.json`, exclu de Git.
