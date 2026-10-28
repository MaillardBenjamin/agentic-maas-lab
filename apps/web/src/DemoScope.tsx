import { ChevronDown, ShieldCheck } from "lucide-react";

export type AIProvider = "ollama" | "openai" | "disabled";

export function DemoScope({
  provider,
  bridgeEnabled,
  expanded = false,
}: {
  provider: AIProvider;
  bridgeEnabled: boolean;
  expanded?: boolean;
}) {
  const model = provider === "ollama" ? "Ollama local" : "OpenAI";
  return (
    <details className="card demo-scope" open={expanded}>
      <summary>
        <ShieldCheck size={20} aria-hidden="true" />
        <span className="scope-title">
          <strong>Périmètre du démonstrateur</strong>
          <span>Fonctions présentes, simulations et compléments à réaliser</span>
        </span>
        <span className="badge light">POC partiel</span>
        <ChevronDown className="scope-chevron" size={18} aria-hidden="true" />
      </summary>
      <div className="scope-grid">
        <section>
          <h3><span className="badge real">Présent dans le POC</span></h3>
          <ul>
            <li>{provider === "disabled" ? "Dialogue IA branché ; fournisseur désactivé dans la configuration." : `Dialogue IA branché ; fournisseur sélectionné : ${model}.`} Délégation entre agents et consultation des outils métier.</li>
            <li>Devis, achat, délivrance via Temporal, commissions et contrôle des habilitations SAV.</li>
            <li>Tarifs, disponibilités, SAV et commissions : les coordinateurs consultent les agents Transport, Parking et Vélo dans leurs périmètres. Le dialogue peut préparer un devis à examiner avant confirmation.</li>
            <li>Vélo et parking : agents MaaS et partenaires connectés en A2A, outils MCP opérationnels et parcours de réservation et d’usage testé avec le modèle IA local.</li>
            <li>Paiement prépayé Bridge testé en sandbox jusqu’à la délivrance. {bridgeEnabled ? "Sandbox activée." : "Sandbox désactivée dans la configuration."}</li>
            <li>Graphe FalkorDB et recherche lexicale ; ancrage de preuves sur blockchain locale.</li>
            <li>Échanges A2A et appels MCP visibles en direct : agents sollicités, état, durée et distinction entre modèle réel et modèle de test.</li>
            <li>Capture webcam et transcription locale par mWhisper-Flamingo : audio + lèvres ou lèvres seules, avec correction et validation. Audio OpenAI facultatif, sans transmission des images.</li>
          </ul>
        </section>
        <section>
          <h3><span className="badge light">Simulé pour la démonstration</span></h3>
          <ul>
            <li>Borne tactile : parcours d’achat, chargement et fin de session opérationnels ; présentation de carte, lecteur et terminal de paiement fictifs. SDK Keyple réel sur carte stub.</li>
            <li>Valideurs X/Y : réception et déduplication opérationnelles ; passages injectés par des simulateurs, sans valideur physique ni agent constructeur A2A.</li>
            <li>Vélos et places de parking fictifs : stocks, réservations et usages gérés par les simulateurs du POC. Les réservations ne concernent aucun opérateur réel.</li>
            <li>Identités, droits étudiants et régularisations SAV fictifs. Aucun remboursement bancaire exécuté.</li>
          </ul>
        </section>
        <section>
          <h3><span className="badge incomplete">À compléter ou à valider</span></h3>
          <ul>
            <li>Webcam et microphone physiques : autorisations, qualité et latence à valider dans le navigateur. Connexion audio OpenAI testée sur un extrait public.</li>
            <li>Lecture labiale : inférence testée sur un extrait public français préparé ; précision et capture caméra à évaluer sur les conditions d’usage.</li>

            <li>Banque : réception des notifications à valider ; remboursement, encaissement postpayé et reversements non implémentés.</li>
            <li>Recherche par embeddings sémantiques, identité numérique et vérification de justificatifs : non implémentées.</li>
            <li>Corrélation distribuée OpenTelemetry à compléter ; Harness² testé avec des éditeurs scriptés, optimisation par LLM à réaliser.</li>
          </ul>
        </section>
      </div>
      <p className="scope-footnote">
        Autopartage et covoiturage : extensions futures. Le calcul d’itinéraire et l’information voyageurs restent hors périmètre.
        Les statuts d’activation indiquent la configuration sélectionnée, sans garantir la disponibilité des services.
      </p>
    </details>
  );
}
