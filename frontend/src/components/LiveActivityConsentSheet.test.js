import { act } from 'react';
import { createRoot } from 'react-dom/client';
import LiveActivityConsentSheet from './LiveActivityConsentSheet';
import tr from '../i18n/locales/tr/translation.json';
import en from '../i18n/locales/en/translation.json';

// jest has no '@/' alias (only webpack does); stand in for the one helper module the ui/* components import.
jest.mock('@/lib/utils', () => ({
  cn: (...a) => a.filter((x) => typeof x === 'string').join(' '),
  keepOpenOnToastInteract: (fn) => fn,
}), { virtual: true });

// t() resolves from the shipped Turkish translation file, so the tests check the copy users see.
jest.mock('react-i18next', () => {
  const trJson = jest.requireActual('../i18n/locales/tr/translation.json');
  const lookup = (key) => key.split('.').reduce((o, k) => (o == null ? undefined : o[k]), trJson);
  return { useTranslation: () => ({ t: (k) => lookup(k) ?? k }) };
});

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
let onAllow;
let onLater;

async function render(props) {
  await act(async () => {
    root.render(<LiveActivityConsentSheet open onAllow={onAllow} onLater={onLater} {...props} />);
  });
}
const dialog = () => document.body.querySelector('[role="dialog"]');
const button = (label) => [...document.body.querySelectorAll('button')].find((b) => b.textContent.trim() === label);
const text = (el) => el.textContent.replace(/\s+/g, ' ').trim();

beforeEach(() => {
  onAllow = jest.fn();
  onLater = jest.fn();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('renders the approved Turkish copy', async () => {
  await render();
  const d = dialog();
  expect(d).not.toBeNull();
  expect(text(d)).toContain('Randevularınız kilit ekranında');
  expect(text(d)).toContain(
    'Telefonunuzun kilidini açmadan sıradaki randevunuzu görürsünüz. Kilit ekranında küçük bir kart çıkar ve şunları gösterir:'
  );

  const bullets = [...d.querySelectorAll('ul > li')].map(text);
  expect(bullets).toEqual([
    'Müşterinin adı ve yapılacak işlem',
    'Randevunun başlamasına kaç dakika kaldığı',
    'İşlem başlayınca bitmesine kaç dakika kaldığı',
  ]);

  expect(text(d)).toContain(
    'Kart kendi kendine güncellenir, uygulamayı açmanıza gerek yok. Randevu bitince "Tamamlandı" yazar ve bir süre sonra kaybolur.'
  );
  expect(text(d)).toContain('Bunun için 2 izin gerekiyor:');

  const steps = [...d.querySelectorAll('ol > li')];
  expect(steps.map(text)).toEqual([
    'Şimdi "Bildirim göndermek istiyor" sorusu gelecek. İzin Ver\'e basın.',
    'İlk kart geldiğinde iPhone "izin vermeyi sürdürmek istiyor musunuz?" diye sorabilir. Her Zaman İzin Ver\'i seçin.',
  ]);
  expect(text(steps[0].querySelector('strong'))).toBe('İzin Ver');
  expect(text(steps[1].querySelector('strong'))).toBe('Her Zaman İzin Ver');

  expect(button('Şimdi değil')).toBeTruthy();
  expect(button('İzin ver')).toBeTruthy();
});

test('English strings exist for every Turkish consent key', () => {
  const trKeys = Object.keys(tr.liveActivity.consent).sort();
  expect(Object.keys(en.liveActivity.consent).sort()).toEqual(trKeys);
  expect(trKeys).toEqual(['allow', 'bullets', 'intro', 'later', 'outro', 'permissionsTitle', 'steps', 'title']);
  expect(en.liveActivity.consent.bullets).toHaveLength(3);
  expect(en.liveActivity.consent.steps).toHaveLength(2);
});

test('İzin ver calls onAllow', async () => {
  await render();
  await act(async () => button('İzin ver').click());
  expect(onAllow).toHaveBeenCalledTimes(1);
  expect(onLater).not.toHaveBeenCalled();
});

test('Şimdi değil calls onLater', async () => {
  await render();
  await act(async () => button('Şimdi değil').click());
  expect(onLater).toHaveBeenCalledTimes(1);
  expect(onAllow).not.toHaveBeenCalled();
});

test('Escape calls onLater', async () => {
  await render();
  await act(async () => {
    dialog().dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  });
  expect(onLater).toHaveBeenCalledTimes(1);
  expect(onAllow).not.toHaveBeenCalled();
});

test('closed renders nothing', async () => {
  await render({ open: false });
  expect(dialog()).toBeNull();
  expect(onAllow).not.toHaveBeenCalled();
  expect(onLater).not.toHaveBeenCalled();
});

test('uses theme colour tokens, not fixed zinc/white', async () => {
  await render();
  const own = [button('Şimdi değil'), button('İzin ver')].map((el) => el.className).join(' ');
  expect(own).not.toMatch(/\b(?:text|bg|border)-(?:zinc-\d+|white)\b/);
  expect(button('İzin ver').className).toEqual(expect.stringContaining('bg-primary'));
  expect(button('İzin ver').className).toEqual(expect.stringContaining('text-primary-foreground'));
  expect(button('Şimdi değil').className).toEqual(expect.stringContaining('border-input'));
});
