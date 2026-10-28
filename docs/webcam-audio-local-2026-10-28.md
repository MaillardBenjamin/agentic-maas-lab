# Webcam locale, audio OpenAI facultatif

L’interface capture la vidéo **uniquement avec la webcam**. Aucun sélecteur de fichier ni réglage de vidéo préparée n’est proposé. La vidéo et le cadrage des lèvres restent traités sur le Mac par mWhisper-Flamingo. OpenAI peut intervenir uniquement pour le dialogue audio, après activation explicite ; aucune image n’est transmise à OpenAI.

## Parcours

Dans l’assistant Voyageur, Agence/CRC ou Console, ouvrir **Webcam et reconnaissance labiale**. Choisir **Audio + lèvres, en local** ou **Lèvres seules, en local**, puis démarrer la webcam. Le navigateur demande les autorisations nécessaires. Le microphone est demandé pour le mode audiovisuel local ou lorsque l’audio OpenAI est sélectionné.

Autoriser l’analyse locale puis choisir **Analyser une phrase · 8 secondes**. La capture est automatiquement transmise au moteur local à la fin des huit secondes, ou après **Terminer la phrase et analyser**. L’aperçu webcam reste actif ; la reconnaissance locale est différée, pas une transcription vidéo continue. Relire et corriger le texte proposé, puis le placer dans le message. Aucun envoi automatique aux agents.

L’option **Ajouter l’audio OpenAI en direct** est décochée par défaut. Elle demande une autorisation explicite de partage du son et des textes de dialogue. La connexion WebRTC transmet exclusivement les pistes obtenues par `getAudioTracks()` ; aucune piste vidéo, image fixe ou séquence de trames n’est envoyée. La voix peut consulter les agents métier via l’API authentifiée, en lecture seule. Une proposition labiale ne rejoint cette conversation qu’après relecture et clic sur le bouton dédié. Les textes et réponses métier nécessaires au dialogue peuvent alors être transmis ; les images restent locales.

Arrêter la webcam, fermer le panneau, changer de contexte ou masquer la page ferme les ressources concernées. Un plafond de trois minutes arrête la capture et la connexion côté navigateur. Annuler une autorisation en attente empêche une ouverture tardive des appareils. Une erreur du MediaRecorder empêche l’envoi d’une capture partielle comme résultat valide. Le texte déjà produit peut rester consultable après l’arrêt ; le bouton d’effacement le retire.

## Configuration

```dotenv
AI_ENABLED=true
OPENAI_LIVE_AUDIO_ENABLED=true
OPENAI_REALTIME_MODEL=gpt-realtime-2.1-mini
# OPENAI_API_KEY à conserver dans le fichier local .env
# AGENT_MODE peut rester à ollama
```

Les nouvelles installations gardent l’option désactivée dans `.env.example`. Sur cette machine, l’option est configurée avec la clé existante et les agents texte restent sur Ollama. Aucun partage audio ne commence avant l’action explicite dans le navigateur.

`GET /api/voice/status` donne la configuration accessible à la session. `POST /api/voice/session` exige un JWT et `consent=true`, réserve le budget applicatif existant et demande un secret éphémère de trente secondes. La clé principale reste sur le serveur. Ce délai borne la création de connexion, pas sa durée ; la limite de trois minutes est appliquée par le client et ne constitue pas un plafond de facturation absolu. Le budget conserve des réservations prudentes, distinctes de la facture OpenAI.

L’ancien bouton vocal séparé est remplacé par l’option audio du parcours webcam, afin de partager la même acquisition microphone et de centraliser les arrêts. Le fournisseur du dialogue texte n’est pas changé automatiquement. Les outils audio utilisent l’agent et la commande sélectionnés dans le panneau parent.

## Vérifications

- 94 tests Python du socle/API et 33 tests du frontal réussis, dont consentement, configuration indépendante des agents locaux, protection des clés, transport audio seul, arrêt pendant la connexion, appels d’outils dédupliqués, capture annulée et piste micro exclue en lecture labiale seule.
- Construction TypeScript/Vite et images Docker réussies.
- Vérification dans l’interface Voyageur déployée : moteur local disponible, option audio décochée et bouton webcam présent, sans sélecteur de fichier. La caméra et le microphone personnels n’ont pas été activés pendant cette vérification. [Capture de l’interface](webcam-audio-interface-2026-10-28.jpg).
- Test réel de connexion OpenAI avec l’extrait audio public français MuAViC déjà téléchargé, sans webcam ni microphone personnels. Réponse vocale et transcription de cette réponse reçues ; zéro image envoyée. Le premier essai à faible niveau sonore n’a pas été entendu. Après amplification de l’extrait et configuration explicite PCM 24 kHz, la phrase a été reprise, avec une erreur sur l’année : le modèle a dit 2100 alors que l’essai local audiovisuel donnait 2048. Cela valide le transport et une compréhension partielle, pas une transcription exacte ou une mesure d’accessibilité.

Les preuves locales sont `data/live-audio-evidence/openai-audio-public.json` et `openai-audio-public-normalized.json`, hors Git. Le parcours WebRTC avec la webcam et le microphone physiques reste à valider après autorisation de l’utilisateur dans son navigateur. Les tests automatiques utilisent des doubles d’appareils, explicitement distincts de ce test matériel.

Références : [WebRTC OpenAI](https://developers.openai.com/api/docs/guides/voice-webrtc), [modèle audio Realtime](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini), [clé éphémère](https://developers.openai.com/api/reference/resources/realtime/subresources/client_secrets/methods/create).
