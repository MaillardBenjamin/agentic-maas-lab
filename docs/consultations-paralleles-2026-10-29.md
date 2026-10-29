# Consultations indépendantes en parallèle — 29 octobre 2026

La coordination attendait chaque réponse fournisseur dans une boucle avant de contacter le suivant. Les consultations de Transport, Vélo et Parking sont désormais lancées simultanément, avec au plus trois appels A2A fournisseurs en cours par consultation.

Pour Commissions, la lecture du relevé global démarre aussi dans ce groupe. Pour le SAV, c’est la lecture des règles MaaS. Les mêmes consultations fournisseurs servent aux demandes tarifaires et à la préparation commerciale MaaS.

## Dépendances conservées

Le coordinateur reçoit d’abord la demande et détermine les organisations concernées. Toutes les organisations sont vérifiées avant le premier appel. Les lectures indépendantes s’exécutent ensuite en parallèle ; la synthèse attend tous leurs résultats. Leur ordre de présentation reste celui de la sélection, indépendamment de leur ordre de retour.

Un échec empêche de présenter une réponse partielle comme complète. Le groupe attend la fin des autres lectures avant de propager l’erreur. L’annulation de la demande annule et attend les tâches de consultation locales. Chaque tâche conserve le contexte d’identité, la délégation signée et le suivi d’activité.

La préparation du devis attend les consultations. Les actions confirmées de réservation et d’usage conservent leurs dépendances et leurs contrôles métier.

## Validation reproductible

`make test-cooperation` exécute les tests du runtime et les cinq parcours A2A/MCP avec un double de modèle. Les tests de concurrence utilisent des événements de synchronisation : ils vérifient que les appels démarrent avant de libérer leurs réponses, sans déduire le parallélisme d’un simple temps d’exécution.

Les tests couvrent le démarrage simultané des fournisseurs et du relevé, la transmission du contexte, l’ordre des résultats, la limite de trois appels, l’autorisation préalable, l’échec d’un fournisseur, l’annulation et la lecture des règles SAV en parallèle.

`make test-parallel-consultations-local` vérifie le cas Commissions avec Ollama réel et les traces publiées par les frontières A2A/MCP. Il exige que les trois échanges A2A fournisseurs aient commencé avant la fin du premier. Il vérifie également l’absence de modification des stocks et opérations partenaires. Le rapport est écrit dans `data/cooperation-evidence/parallel-consultations-ollama.json`.

Résultats du 29 octobre : **12 tests du runtime et cinq parcours de coopération réussis**. Avec Ollama `qwen3:14b`, les trois appels A2A fournisseurs ont démarré dans une fenêtre inférieure à 1 ms, avant la fin du premier. La demande Commissions complète a pris 134,10 s ; les durées des appels fournisseurs ont été de 32,79 s pour Transport, 59,60 s pour Vélo et 85,63 s pour Parking. Les stocks et opérations sont restés identiques. [Preuve enregistrée](evidence-consultations-paralleles-2026-10-29.json).

Le contrat de l’outil expose au modèle les identifiants exacts des fournisseurs publiés. Les noms affichés ne remplacent pas ces identifiants dans les appels d’outils.

Cette preuve porte sur le chevauchement des appels A2A. Le gain de temps total dépend aussi de la capacité du moteur d’inférence et de la machine à traiter plusieurs demandes simultanément. Le test ne mesure pas directement le parallélisme des calculs GPU et ne constitue pas un benchmark avant/après.
