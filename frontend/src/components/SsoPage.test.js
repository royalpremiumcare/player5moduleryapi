import { act } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import SsoPage from './SsoPage';

// A one-time login code may only be sent once: a second mount (or a re-mount) of the page must
// reuse the first exchange, otherwise the server answers "Code expired or already used" and the
// page shows that error even though the first exchange succeeded (field bug 2026-11-18).
jest.mock('axios', () => ({ __esModule: true, default: { post: jest.fn() } }), { virtual: true });
jest.mock('react-router-dom', () => ({ useLocation: () => ({ search: '?code=abc&redirect=/subscribe' }) }), { virtual: true });

global.IS_REACT_ACT_ENVIRONMENT = true;

const token = `h.${btoa(JSON.stringify({ role: 'admin' }))}.s`;

let roots = [];
let assigned;

beforeEach(() => {
  axios.post.mockReset();
  assigned = [];
  delete window.location;
  window.location = { set href(v) { assigned.push(v); }, get href() { return ''; } };
  sessionStorage.clear();
});

afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
});

async function mount() {
  const el = document.createElement('div');
  document.body.appendChild(el);
  const root = createRoot(el);
  roots.push(root);
  await act(async () => root.render(<SsoPage />));
  return el;
}

test('two mounts send the code once and both redirect, no error shown', async () => {
  let resolve;
  axios.post.mockImplementation(() => new Promise((r) => { resolve = r; }));
  const a = await mount();
  const b = await mount();
  await act(async () => resolve({ data: { access_token: token } }));
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(assigned).toContain('/subscribe');
  expect(a.textContent).not.toContain('already used');
  expect(b.textContent).not.toContain('already used');
  expect(sessionStorage.getItem('authToken')).toBe(token);
});
