export type CartQuote = {
  traveler: string;
  seller: string;
  travel_date: string;
  expires_at: string;
  lines: { product: string }[];
};

// A response for an earlier basket, profile or date must never enable checkout.
export function quoteMatchesCart(quote: CartQuote | null, products: string[], date: string, traveler: string): boolean {
  if (!quote || !products.length || quote.traveler !== traveler || quote.seller !== "app" || quote.travel_date !== date) return false;
  const quoted = quote.lines.map(line => line.product);
  return new Set(products).size === products.length && quoted.length === products.length && products.every(id => quoted.includes(id));
}

export function localTravelDate(now = new Date()): string {
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}

export function deliveryConfirmed(order: { state: string; payment_count: number; card?: { sdk?: { verified_read_after_write?: boolean } } }): boolean {
  return order.state === "fulfilled" && order.payment_count > 0 && order.card?.sdk?.verified_read_after_write === true;
}
