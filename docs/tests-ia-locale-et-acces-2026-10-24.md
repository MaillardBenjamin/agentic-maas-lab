# Tests OpenAI, Bridge et Ollama — 24 octobre 2026

Ces essais complètent le [premier rapport du socle](validation-2026-10-24.md). Les secrets sont chargés depuis `.env`, sans apparaître dans les sources, sorties des diagnostics ou ce document.

**Complément effectué ensuite le même jour :** le [paiement Bridge complet](test-paiement-bridge-2026-10-24.md) a depuis été validé jusqu'à la délivrance du titre. Les constats d'authentification seule ci-dessous décrivent l'étape précédente. La configuration finale conserve Ollama et active Bridge sandbox.

## Accès externes

| Essai réel | Résultat |
|---|---|
| OpenAI, lecture du modèle `gpt-6-luna` | HTTP 200 ; accès authentifié au modèle |
| Bridge sandbox, `GET /v3/payment/payment-requests?limit=1` | HTTP 200 ; aucun paiement retourné ; aucune création de paiement |
| Ollama natif, API accessible depuis Docker | HTTP 200 ; serveur 0.32.1, modèle `qwen3:14b`, capacités completion/tools/thinking |

L'authentification Bridge ne prouve pas le parcours de paiement complet. Le bénéficiaire de test et les notifications restent à configurer. Aucun mouvement d'argent n'a été déclenché. Les messages d'erreur bruts des prestataires ne sont pas imprimés par le diagnostic.

## Parcours réels d'agents

Même question de test : expliquer le prix du titre transport pour un étudiant disposant d'un droit valide, consulter les outils puis citer la source.

| Fournisseur et modèle | Parcours observé | Résultat | Durée d'une exécution |
|---|---|---|---|
| OpenAI / `gpt-6-luna` | API → accueil Agno → A2A vers tarifs → MCP `read_catalog` et `search_tariffs` → API métier/FalkorDB | Réponse 7 €, réduction de 30 % sur une base de 10 €, source `tariff-1` | 9 661 ms |
| Ollama local / `qwen3:14b` | Même chaîne avec le fournisseur natif Ollama d'Agno | Réponse 7 €, source `tariff-1`, aucun double déterministe | 39 553 ms |

Les preuves d'exécution des outils proviennent d'en-têtes ajoutés par le runtime, pas d'une déclaration du modèle. Le contrôle vérifie également le fournisseur et l'identifiant de modèle. Il s'agit d'une exécution par mode, sans protocole de benchmark ni mesure de qualité générale ; ces temps ne constituent pas une garantie de latence.

OpenAI : une réservation applicative conservatrice de 100 centimes a été enregistrée pour le parcours. Ce n'est pas une mesure de la facture réelle. Ollama : réservation supplémentaire de **0 centime**, aucune requête OpenAI dans cette chaîne. Aucune session audio n'a été ouverte ; la voix et sa latence restent à tester.

## Configuration locale retenue

Le Mac dispose de 24 Go de mémoire. Le modèle `qwen3:14b` était déjà installé : empreinte de version `bdbd181c33f2`, environ 9,3 Go de poids. Aucun téléchargement de modèle supplémentaire.

Les agents Docker utilisent le serveur natif `http://host.docker.internal:11434`, avec un contexte de 8 192 tokens, une sortie limitée à 700 tokens et la réflexion désactivée pour ces essais. Le fournisseur est explicitement `Ollama`. Les URL et identifiants de modèles cloud sont refusés ; aucun basculement vers OpenAI n'est prévu en cas de panne locale.

Le mode **Ollama est laissé actif** dans la configuration locale. Les clés OpenAI et Bridge sont préservées ; le paiement Bridge reste désactivé. Le frontal identifie les réponses locales et affiche les outils MCP et la délégation A2A réellement observés. En mode local, le bouton vocal OpenAI est désactivé.

## Vérifications automatiques

La suite Python comprend maintenant **45 tests réussis**, dont 11 nouveaux contrôles du choix de fournisseur : absence de clé OpenAI en local, désactivation globale, absence de repli automatique et refus des hôtes/modèles cloud pour Ollama. Les 5 tests OPA, 4 tests Solidity et 2 tests Java du socle portent le total de ces suites à **56 tests**, en plus des parcours d'intégration.

La construction TypeScript/Vite a réussi. Les tests de protocole déterministes restent indépendants des tests avec modèles réels ; ils ne provoquent aucun appel cloud caché. La suite Python conserve l'avertissement de dépréciation `websockets.legacy` déjà signalé dans le premier rapport.

## Reproduire

Après construction et démarrage du socle :

```sh
make test-access
make ai-local
make test-live-local
```

Pour un nouvel essai OpenAI, explicitement payant en tokens :

```sh
make ai-openai
make test-live-openai
make ai-local
```

Le script `scripts/set_ai_mode.py` change le fournisseur sans afficher ni modifier les secrets. Les tests locaux ne téléchargent aucun poids et nécessitent un serveur Ollama déjà lancé avec un modèle compatible avec les outils.
