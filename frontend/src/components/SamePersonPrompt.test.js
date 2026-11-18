import { act } from 'react';
import { createRoot } from 'react-dom/client';
import SamePersonPrompt, { findExistingCustomer } from './SamePersonPrompt';
import api from '../api/api';
import tr from '../i18n/locales/tr/translation.json';
import en from '../i18n/locales/en/translation.json';

jest.mock('@/lib/utils', () => ({
  cn: (...a) => a.filter((x) => typeof x === 'string').join(' '),
  keepOpenOnToastInteract: (fn) => fn,
}), { virtual: true });
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }), { virtual: true });
jest.mock('../api/api', () => ({ __esModule: true, default: { post: jest.fn(), get: jest.fn() } }));
jest.mock('react-i18next', () => {
  const trJson = jest.requireActual('../i18n/locales/tr/translation.json');
  const lookup = (key) => key.split('.').reduce((o, k) => (o == null ? undefined : o[k]), trJson);
  return {
    useTranslation: () => ({
      t: (k, o) => String(lookup(k) ?? k).replace(/\{\{(\w+)\}\}/g, (_, v) => (o && o[v]) ?? ''),
    }),
  };
});

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
const payload = { name: 'Ayşe Yeni', phone: '0532 111 22 33' };
const dialog = () => document.body.querySelector('[role="dialog"]');
const button = (label) => [...document.body.querySelectorAll('button')].find((b) => b.textContent.trim() === label);
const text = (el) => el.textContent.replace(/\s+/g, ' ').trim();

beforeEach(() => {
  jest.clearAllMocks();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function render(props) {
  await act(async () => {
    root.render(<SamePersonPrompt open name="Ayşe Yılmaz" payload={payload} onSame={jest.fn()} onDone={jest.fn()} onClose={jest.fn()} {...props} />);
  });
}

test('shows existing name and both choices', async () => {
  await render();
  expect(text(dialog())).toContain('Bu numara zaten Ayşe Yılmaz adına kayıtlı. Aynı kişi mi?');
  expect(button('Aynı kişi')).toBeDefined();
  expect(button('Farklı kişi')).toBeDefined();
});

test('same person hands the existing customer back without posting', async () => {
  const onSame = jest.fn();
  await render({ onSame });
  await act(async () => button('Aynı kişi').click());
  expect(onSame).toHaveBeenCalled();
  expect(api.post).not.toHaveBeenCalled();
});

test('different person resends with allow_shared_phone', async () => {
  api.post.mockResolvedValue({ data: { message: 'ok' } });
  const onDone = jest.fn();
  await render({ onDone });
  await act(async () => button('Farklı kişi').click());
  expect(api.post).toHaveBeenCalledWith('/customers', { ...payload, allow_shared_phone: true });
  expect(onDone).toHaveBeenCalled();
});

test('different person failure keeps the prompt open and does not call onDone', async () => {
  api.post.mockRejectedValue({ response: { data: { detail: 'Hata oldu' } } });
  const onDone = jest.fn();
  await render({ onDone });
  await act(async () => button('Farklı kişi').click());
  expect(onDone).not.toHaveBeenCalled();
  expect(dialog()).not.toBeNull();
});

test('findExistingCustomer searches by digits and returns the first match', async () => {
  api.get.mockResolvedValue({ data: { items: [{ id: 'c1', name: 'Ayşe Yılmaz', phone: '905321112233' }], has_more: false } });
  const found = await findExistingCustomer('0532 111 22 33');
  expect(api.get).toHaveBeenCalledWith('/customers', { params: { search: '05321112233', limit: 5 } });
  expect(found.id).toBe('c1');
});

test('TR and EN copy match the approved text', () => {
  expect(tr.customers.samePerson).toEqual({
    prompt: 'Bu numara zaten {{name}} adına kayıtlı. Aynı kişi mi?', same: 'Aynı kişi', different: 'Farklı kişi',
  });
  expect(en.customers.samePerson.same).toBe('Same person');
  expect(en.customers.mergeSuggestion.merge).toBe('Merge');
});
