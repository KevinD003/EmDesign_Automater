import { describe, expect, it } from 'vitest';
import { parseRoute } from './routes';

describe('parseRoute', () => {
  it('defaults to studio', () => {
    expect(parseRoute('')).toEqual({ page: 'studio' });
    expect(parseRoute('#/')).toEqual({ page: 'studio' });
    expect(parseRoute('#/nonsense')).toEqual({ page: 'studio' });
  });

  it('parses dashboard sections and falls back to overview', () => {
    expect(parseRoute('#/dashboard')).toEqual({ page: 'dashboard', section: 'overview' });
    expect(parseRoute('#/dashboard/analytics')).toEqual({ page: 'dashboard', section: 'analytics' });
    expect(parseRoute('#/dashboard/admin')).toEqual({ page: 'dashboard', section: 'admin' });
    expect(parseRoute('#/dashboard/bogus')).toEqual({ page: 'dashboard', section: 'overview' });
  });

  it('extracts the reset token exactly as mailed', () => {
    // The mailer writes /#/reset?token=… — this parse IS the email contract.
    expect(parseRoute('#/reset?token=abc_DEF-123')).toEqual({ page: 'reset', token: 'abc_DEF-123' });
    expect(parseRoute('#/reset')).toEqual({ page: 'reset', token: '' });
  });

  it('parses auth pages', () => {
    expect(parseRoute('#/login')).toEqual({ page: 'login' });
    expect(parseRoute('#/signup')).toEqual({ page: 'signup' });
    expect(parseRoute('#/forgot')).toEqual({ page: 'forgot' });
  });
});
