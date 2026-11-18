import { act } from 'react';
import { createRoot } from 'react-dom/client';
import MergeSuggestion from './MergeSuggestion';
import api from '../api/api';

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
const { toast } = require('sonner');

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
const row = { id: 'src1', name: 'Ayşe (online)', phone: '905321112233', merge_suggestion_for: 'key1' };
const button = (label) => [...container.querySelectorAll('button')].find((b) => b.textContent.trim() === label);

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
    root.render(<MergeSuggestion customer={row} survivorName="Ayşe Yılmaz" userRole="admin" onDone={jest.fn()} {...props} />);
  });
}

test('shows the keyed customer name and both choices', async () => {
  await render();
  expect(container.textContent).toContain('Bu numarada zaten Ayşe Yılmaz kayıtlı. Aynı kişi mi?');
  expect(button('Birleştir')).toBeDefined();
  expect(button('Farklı kişi')).toBeDefined();
});

test('merge calls endpoint with survivor and source', async () => {
  api.post.mockResolvedValue({ data: { merged: true, survivor_id: 'key1' } });
  const onDone = jest.fn();
  await render({ onDone });
  await act(async () => button('Birleştir').click());
  expect(api.post).toHaveBeenCalledWith('/customers/merge', { survivor_id: 'key1', source_id: 'src1' });
  expect(onDone).toHaveBeenCalled();
});

test('merge conflict shows the API message and keeps the suggestion', async () => {
  api.post.mockRejectedValue({ response: { status: 409, data: { detail: 'Kayıt şu anda değişti' } } });
  const onDone = jest.fn();
  await render({ onDone });
  await act(async () => button('Birleştir').click());
  expect(toast.error).toHaveBeenCalledWith('Kayıt şu anda değişti');
  expect(onDone).not.toHaveBeenCalled();
});

test('different person clears suggestion', async () => {
  api.post.mockResolvedValue({ data: { ok: true } });
  const onDone = jest.fn();
  await render({ onDone });
  await act(async () => button('Farklı kişi').click());
  expect(api.post).toHaveBeenCalledWith('/customers/src1/not-duplicate');
  expect(onDone).toHaveBeenCalled();
});

test('looks up the keyed customer name when it was not passed in', async () => {
  api.get.mockResolvedValue({ data: { items: [{ id: 'other', name: 'X' }, { id: 'key1', name: 'Ayşe Yılmaz' }] } });
  await render({ survivorName: undefined });
  expect(container.textContent).toContain('Ayşe Yılmaz');
});

test.each(['staff', undefined])('renders nothing and looks nothing up for role %s', async (userRole) => {
  api.get.mockResolvedValue({ data: { items: [{ id: 'key1', name: 'Ayşe Yılmaz' }] } });
  await render({ userRole, survivorName: undefined });
  expect(container.innerHTML).toBe('');
  expect(button('Birleştir')).toBeUndefined();
  expect(api.get).not.toHaveBeenCalled();
});
