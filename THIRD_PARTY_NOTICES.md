# Composants tiers

La licence MIT du code original n'altère pas les licences des composants ci-dessous. Cette liste couvre les composants principaux ; les verrous de dépendances énumèrent les versions transitives, sans constituer un audit exhaustif de leurs licences.

| Composant | Version intégrée | Licence déclarée / conditions |
|---|---|---|
| Agno / AgentOS | 3.1.10 | Apache-2.0 |
| OpenAI SDK | 2.29.0 | Apache-2.0 ; services OpenAI sous leurs conditions API |
| Ollama SDK Python | 0.6.3 | MIT |
| Qwen3:14b | modèle local existant, `bdbd181c33f2` | Apache-2.0 ; poids non redistribués dans le projet |
| A2A SDK | 0.3.26 | Apache-2.0 |
| FastMCP | 4.1.3 | Apache-2.0 |
| PostgreSQL | 17.6 | PostgreSQL License |
| FalkorDB serveur | 4.20.3 | SSPLv1 ; service séparé, ne pas le présenter comme MIT |
| FalkorDB client Python | 1.2.0 | MIT |
| Temporal serveur / SDK Python | 1.29.1 / 1.12.0 | MIT |
| OPA | 1.0.1 | Apache-2.0 ; image amd64 émulée sur le Mac testé |
| OpenTelemetry / Jaeger | Collector 0.128.0 / Jaeger 1.68.0 | Apache-2.0 |
| Keyple Service / Calypso / Stub | 3.5.0 / 3.3.0 / 2.2.2 | EPL-2.0 |
| Keypop Reader / Calypso API | 2.1.0 / 2.3.0 | EPL-2.0 |
| Foundry / Anvil | 1.3.1 | MIT ou Apache-2.0 selon les composants ; bibliothèques embarquées sous leurs propres licences |
| qrcode.react | 4.2.0 | ISC ; encodeur QR intégré de Nayuki sous MIT, notices du paquet conservées dans node_modules |
| React / Vite / Lucide | 19.1.0 / 6.4.5 / 0.468.0 | MIT / MIT / ISC |
| Harness² | 0.1.0, commit `1cfe254e8d25b15f37048c3730134686abe60335` | Apache-2.0 ; ses dépendances et benchmarks conservent leurs notices |
| Bridge | API `2025-01-15` | Service sous conditions du prestataire, aucune licence MIT sur l'API |

Les sources de Harness² sont téléchargées depuis le dépôt officiel lors de la construction du laboratoire ; leur licence est conservée dans l'image à `/opt/harness2/LICENSE`. Aucune clé ni socket Docker n'est monté dans le laboratoire. Le runtime est sans réseau et ses éditeurs sont déterministes ; l'adaptateur MaaS est du code original.

## Vecteurs de test Calypso

Le profil de sélection fictif (AID, FCI et données de mise sous tension) de l'adaptateur Java s'appuie sur les vecteurs de démonstration de [Eclipse Keyple Java Example](https://github.com/eclipse-keyple/keyple-java-example), en particulier `StubSmartCardFactory`. Aucun code applicatif de cet exemple n'est redistribué ; la notice des données d'exemple est conservée ci-dessous.

Copyright (c) 2021 Calypso Networks Association https://calypsonet.org/

Eclipse Distribution License 1.0 / BSD-3-Clause:

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
