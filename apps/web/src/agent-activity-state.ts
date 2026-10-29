export type Exchange = { run_id: string; span_id: string; protocol: string; source: string; target: string; state: string; at: string; sequence: number; duration_ms: number | null };
export function mergeExchanges(previous: Exchange[], incoming: Exchange[]): Exchange[] {
  const spans = new Map(previous.map(value => [value.span_id, value]));
  for (const value of incoming) {
    const before = spans.get(value.span_id);
    if (!before || before.sequence < value.sequence) spans.set(value.span_id, value);
  }
  return [...spans.values()].sort((a, b) => a.sequence - b.sequence).slice(-512);
}
export function actorState(spans: Exchange[], actor: string): string {
  const relevant = spans.filter(span => span.target === actor || span.source === actor);
  if (relevant.some(span => span.state === 'started')) return 'started';
  return relevant.at(-1)?.state || 'idle';
}
export const actorLabels: Record<string, string> = { interface: 'Interface', history: 'Achats et preuves', read_abt_account: 'Compte mobilité ABT', list_purchases: 'Historique des achats', read_purchase: 'Détail d’achat', verify_purchase_proofs: 'Vérification blockchain', conversation: 'Accueil', tariffs: 'Tarifs', sav: 'SAV', clearing: 'Commissions', mobility: 'MaaS', transport: 'Agent transport', read_provider_context: 'Données de l’organisation', prepare_quote: 'Préparation du devis', bike: 'Agent vélo', parking: 'Agent parking', read_catalog: 'Catalogue', search_tariffs: 'Recherche tarifaire', read_order: 'Commande', read_statement: 'Relevé', bike_availability: 'Disponibilité vélo', bike_apply: 'Action vélo confirmée', parking_availability: 'Disponibilité parking', parking_apply: 'Action parking confirmée' };
