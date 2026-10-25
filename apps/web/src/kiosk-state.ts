export type KioskStep = "welcome" | "products" | "review" | "payment" | "loading" | "done";
type Order = { state: string; payment_count: number; card?: { sdk?: { verified_read_after_write?: boolean } } };

export function kioskStep(cardPresented: boolean, hasQuote: boolean, order: Order | null): KioskStep {
  if (!cardPresented) return "welcome";
  if (!order) return hasQuote ? "review" : "products";
  if (order.payment_count > 0 && order.state === "fulfilled" && order.card?.sdk?.verified_read_after_write === true) return "done";
  return order.payment_count > 0 ? "loading" : "payment";
}

export function quoteExpired(expiresAt: string, now = Date.now()): boolean {
  const expiry = Date.parse(expiresAt);
  return !Number.isFinite(expiry) || expiry <= now;
}

export function idleSeconds(lastActivity: number, now = Date.now(), timeout = 120): number {
  return Math.max(0, Math.min(timeout, Math.ceil(timeout - (now - lastActivity) / 1000)));
}

export function bridgePaymentUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "pay.bridgeapi.io" && !url.port && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function bankScreenSeconds(expiresAt: string | undefined, now = Date.now()): number {
  const expiry = Date.parse(expiresAt || "");
  return Number.isFinite(expiry) ? Math.max(0, Math.min(600, Math.ceil((expiry - now) / 1000))) : 0;
}
