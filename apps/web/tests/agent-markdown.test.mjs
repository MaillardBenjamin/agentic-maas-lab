import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAgentMarkdown } from '../src/agent-markdown.ts';

const sample = `Voici les tarifs pour un étudiant selon les différents fournisseurs :

- **Transport** : Le tarif est de **10,00 €** avec une réduction de **30,00 %**, ce qui donne un prix final de **7,00 €** (source : **tariff-1**).
- **Parking** : Le tarif est de **3,00 €** après validation de l'usage (source : \`parking-1\`).
- **Vélo** : Le tarif est le même que pour tout autre utilisateur :
  - **Déverrouillage** : 1,00 €
  - **Par minute commencée** : 0,20 €
  - **Plafond maximum** : 5,00 €
  (source : \`bike-1\`).`;

function spans(text) {
  return parseAgentMarkdown(text).flatMap(block => block.type === 'gap' ? [] : block.spans);
}

test('les segments ** ... ** deviennent du gras, y compris avec des espaces', () => {
  assert.deepEqual(spans('Tarif ** 7,00 € ** et **Transport**').filter(span => span.type === 'bold').map(span => span.value), [' 7,00 € ', 'Transport']);
});

test('la réponse agent conserve le texte et isole le gras et le code', () => {
  const parts = spans(sample);
  assert.deepEqual(parts.filter(span => span.type === 'bold').map(span => span.value), [
    'Transport', '10,00 €', '30,00 %', '7,00 €', 'tariff-1', 'Parking', '3,00 €', 'Vélo', 'Déverrouillage', 'Par minute commencée', 'Plafond maximum',
  ]);
  assert.deepEqual(parts.filter(span => span.type === 'code').map(span => span.value), ['parking-1', 'bike-1']);
  assert.equal(parts.map(span => span.value).join('').includes('**'), false);
});

test('un titre markdown et un lien local perdent leurs marqueurs', () => {
  const blocks = parseAgentMarkdown('### Transport\n\nsource : [parking-1](#parking-1) et [doc](https://example.com/tarif)');
  assert.equal(blocks[0].type, 'heading');
  if (blocks[0].type === 'heading') assert.equal(blocks[0].spans[0].value, 'Transport');
  const line = spans('source : [parking-1](#parking-1) et [doc](https://example.com/tarif)');
  assert.equal(line.some(span => span.type === 'text' && span.value === 'parking-1'), true);
  const link = line.find(span => span.type === 'link');
  assert.equal(link && link.type === 'link' && link.href, 'https://example.com/tarif');
  assert.equal(spans('[x](javascript:alert(1))').some(span => span.type === 'link'), false);
});

test('un marqueur incomplet reste du texte', () => {
  assert.deepEqual(spans('voir **tarif'), [{ type: 'text', value: 'voir **tarif' }]);
});
