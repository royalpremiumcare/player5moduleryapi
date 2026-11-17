import { parseAppDeepLink } from './deepLinks';

describe('parseAppDeepLink', () => {
  it('parses new-appointment with source', () => {
    expect(parseAppDeepLink('plannapp://new-appointment?source=widget_small')).toEqual({
      kind: 'new-appointment',
      source: 'widget_small',
    });
    expect(parseAppDeepLink('plannapp://new-appointment?source=widget_lock').source).toBe('widget_lock');
    expect(parseAppDeepLink('plannapp://new-appointment')).toEqual({ kind: 'new-appointment', source: null });
  });

  it('parses appointment id', () => {
    expect(parseAppDeepLink('plannapp://appointment/123')).toEqual({ kind: 'appointment', id: '123' });
    expect(parseAppDeepLink('plannapp://appointment/ab%20c?x=1')).toEqual({ kind: 'appointment', id: 'ab c' });
  });

  it('rejects other schemes and empty id', () => {
    expect(parseAppDeepLink('https://app.plann.com/appointment/1')).toBeNull();
    expect(parseAppDeepLink('other://appointment/1')).toBeNull();
    expect(parseAppDeepLink('plannapp://appointment/')).toBeNull();
    expect(parseAppDeepLink('plannapp://appointment')).toBeNull();
    expect(parseAppDeepLink('plannapp://appointment/%E0%A4%A')).toBeNull();
    expect(parseAppDeepLink(undefined)).toBeNull();
    expect(parseAppDeepLink('')).toBeNull();
  });

  it('checkout links not claimed', () => {
    expect(parseAppDeepLink('plannapp://checkout/success')).toBeNull();
    expect(parseAppDeepLink('plannapp://checkout/cancel?session_id=x')).toBeNull();
  });
});
