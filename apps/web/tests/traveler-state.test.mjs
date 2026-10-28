import test from "node:test";
import assert from "node:assert/strict";
import { deliveryConfirmed, localTravelDate, quoteMatchesCart } from "../src/traveler-state.ts";
const quote = { traveler: "lea", seller: "app", travel_date: "2026-10-27", expires_at: "2026-10-27T14:00:00Z", lines: [{ product: "transport" }, { product: "parking" }] };
test("removing a product invalidates the earlier basket price", () => {
  assert.equal(quoteMatchesCart(quote, ["transport"], quote.travel_date, "lea"), false);
  assert.equal(quoteMatchesCart(quote, ["transport", "parking", "bike"], quote.travel_date, "lea"), false);
});
test("a quote from another profile, date or seller cannot enable confirmation", () => {
  assert.equal(quoteMatchesCart(quote, ["transport", "parking"], quote.travel_date, "adult"), false);
  assert.equal(quoteMatchesCart(quote, ["transport", "parking"], "2027-09-01", "lea"), false);
  assert.equal(quoteMatchesCart({ ...quote, seller: "agency" }, ["transport", "parking"], quote.travel_date, "lea"), false);
});
test("reordering the same selection preserves the quote but duplicates and empty carts do not", () => {
  assert.equal(quoteMatchesCart(quote, ["parking", "transport"], quote.travel_date, "lea"), true);
  assert.equal(quoteMatchesCart(quote, ["transport", "transport"], quote.travel_date, "lea"), false);
  assert.equal(quoteMatchesCart({ ...quote, lines: [] }, [], quote.travel_date, "lea"), false);
  assert.equal(quoteMatchesCart(null, ["transport"], quote.travel_date, "lea"), false);
});
test("the account shows titles as usable only after payment and verified delivery", () => {
  const order = { state: "fulfilled", payment_count: 1, card: { sdk: { verified_read_after_write: true } } };
  assert.equal(deliveryConfirmed(order), true);
  assert.equal(deliveryConfirmed({ ...order, payment_count: 0 }), false);
  assert.equal(deliveryConfirmed({ ...order, state: "issuance_pending" }), false);
  assert.equal(deliveryConfirmed({ ...order, card: undefined }), false);
  assert.equal(deliveryConfirmed({ ...order, card: { sdk: { verified_read_after_write: false } } }), false);
});
test("the use date follows the local calendar rather than a hardcoded demonstration date", () => {
  assert.equal(localTravelDate(new Date(2026, 9, 27, 0, 15)), "2026-10-27");
});
