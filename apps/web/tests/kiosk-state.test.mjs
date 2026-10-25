import test from "node:test";
import assert from "node:assert/strict";
import { bankScreenSeconds, bridgePaymentUrl, idleSeconds, kioskStep, quoteExpired } from "../src/kiosk-state.ts";

test("a closed session cannot display a late result from the previous traveler", () => {
  assert.equal(kioskStep(false, true, { state: "fulfilled", payment_count: 1, card: { sdk: { verified_read_after_write: true } } }), "welcome");
});
test("a presented card needs a quote before confirmation", () => {
  assert.equal(kioskStep(true, false, null), "products");
  assert.equal(kioskStep(true, true, null), "review");
});
test("an unpaid order stays on the payment screen", () => {
  assert.equal(kioskStep(true, true, { state: "payment_pending", payment_count: 0 }), "payment");
});
test("even a card receipt cannot replace confirmation of the payment", () => {
  assert.equal(kioskStep(true, true, { state: "fulfilled", payment_count: 0, card: { sdk: { verified_read_after_write: true } } }), "payment");
});
test("a recorded payment must not offer another payment while loading", () => {
  assert.equal(kioskStep(true, true, { state: "paid", payment_count: 1 }), "loading");
  assert.equal(kioskStep(true, true, { state: "awaiting_resume", payment_count: 1 }), "loading");
});
test("fulfilled without verified card readback is not a successful delivery", () => {
  assert.equal(kioskStep(true, true, { state: "fulfilled", payment_count: 1 }), "loading");
  assert.equal(kioskStep(true, true, { state: "fulfilled", payment_count: 1, card: { sdk: { verified_read_after_write: false } } }), "loading");
});
test("verified delivery allows card retrieval", () => {
  assert.equal(kioskStep(true, true, { state: "fulfilled", payment_count: 1, card: { sdk: { verified_read_after_write: true } } }), "done");
});
test("expired or malformed quotes must be recalculated", () => {
  const now = Date.parse("2026-10-24T10:00:00Z");
  assert.equal(quoteExpired("2026-10-24T10:00:00Z", now), true);
  assert.equal(quoteExpired("invalid", now), true);
  assert.equal(quoteExpired("2026-10-24T10:15:00Z", now), false);
});
test("inactivity reaches warning and expiration thresholds without negative seconds", () => {
  assert.equal(idleSeconds(1000, 101000), 20);
  assert.equal(idleSeconds(1000, 121000), 0);
  assert.equal(idleSeconds(1000, 200000), 0);
});
test("new activity restores the full interval and a clock rollback cannot extend it", () => {
  assert.equal(idleSeconds(120000, 120000), 120);
  assert.equal(idleSeconds(120000, 100000), 120);
});

test("QR links accept only public HTTPS Bridge URLs without embedded credentials", () => {
  assert.equal(bridgePaymentUrl("https://pay.bridgeapi.io/link/test"), "https://pay.bridgeapi.io/link/test");
  for (const value of [null, "javascript:alert(1)", "http://pay.bridgeapi.io/link/test", "https://pay.bridgeapi.io.evil.test/", "https://secret@pay.bridgeapi.io/link/test", "https://pay.bridgeapi.io:8443/", "http://127.0.0.1:5190"]) assert.equal(bridgePaymentUrl(value), null);
});
test("bank screen follows link expiry instead of extending on every touch", () => {
  const now = Date.parse("2026-10-25T12:00:00Z");
  assert.equal(bankScreenSeconds("2026-10-25T12:10:00Z", now), 600);
  assert.equal(bankScreenSeconds("2026-10-25T12:01:00Z", now), 60);
  assert.equal(bankScreenSeconds("2026-10-25T11:00:00Z", now), 0);
  assert.equal(bankScreenSeconds(undefined, now), 0);
  assert.equal(bankScreenSeconds("invalid", now), 0);
});
