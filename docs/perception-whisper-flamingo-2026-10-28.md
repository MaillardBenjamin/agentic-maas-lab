# Reconnaissance audiovisuelle et labiale locale

> Mise à jour de l’interface : capture par webcam uniquement, import de fichiers retiré. Voir [le parcours courant et l’audio OpenAI facultatif](webcam-audio-local-2026-10-28.md). Les essais sur fichiers préparés ci-dessous restent des preuves techniques historiques.

Implémentation et essais réalisés les 27–28 octobre 2026, sur Docker Desktop Apple Silicon. Le composant utilise réellement les poids officiels de [mWhisper-Flamingo](https://github.com/roudimit/whisper-flamingo), version multilingue Small permettant de sélectionner le français. Il transcrit la parole dans une vidéo ; il n’analyse pas sémantiquement toute la scène.

## Utilisation

Dans **Voyageur → connexion de démonstration → Aide → Dicter avec la vidéo ou les lèvres** : sélectionner **Audio + vidéo** ou **Lèvres seules · son ignoré**, puis démarrer la webcam et capturer une courte phrase. Le mode caméra propose huit secondes, avec son uniquement en mode audiovisuel. L’autorisation caméra/micro reste à donner dans le navigateur.

Le cadrage webcam est automatiquement de type **Visage entier** : détection d’un seul visage, repères dlib, alignement AV-HuBERT et recadrage des lèvres. Les essais internes sur MuAViC conservent le paramètre API `framing=mouth`, absent de l’interface utilisateur. Le moteur accepte une séquence de 0,4 à 15 secondes et 20 Mio maximum, en MP4/WebM/MOV, jusqu’au Full HD.

Après le consentement explicite, la vidéo est traitée localement. Le texte peut être corrigé, doit être validé, puis **Utiliser ce texte dans mon message** remplit le champ de l’assistant. Il faut ensuite choisir **Envoyer**. La transcription n’exécute aucune commande métier.

## Installation et arrêt

```sh
make perception-assets  # environ 4 Go, ressources officielles et SHA-256 vérifiés
make perception         # construit et démarre perception, API et interface
make test-perception    # contrôles de l’API et du service, sans inférence simulée
make perception-stop    # libère le moteur, saisie écrite toujours disponible
```

Le socle doit être démarré (`make up`). Le profil Docker `perception` reste facultatif et n’impose pas de téléchargement au démarrage ordinaire. La première construction compile dlib et Fairseq, et prend plusieurs minutes. L’image utilise Python 3.10, PyTorch 2.5.1 et trois threads CPU ; le conteneur dispose d’un plafond de 5 Gio. Les versions directes sont figées dans `requirements.txt`, les révisions sources dans le Dockerfile et les ressources dans `assets.json`. Le téléchargement peut être réexécuté et ignore les fichiers déjà valides :

```sh
python3 scripts/perception_assets.py --verify-only
```

Les poids restent sous `data/perception/models/`, hors Git et du contexte Docker, montés en lecture seule. Le service vérifie leur taille et leur SHA-256 avant de se déclarer prêt. Aucune clé OpenAI n’est utilisée par la transcription. L’état effectif est accessible à une session locale via `GET /api/perception/status`.

## Implémentation

Le navigateur envoie un corps vidéo binaire à l’API authentifiée. Celle-ci dérive le propriétaire de la session, impose consentement, type et taille, puis utilise une destination privée fixe. Le service est sur un réseau Docker interne, sans port publié, sans accès au réseau externe, aux bases ou aux agents. Une seule inférence est exécutée à la fois ; une analyse concurrente reçoit un refus explicite.

Un sous-processus charge strictement tous les paramètres du modèle, traite les images à 25 images/s et s’arrête après la séquence. Le traitement CPU est limité à 300 secondes. En mode lèvres seules, aucun échantillon audio du fichier n’est décodé ; les caractéristiques audio de Whisper sont neutralisées, comme lors de l’abandon de modalité à l’entraînement. Il ne s’agit pas d’un modèle distinct optimisé uniquement pour la lecture labiale.

Le cadrage utilise les repères dlib 68 points et le prétraitement officiel AV-HuBERT (96 pixels, centre de 88 pixels, normalisation). Une visibilité insuffisante ou plusieurs visages produisent un refus. Les adaptations d’AV-HuBERT et des anciens alias NumPy de Fairseq sont limitées et appliquées sur des sources figées, sans chargement partiel de poids.

Les fichiers du moteur sont effacés à la fin ou à l’annulation. Le résultat reste uniquement en mémoire serveur pendant au plus quinze minutes, avec expiration même sans nouvelle requête. La fermeture du panneau annule la tâche active. Une autre identité reçoit 404 et ne peut ni lire ni supprimer cette tâche. Le bouton d’effacement supprime également l’aperçu et le texte du panneau. Un texte déjà copié dans le message reste modifiable par le voyageur. Les médias et transcriptions ne sont pas enregistrés dans PostgreSQL, le graphe ou les traces ; l’envoi ultérieur du message suit le fournisseur IA sélectionné dans l’application.

## Vérifications réelles

Extrait public officiel `muavic_fr_0u7tTptBo9I_0081`, lèvres préparées et piste audio associée, 5,7 secondes. Vidéo et son réunis localement en `data/perception/demo/fr-av.mp4`. Les résultats bruts sont conservés localement dans `data/perception/evidence/api-fr.json` ; ce dossier est exclu de Git.

| Mode réel | Temps du moteur, chargement compris | Temps via API | Texte obtenu |
|---|---:|---:|---|
| Audio + vidéo | 18,985 s | 22,67 s | « et pourtant les scientifiques des nations unies prédisent un effondrement des pêcheries d’ici 2048 » |
| Lèvres seules, audio exclu | 18,618 s | 21,49 s | « et pourtant les centaines d’aventures qui passent à des fonctions pour des pêcheurs à des hautes » |

Le contraste montre que l’inférence fonctionne et que la lecture labiale seule comporte des erreurs importantes sur cet extrait. Il ne constitue ni une mesure WER, ni une validation d’accessibilité. Un premier démarrage isolé a pris environ 33 secondes ; la latence varie avec les caches et la charge CPU.

Essai navigateur réel : dépôt de cet extrait depuis l’écran Voyageur, sélection du cadrage préparé, consentement, transcription audio + vidéo en 17,1 secondes moteur, relecture puis copie du texte dans le champ du message. Aucun message envoyé aux agents pendant ce test. La capture caméra personnelle n’a pas été activée. Le test automatique rejette notamment une vidéo sans visage ; une séquence réelle de visage entier reste à évaluer.

Tests automatisés : authentification, consentement, modalités/langues autorisées, types et limites de taille, destination privée et identité dérivée, indisponibilité explicite, isolation entre propriétaires, effacement/expiration, occupation du moteur et rejet d’un fichier invalide ou sans visage. Ils sont distincts du test du vrai modèle :

Validation finale : **80 tests Python du socle/API, 5 tests du moteur et 17 tests du frontal réussis**. Construction TypeScript/Vite et images Docker réussies ; API et moteur déclarés sains après redémarrage.

```sh
docker compose run --rm --no-deps \
  -v "$PWD/data/perception/demo:/samples:ro" \
  -v "$PWD/data/perception/evidence:/evidence" \
  api python scripts/perception_smoke.py /samples/fr-av.mp4 --output /evidence/api-fr.json
```

Les fichiers de démonstration proviennent de l’archive de démonstration indiquée dans le notebook officiel `mwhisper_flamingo_demo_noise.ipynb`. Ce test réel exige leur téléchargement et la préparation préalable du MP4 ; `make test-perception` n’effectue pas ce téléchargement.

## Limites

La reconnaissance est différée, sur une courte séquence, sans streaming ni traduction simultanée. La caméra et les neuf langues disponibles dans le sélecteur n’ont pas toutes été validées ; seul le français sur l’extrait préparé a été essayé. Aucun score de confiance calibré n’est affiché. Il reste à mesurer précision, éclairage, angles du visage, bruit, accents et robustesse sur des demandes MaaS consenties, puis à décider d’un matériel GPU si la latence doit diminuer.

AV-HuBERT impose un usage de recherche non commerciale et exclut la production. Les poids et les ressources faciales ont également leurs conditions propres. Voir [les notices tierces](../THIRD_PARTY_NOTICES.md) avant d’envisager une diffusion ou un usage opérationnel.

![Transcription validée dans l’espace Voyageur](perception-voyageur-2026-10-28.jpg)
