import { act } from 'react';
import { createRoot } from 'react-dom/client';
import SettingsNotifications from './SettingsNotifications';
import Settings from './Settings';
import api from '../api/api';

// jest has no '@/' alias (only webpack does); stand in for the helper module the ui/* components import.
jest.mock('@/lib/utils', () => ({
  cn: (...a) => a.filter((x) => typeof x === 'string').join(' '),
  keepOpenOnToastInteract: (fn) => fn,
}), { virtual: true });
jest.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false, getPlatform: () => 'web', isPluginAvailable: () => false },
  registerPlugin: jest.fn(() => ({})),
}));
jest.mock('@capacitor/push-notifications', () => ({
  PushNotifications: { checkPermissions: jest.fn(), requestPermissions: jest.fn(), register: jest.fn(), addListener: jest.fn() },
}));
jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k, d) => (typeof d === 'string' ? d : k), i18n: { language: 'tr' } }),
}));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));
jest.mock('../api/api', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));
jest.mock('./LiveActivitySettings', () => ({
  __esModule: true,
  default: ({ onOpenConsent }) => (
    <div data-testid="la-settings" onClick={onOpenConsent}>LA-SETTINGS</div>
  ),
}));

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;

const q = (sel) => container.querySelector(sel);
const text = () => container.textContent;

beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { subscribed: true } });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

async function renderNotifications(props = {}) {
  await act(async () => {
    root.render(<SettingsNotifications onNavigate={jest.fn()} onOpenLiveActivityConsent={jest.fn()} {...props} />);
  });
}

async function renderSettings(props = {}) {
  await act(async () => {
    root.render(<Settings onNavigate={jest.fn()} userRole="admin" onLogout={jest.fn()} {...props} />);
  });
}

test('inner page shows push switch, repair row and live activity section', async () => {
  await renderNotifications();
  expect(q('[role="switch"]')).not.toBeNull();
  expect(q('[role="switch"]').getAttribute('aria-checked')).toBe('true');
  expect(text()).toContain('settings.notificationsRepair');
  expect(q('[data-testid="la-settings"]')).not.toBeNull();
});

test('live activity section receives the consent opener', async () => {
  const onOpenLiveActivityConsent = jest.fn();
  await renderNotifications({ onOpenLiveActivityConsent });
  await act(async () => { q('[data-testid="la-settings"]').click(); });
  expect(onOpenLiveActivityConsent).toHaveBeenCalledTimes(1);
});

test('back arrow navigates to settings', async () => {
  const onNavigate = jest.fn();
  await renderNotifications({ onNavigate });
  await act(async () => { q('button').click(); });
  expect(onNavigate).toHaveBeenCalledWith('settings');
});

test('switching push off calls the unsubscribe endpoint', async () => {
  api.delete.mockResolvedValue({});
  await renderNotifications();
  await act(async () => { q('[role="switch"]').click(); });
  expect(api.delete).toHaveBeenCalledWith('/push/unsubscribe');
});

test('settings main page shows Bildirim Ayarları row and no notification switch', async () => {
  await renderSettings();
  expect(text()).toContain('settings.notificationSettings');
  expect(text()).toContain('settings.notificationSettingsSubtitle');
  expect(q('[role="switch"]')).toBeNull();
  expect(q('[data-testid="la-settings"]')).toBeNull();
  expect(text()).not.toContain('settings.notificationsRepair');
});

test('Bildirim Ayarları row navigates to settings-notifications', async () => {
  const onNavigate = jest.fn();
  await renderSettings({ onNavigate });
  const row = [...container.querySelectorAll('div.cursor-pointer')]
    .find((el) => el.textContent.includes('settings.notificationSettings'));
  await act(async () => { row.click(); });
  expect(onNavigate).toHaveBeenCalledWith('settings-notifications');
});
