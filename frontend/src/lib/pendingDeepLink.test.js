import { savePending, takePending, clearPending } from './pendingDeepLink';

const intent = { kind: 'appointment', id: '7' };

describe('pendingDeepLink', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('pending survives until taken once', () => {
    savePending(intent);
    expect(takePending(Date.now())).toEqual(intent);
    expect(takePending(Date.now())).toBeNull();
  });

  it('clearPending removes it', () => {
    savePending(intent);
    clearPending();
    expect(takePending(Date.now())).toBeNull();
  });

  it('pending older than 10 min ignored', () => {
    savePending(intent);
    expect(takePending(Date.now() + 10 * 60 * 1000 + 5000)).toBeNull();
    expect(takePending(Date.now())).toBeNull(); // consumed even when stale
  });

  it('storage throwing is safe', () => {
    const boom = () => { throw new Error('denied'); };
    const s1 = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(boom);
    const s2 = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(boom);
    const s3 = jest.spyOn(Storage.prototype, 'removeItem').mockImplementation(boom);
    expect(() => savePending(intent)).not.toThrow();
    expect(takePending(Date.now())).toBeNull();
    expect(() => clearPending()).not.toThrow();
    [s1, s2, s3].forEach((s) => s.mockRestore());
  });

  it('corrupt payload is ignored', () => {
    window.sessionStorage.setItem('plann_pending_deep_link', '{nope');
    expect(takePending(Date.now())).toBeNull();
  });
});
