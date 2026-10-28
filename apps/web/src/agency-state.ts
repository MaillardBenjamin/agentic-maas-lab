type Data = Record<string, any>;
export function euroCents(value: string): number | null {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d{1,4}(\.\d{1,2})?$/.test(normalized)) return null;
  const [whole, decimals = ''] = normalized.split('.');
  const cents = Number(whole) * 100 + Number(decimals.padEnd(2, '0'));
  return cents > 0 ? cents : null;
}
export function regularizationAllowed(order: Data | null, cents: number | null, role: string): boolean {
  return !!order && order.payment_count > 0 && cents !== null && cents > 0 && ['clerk', 'supervisor'].includes(role) && cents <= (role === 'clerk' ? 500 : 100000) && cents <= order.quote.total_cents - order.refund_cents;
}
export function agencyQuoteMatches(quote: Data | null, traveler: string, products: string[], date: string, now = Date.now()): boolean {
  return !!quote && quote.traveler === traveler && quote.seller === 'agency' && quote.travel_date === date && Date.parse(quote.expires_at) > now && products.length > 0 && new Set(products).size === products.length && quote.lines.length === products.length && products.every(product => quote.lines.some((line: Data) => line.product === product));
}
export function matchingCustomers(customers: Data[], orders: Data[], query: string): Data[] {
  const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  const needle = normalize(query);
  return customers.filter(customer => !needle || normalize(customer.name + ' ' + customer.id).includes(needle) || orders.some(order => order.traveler === customer.id && normalize(order.id).includes(needle)));
}
export function preferredAgencyOrder(orders: Data[], traveler: string, query: string): string {
  const own = orders.filter(order => order.traveler === traveler);
  const reference = query.trim().toLowerCase();
  return (reference ? own.find(order => order.id.toLowerCase().includes(reference)) : undefined)?.id || own[0]?.id || '';
}
