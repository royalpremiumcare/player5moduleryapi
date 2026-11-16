import { act } from 'react';
import { createRoot } from 'react-dom/client';
import LiveActivitySettings from './LiveActivitySettings';
import api from '../api/api';
import * as la from '../native/liveActivities';
import { toast } from 'sonner';

// jest has no '@/' alias (only webpack does); stand in for the one helper module the ui/* components import.
jest.mock('@/lib/utils', () => ({
  cn: (...a) => a.filter((x) => typeof x === 'string').join(' '),
  keepOpenOnToastInteract: (fn) => fn,
}), { virtual: true });
jest.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => true, getPlatform: () => 'ios', isPluginAvailable: () => true },
  registerPlugin: jest.fn(() => ({})),
}));
jest.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k, d) => d ?? k }) }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('../api/api', () => ({ __esModule: true, default: { get: jest.fn(), put: jest.fn() } }));
jest.mock('../native/liveActivities', () => ({ getStatus: jest.fn(), openSettings: jest.fn() }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const OWNER = { enabled: true, scope: 'all', slot_count: 4, start_alert: false, can_choose_scope: true, can_choose_slots: true };
let container;
let root;

async function render(props = {}) {
  await act(async () => {
    root.render(<LiveActivitySettings onOpenConsent={jest.fn()} {...props} />);
  });
}

const text = () => container.textContent;
const q = (sel) => container.querySelector(sel);

beforeEach(() => {
  jest.clearAllMocks();
  la.getStatus.mockResolvedValue({ supported: true, enabled: true });
  api.get.mockResolvedValue({ data: OWNER });
  api.put.mockResolvedValue({ data: { scope: 'all', slot_count: 4, start_alert: true } });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('section hidden when plugin unavailable', async () => {
  la.getStatus.mockResolvedValue(null);
  await render();
  expect(container.innerHTML).toBe('');
});

test('section hidden when plugin reports unsupported', async () => {
  la.getStatus.mockResolvedValue({ supported: false });
  await render();
  expect(container.innerHTML).toBe('');
});

test('section hidden when org flag off', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, enabled: false } });
  await render();
  expect(container.innerHTML).toBe('');
});

const SCOPE_TITLE = 'Kimin randevuları gösterilsin?';
const SLOTS_TITLE = 'Kilit ekranında kaç randevu';
const rowOf = (title) => {
  const p = [...container.querySelectorAll('p')].find((x) => x.textContent === title);
  return p ? p.closest('div.flex.items-center.justify-between') : null;
};
const sheet = () => document.body.querySelector('[role="dialog"]');
const sheetOptions = () => [...(sheet()?.querySelectorAll('button[data-option]') || [])];
const clickRow = (title) => act(async () => { rowOf(title).click(); });
const chooseOption = (value) => act(async () => {
  sheetOptions().find((b) => b.dataset.option === String(value)).click();
});

test('rows render with icons and current values in subtitles', async () => {
  await render();
  expect(text()).toContain('Canlı bildirimler');
  const scope = rowOf(SCOPE_TITLE);
  expect(scope.querySelector('svg')).not.toBeNull();
  expect(scope.textContent).toContain('Tüm personelin randevuları');
  const slots = rowOf(SLOTS_TITLE);
  expect(slots.querySelector('svg')).not.toBeNull();
  expect(slots.textContent).toContain('4');
  expect(rowOf('Randevu başladığında sesli uyarı').querySelector('svg')).not.toBeNull();
  expect(q('[role="switch"]')).not.toBeNull();
  expect(rowOf('Nasıl çalışır?').querySelector('svg')).not.toBeNull();
});

test('no radio inputs or select remain', async () => {
  await render();
  expect(q('[role="radiogroup"]')).toBeNull();
  expect(q('[role="radio"]')).toBeNull();
  expect(q('input[type="radio"]')).toBeNull();
  expect(q('select')).toBeNull();
});

test('uses the owner-approved labels', async () => {
  await render();
  expect(text()).toContain('Canlı bildirimler');
  expect(text()).toContain('Kimin randevuları gösterilsin?');
  expect(text()).toContain('Randevu başladığında sesli uyarı');
  await clickRow(SCOPE_TITLE);
  expect(sheet().textContent).toContain('Sadece benim randevularım');
  expect(sheet().textContent).toContain('Tüm personelin randevuları');
});

test('plain staff sees only alert and how-it-works', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, scope: 'own', slot_count: 1, can_choose_scope: false, can_choose_slots: false } });
  await render();
  expect(rowOf(SCOPE_TITLE)).toBeNull();
  expect(rowOf(SLOTS_TITLE)).toBeNull();
  expect(q('[role="switch"]')).not.toBeNull();
});

test('scope row hidden when the server does not let the user choose', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, can_choose_scope: false } });
  await render();
  expect(rowOf(SCOPE_TITLE)).toBeNull();
  expect(rowOf(SLOTS_TITLE)).not.toBeNull();
});

test('scope row opens choice sheet and saves selection', async () => {
  await render();
  await clickRow(SCOPE_TITLE);
  expect(sheet()).not.toBeNull();
  const own = sheetOptions().find((b) => b.dataset.option === 'own');
  const all = sheetOptions().find((b) => b.dataset.option === 'all');
  expect(all.querySelector('svg')).not.toBeNull(); // check on the current value
  expect(own.querySelector('svg')).toBeNull();
  await chooseOption('own');
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { scope: 'own' });
  expect(toast.success).toHaveBeenCalled();
  expect(sheet()).toBeNull();
});

test('slot row hidden when scope own', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, scope: 'own', slot_count: 1 } });
  await render();
  expect(rowOf(SCOPE_TITLE)).not.toBeNull();
  expect(rowOf(SLOTS_TITLE)).toBeNull();
});

test('slot row appears once scope is switched to all', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, scope: 'own', slot_count: 1 } });
  api.put.mockResolvedValue({ data: { scope: 'all', slot_count: 4, start_alert: false } });
  await render();
  await clickRow(SCOPE_TITLE);
  await chooseOption('all');
  expect(rowOf(SLOTS_TITLE)).not.toBeNull();
  expect(rowOf(SLOTS_TITLE).textContent).toContain('4');
});

test('slot choice offers 1..5 and saves', async () => {
  await render();
  await clickRow(SLOTS_TITLE);
  expect(sheetOptions().map((b) => b.dataset.option)).toEqual(['1', '2', '3', '4', '5']);
  await chooseOption(2);
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { slot_count: 2 });
});

test('slot choice saves and rolls back on error', async () => {
  api.put.mockRejectedValue(new Error('boom'));
  await render();
  await clickRow(SLOTS_TITLE);
  await chooseOption(2);
  expect(toast.error).toHaveBeenCalled();
  expect(rowOf(SLOTS_TITLE).textContent).toContain('4');
  expect(rowOf(SLOTS_TITLE).textContent).not.toContain('2');
});

test('start alert switch saves via preferences endpoint', async () => {
  await render();
  await act(async () => { q('[role="switch"]').click(); });
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { start_alert: true });
  expect(toast.success).toHaveBeenCalled();
});

test('save failure shows an error toast and keeps the old value', async () => {
  api.put.mockRejectedValue(new Error('boom'));
  await render();
  await act(async () => { q('[role="switch"]').click(); });
  expect(toast.error).toHaveBeenCalled();
  expect(q('[role="switch"]').getAttribute('aria-checked')).toBe('false');
});

test('disabled banner deep-links to iOS settings', async () => {
  la.getStatus.mockResolvedValue({ supported: true, enabled: false });
  await render();
  const btn = [...container.querySelectorAll('button')].find((b) => b.textContent.includes('iOS Ayarlarını Aç'));
  expect(btn).toBeTruthy();
  await act(async () => {
    btn.click();
  });
  expect(la.openSettings).toHaveBeenCalled();
});

test('no banner when enabled', async () => {
  await render();
  expect(text()).not.toContain('iOS Ayarlarını Aç');
});

test('how it works row opens consent', async () => {
  const onOpenConsent = jest.fn();
  await render({ onOpenConsent });
  await clickRow('Nasıl çalışır?');
  expect(onOpenConsent).toHaveBeenCalled();
});

describe('returning from iOS Settings', () => {
  function setVisibility(state) {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  }
  afterEach(() => setVisibility('visible'));

  test('re-reads the status when the page becomes visible again', async () => {
    la.getStatus.mockResolvedValue({ supported: true, enabled: false });
    await render();
    expect(text()).toContain('iOS Ayarlarını Aç');

    la.getStatus.mockResolvedValue({ supported: true, enabled: true });
    setVisibility('hidden');
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(text()).toContain('iOS Ayarlarını Aç');

    setVisibility('visible');
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(text()).not.toContain('iOS Ayarlarını Aç');
    expect(api.get).toHaveBeenCalledTimes(1); // preferences are not refetched
  });

  test('stops listening after unmount', async () => {
    await render();
    act(() => root.unmount());
    la.getStatus.mockClear();
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    expect(la.getStatus).not.toHaveBeenCalled();
    root = createRoot(container); // afterEach unmounts again
  });
});
