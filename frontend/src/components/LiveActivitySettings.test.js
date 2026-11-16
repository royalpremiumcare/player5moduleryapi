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

test('owner sees scope, slots and alert', async () => {
  await render();
  expect(text()).toContain('Canlı bildirimler');
  expect(q('[role="radiogroup"]')).not.toBeNull();
  expect(q('select')).not.toBeNull();
  expect(q('[role="switch"]')).not.toBeNull();
});

test('uses the owner-approved labels', async () => {
  await render();
  expect(text()).toContain('Canlı bildirimler');
  expect(text()).toContain('Sadece benim randevularım');
  expect(text()).toContain('Tüm personelin randevuları');
  expect(text()).toContain('Randevu başladığında sesli uyarı');
});

test('manager sees scope and slots', async () => {
  await render();
  expect(q('[role="radiogroup"]') && q('select')).toBeTruthy();
});

test('plain staff sees only alert', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, scope: 'own', slot_count: 1, can_choose_scope: false, can_choose_slots: false } });
  await render();
  expect(q('[role="radiogroup"]')).toBeNull();
  expect(q('select')).toBeNull();
  expect(q('[role="switch"]')).not.toBeNull();
});

test('scope hidden when admin does not provide service and no staff', async () => {
  api.get.mockResolvedValue({ data: { ...OWNER, can_choose_scope: false } });
  await render();
  expect(q('[role="radiogroup"]')).toBeNull();
  expect(q('select')).not.toBeNull();
});

test('slot count limited to 1..5 default 4', async () => {
  await render();
  const sel = q('select');
  expect([...sel.options].map((o) => o.value)).toEqual(['1', '2', '3', '4', '5']);
  expect(sel.value).toBe('4');
});

test('saves via preferences endpoint', async () => {
  await render();
  await act(async () => {
    q('[role="switch"]').click();
  });
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { start_alert: true });
  expect(toast.success).toHaveBeenCalled();

  await act(async () => {
    [...container.querySelectorAll('[role="radio"]')].find((r) => r.value === 'own').click();
  });
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { scope: 'own' });

  const sel = q('select');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(sel, '2');
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(api.put).toHaveBeenCalledWith('/live-activities/preferences', { slot_count: 2 });
});

test('save failure shows an error toast and keeps the old value', async () => {
  api.put.mockRejectedValue(new Error('boom'));
  await render();
  await act(async () => {
    q('[role="switch"]').click();
  });
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

test('consent link calls onOpenConsent', async () => {
  const onOpenConsent = jest.fn();
  await render({ onOpenConsent });
  const btn = [...container.querySelectorAll('button')].find((b) => b.textContent.includes('Nasıl çalışır'));
  await act(async () => {
    btn.click();
  });
  expect(onOpenConsent).toHaveBeenCalled();
});
