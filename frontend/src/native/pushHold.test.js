import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { usePushHold } from './pushHold';

global.IS_REACT_ACT_ENVIRONMENT = true;

let container;
let root;
let deferIfHeld;
let run;

function Probe(props) {
  deferIfHeld = usePushHold(props);
  return null;
}
const render = (props) => act(() => root.render(<Probe run={run} {...props} />));

beforeEach(() => {
  run = jest.fn();
  container = document.createElement('div');
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
});

test('defers while held and runs nothing yet', () => {
  render({ held: true, active: true });
  expect(deferIfHeld()).toBe(true);
  expect(run).not.toHaveBeenCalled();
});

test('does not defer when nothing is held', () => {
  render({ held: false, active: true });
  expect(deferIfHeld()).toBe(false);
  render({ held: false, active: true });
  expect(run).not.toHaveBeenCalled();
});

test('close while a run is pending triggers exactly one run', () => {
  render({ held: true, active: true });
  deferIfHeld();
  deferIfHeld();
  render({ held: false, active: true });
  render({ held: false, active: true });
  expect(run).toHaveBeenCalledTimes(1);
  // The released run is not held again.
  expect(deferIfHeld()).toBe(false);
});

test('manual close with nothing pending triggers no run', () => {
  render({ held: true, active: true });
  render({ held: false, active: true });
  expect(run).not.toHaveBeenCalled();
});

test('token null clears pending', () => {
  render({ held: true, active: true });
  deferIfHeld();
  render({ held: false, active: false });
  render({ held: false, active: true });
  expect(run).not.toHaveBeenCalled();
});

test('release uses the latest run callback', () => {
  render({ held: true, active: true });
  deferIfHeld();
  const latest = jest.fn();
  render({ held: false, active: true, run: latest });
  expect(run).not.toHaveBeenCalled();
  expect(latest).toHaveBeenCalledTimes(1);
});
