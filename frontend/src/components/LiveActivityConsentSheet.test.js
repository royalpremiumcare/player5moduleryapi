import { act } from 'react';
import { createRoot } from 'react-dom/client';
import LiveActivityConsentSheet from './LiveActivityConsentSheet';
import * as la from '../native/liveActivities';

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
jest.mock('../native/liveActivities', () => ({ getStatus: jest.fn() }));

global.IS_REACT_ACT_ENVIRONMENT = true;

const jwt = (sub) => `h.${btoa(JSON.stringify({ sub }))}.s`;
let container;
let root;

async function render(props) {
  await act(async () => {
    root.render(<LiveActivityConsentSheet orgFlagEnabled {...props} />);
  });
}
const dialog = () => document.body.querySelector('[role="dialog"]');
const button = (label) => [...document.body.querySelectorAll('button')].find((b) => b.textContent.trim() === label);

beforeEach(() => {
  jest.restoreAllMocks();
  localStorage.clear();
  la.getStatus.mockResolvedValue({ supported: true, enabled: true });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('shown once after login, never before login', async () => {
  await render({ token: null });
  expect(dialog()).toBeNull();

  await render({ token: jwt('u1') });
  expect(dialog()).not.toBeNull();

  await act(async () => button('Şimdi değil').click());
  expect(dialog()).toBeNull();
  expect(localStorage.getItem('la_consent_seen:u1')).toBe('1');

  // remount (next app launch): already seen
  act(() => root.unmount());
  root = createRoot(container);
  await render({ token: jwt('u1') });
  expect(dialog()).toBeNull();

  // another user on the same device still gets it
  await render({ token: jwt('u2') });
  expect(dialog()).not.toBeNull();
});

test('not shown when flag off or plugin unsupported', async () => {
  await render({ token: jwt('u1'), orgFlagEnabled: false });
  expect(dialog()).toBeNull();
  la.getStatus.mockResolvedValue({ supported: false });
  await render({ token: jwt('u1'), orgFlagEnabled: true });
  expect(dialog()).toBeNull();
});

test('copy is verbatim', async () => {
  await render({ token: jwt('u1') });
  const d = dialog();
  expect(d.textContent).toContain('Randevularınız kilit ekranında');
  expect(d.textContent).toContain(
    'Sıradaki randevunuz kilit ekranında ve Dynamic Island\'da geri sayımla görünür. Saati gelince kendiliğinden "İşlemde" olur.'
  );
  expect(d.textContent).toContain(
    'iOS izin isteyecek. İleride "izin vermeyi sürdürmek istiyor musunuz?" diye tekrar sorabilir. Sorarsa Her Zaman İzin Ver\'i seçin, yoksa randevular kilit ekranına gelmez.'
  );
  expect(button('Devam')).toBeTruthy();
  expect(button('Şimdi değil')).toBeTruthy();
});

test('Şimdi değil dismisses and records seen', async () => {
  await render({ token: jwt('u1') });
  await act(async () => button('Şimdi değil').click());
  expect(dialog()).toBeNull();
  expect(localStorage.getItem('la_consent_seen:u1')).toBe('1');
});

test('Devam dismisses and records seen', async () => {
  await render({ token: jwt('u1') });
  await act(async () => button('Devam').click());
  expect(dialog()).toBeNull();
  expect(localStorage.getItem('la_consent_seen:u1')).toBe('1');
});

test('localStorage failure still renders and dismisses', async () => {
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied'); });
  await render({ token: jwt('u1') });
  expect(dialog()).not.toBeNull();
  await act(async () => button('Şimdi değil').click());
  expect(dialog()).toBeNull();
});

test('manual open from settings works even when already seen', async () => {
  localStorage.setItem('la_consent_seen:u1', '1');
  const onManualClose = jest.fn();
  await render({ token: jwt('u1'), manualOpen: true, onManualClose });
  expect(dialog()).not.toBeNull();
  await act(async () => button('Devam').click());
  expect(onManualClose).toHaveBeenCalled();
});
