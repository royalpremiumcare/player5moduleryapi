import { act } from 'react';
import { createRoot } from 'react-dom/client';
import PaymentsPausedNotice from './PaymentsPausedNotice';
import { MERCHANT_PAYMENTS_PAUSED, selectablePaymentRules } from '../lib/paymentsPause';

// t() resolves from the shipped Turkish translation file, so the tests check the copy users see.
jest.mock('react-i18next', () => {
  const trJson = jest.requireActual('../i18n/locales/tr/translation.json');
  const lookup = (key) => key.split('.').reduce((o, k) => (o == null ? undefined : o[k]), trJson);
  return { useTranslation: () => ({ t: (k) => lookup(k) ?? k }) };
});

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

const text = (el) => el.textContent.replace(/\s+/g, ' ').trim();

test('shows a real heading and plain-language explanation', async () => {
  await act(async () => root.render(<PaymentsPausedNotice onNavigate={jest.fn()} />));
  const h1 = container.querySelector('h1');
  expect(h1).not.toBeNull();
  expect(text(h1)).toBe('Ödemeler geçici olarak kapalı');
  expect(text(container)).toContain('ödemeyi salonda almaya devam edebilirsiniz');
});

test('back button returns to settings', async () => {
  const onNavigate = jest.fn();
  await act(async () => root.render(<PaymentsPausedNotice onNavigate={onNavigate} />));
  const back = [...container.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === 'Geri');
  expect(back).toBeDefined();
  await act(async () => back.click());
  expect(onNavigate).toHaveBeenCalledWith('settings');
});

test('while paused only pay-at-salon can be chosen for a service', () => {
  expect(MERCHANT_PAYMENTS_PAUSED).toBe(true);
  expect(selectablePaymentRules()).toEqual(['on_site']);
  expect(selectablePaymentRules(false)).toEqual(['on_site', 'online', 'deposit']);
});
