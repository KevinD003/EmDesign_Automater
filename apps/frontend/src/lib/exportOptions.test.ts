/**
 * The Part 60 export-request contract.
 *
 * Gate 1 of the brief is stated at the REQUEST level on purpose: an untouched
 * control must produce a request byte-identical to what the app sent before
 * the control existed — not merely one the backend treats the same. That is
 * why the default profile is omitted from the URL, and why these tests pin
 * the exact query strings.
 */
import { describe, expect, it } from 'vitest';

import {
  DEFAULT_TRIM_PROFILE,
  TRIM_PROFILE_OPTIONS,
  exportQuery,
} from './exportOptions';

describe('exportQuery', () => {
  it('omits the profile entirely when it is the default', () => {
    expect(exportQuery('dst')).toBe('format=dst');
    expect(exportQuery('dst', 'conservative')).toBe('format=dst');
  });

  it('sends trim_profile=aggressive when the user opted in', () => {
    expect(exportQuery('dst', 'aggressive')).toBe('format=dst&trim_profile=aggressive');
  });

  it('keeps the format value encoded', () => {
    expect(exportQuery('pes', 'aggressive')).toBe('format=pes&trim_profile=aggressive');
    expect(exportQuery('a b')).toBe('format=a+b');
  });
});

describe('the profile catalogue', () => {
  it('defaults to conservative', () => {
    expect(DEFAULT_TRIM_PROFILE).toBe('conservative');
    expect(TRIM_PROFILE_OPTIONS[0].value).toBe('conservative');
  });

  it('labels both profiles in user language, not API values', () => {
    const labels = TRIM_PROFILE_OPTIONS.map((o) => o.label);
    expect(labels.some((l) => l.includes('safe') && l.includes('any machine'))).toBe(true);
    expect(labels.some((l) => l.includes('fewer') && l.includes('auto-trim'))).toBe(true);
    // The wire values never appear in what the user reads.
    for (const l of labels) {
      expect(l).not.toMatch(/conservative|aggressive/);
    }
  });

  it('states the tradeoff in the helper text', () => {
    const safe = TRIM_PROFILE_OPTIONS.find((o) => o.value === 'conservative')!;
    const fewer = TRIM_PROFILE_OPTIONS.find((o) => o.value === 'aggressive')!;
    expect(safe.help).toMatch(/safest|any machine/i);
    expect(fewer.help).toMatch(/auto-trim/i);
    expect(fewer.help).toMatch(/identical/i);
  });
});
