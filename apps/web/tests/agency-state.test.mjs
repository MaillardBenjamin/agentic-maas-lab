import test from 'node:test';
import assert from 'node:assert/strict';
import { euroCents, regularizationAllowed, agencyQuoteMatches, matchingCustomers, preferredAgencyOrder } from '../src/agency-state.ts';

test('euro input accepts decimal comma without accepting rounding, exponent or negative amounts', () => {
  assert.equal(euroCents('2,15'), 215);
  assert.equal(euroCents('5'), 500);
  for (const value of ['', '-2', '0', '2.001', '1e2', 'NaN']) assert.equal(euroCents(value), null);
});
test('regularization requires a paid order, role delegation and enough remaining prepaid funds', () => {
  const order = {payment_count: 1, quote: {total_cents: 1000}, refund_cents: 400};
  assert.equal(regularizationAllowed(order, 500, 'clerk'), true);
  assert.equal(regularizationAllowed(order, 600, 'clerk'), false);
  assert.equal(regularizationAllowed(order, 600, 'supervisor'), true);
  assert.equal(regularizationAllowed(order, 601, 'supervisor'), false);
  assert.equal(regularizationAllowed({...order, payment_count: 0}, 200, 'clerk'), false);
  assert.equal(regularizationAllowed(order, 200, 'traveler'), false);
});
test('an earlier customer, date, product selection, expired or app-seller quote cannot confirm an agency sale', () => {
  const quote = {traveler: 'lea', seller: 'agency', travel_date: '2026-10-28', expires_at: '2026-10-28T12:00:00Z', lines: [{product: 'transport'}]};
  const check = value => agencyQuoteMatches(value, 'lea', ['transport'], '2026-10-28', Date.parse('2026-10-28T11:59:00Z'));
  assert.equal(check(quote), true);
  for (const value of [{...quote, traveler: 'adult'}, {...quote, seller: 'app'}, {...quote, travel_date: '2026-10-29'}, {...quote, lines: []}, {...quote, expires_at: '2026-10-28T11:00:00Z'}]) assert.equal(check(value), false);
});
test('customer search handles accents and returns the owner of a reference, not another traveler', () => {
  const customers = [{id: 'lea', name: 'Léa'}, {id: 'adult', name: 'Alex'}];
  const orders = [{id: 'order-ab12345', traveler: 'adult'}];
  assert.deepEqual(matchingCustomers(customers, orders, 'lea').map(c => c.id), ['lea']);
  assert.deepEqual(matchingCustomers(customers, orders, '12345').map(c => c.id), ['adult']);
  assert.deepEqual(matchingCustomers(customers, orders, 'absent'), []);
  const many = [{id: 'order-recent', traveler: 'lea'}, {id: 'order-requested', traveler: 'lea'}, {id: 'order-foreign', traveler: 'adult'}];
  assert.equal(preferredAgencyOrder(many, 'lea', 'requested'), 'order-requested');
  assert.equal(preferredAgencyOrder(many, 'lea', 'foreign'), 'order-recent');
});
