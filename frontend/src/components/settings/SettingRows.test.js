import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Bell } from 'lucide-react';
import { SettingItem } from './SettingRows';

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

function render(props) {
  act(() => {
    root.render(<SettingItem icon={Bell} title="Bildirim Ayarları" {...props} />);
  });
  return container.firstChild;
}

function key(el, type, k) {
  const event = new KeyboardEvent(type, { key: k, bubbles: true, cancelable: true });
  act(() => {
    el.dispatchEvent(event);
  });
  return event;
}

test('a row with onClick is a focusable button for keyboard and VoiceOver', () => {
  const row = render({ onClick: jest.fn() });

  expect(row.getAttribute('role')).toBe('button');
  expect(row.getAttribute('tabindex')).toBe('0');
});

test('Enter activates the row', () => {
  const onClick = jest.fn();
  const row = render({ onClick });

  key(row, 'keydown', 'Enter');

  expect(onClick).toHaveBeenCalledTimes(1);
});

test('Space activates the row once on release and does not scroll the page', () => {
  const onClick = jest.fn();
  const row = render({ onClick });

  const down = key(row, 'keydown', ' ');
  expect(down.defaultPrevented).toBe(true);
  expect(onClick).not.toHaveBeenCalled();

  key(row, 'keyup', ' ');
  expect(onClick).toHaveBeenCalledTimes(1);
});

test('other keys do nothing', () => {
  const onClick = jest.fn();
  const row = render({ onClick });

  key(row, 'keydown', 'a');
  key(row, 'keyup', 'a');

  expect(onClick).not.toHaveBeenCalled();
});

test('keys pressed on a control inside the row do not activate the row', () => {
  const onClick = jest.fn();
  const row = render({ onClick, rightElement: <button type="button">inner</button> });
  const inner = row.querySelector('button');

  key(inner, 'keydown', 'Enter');
  key(inner, 'keydown', ' ');
  key(inner, 'keyup', ' ');

  expect(onClick).not.toHaveBeenCalled();
});

test('a row without onClick renders as before: no role, not focusable', () => {
  const row = render({ rightElement: <span>switch</span> });

  expect(row.hasAttribute('role')).toBe(false);
  expect(row.hasAttribute('tabindex')).toBe(false);
});

test('a mouse click still activates the row', () => {
  const onClick = jest.fn();
  const row = render({ onClick });

  act(() => {
    row.click();
  });

  expect(onClick).toHaveBeenCalledTimes(1);
});
