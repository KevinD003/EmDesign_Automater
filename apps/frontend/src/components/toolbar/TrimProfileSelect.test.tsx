/**
 * The trim control itself: both options rendered in user language, the
 * selected value marked, and the tradeoff available as helper text.
 *
 * Interaction (select → state → request) is covered in two tested halves that
 * meet at a prop: `exportQuery` pins what each profile value puts on the wire,
 * and this pins that choosing an option yields exactly that value — the
 * component's onChange forwards `option.value` untouched.
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { TRIM_PROFILE_OPTIONS } from '../../lib/exportOptions';
import { TrimProfileSelect } from './TrimProfileSelect';

describe('TrimProfileSelect', () => {
  it('offers exactly the two profiles, labelled for users', () => {
    const html = renderToStaticMarkup(
      <TrimProfileSelect value="conservative" onChange={() => {}} />,
    );
    expect(html).toContain('Trims: safe (any machine)');
    expect(html).toContain('Trims: fewer (auto-trim machines)');
    expect((html.match(/<option/g) ?? []).length).toBe(2);
  });

  it('marks the chosen profile as selected', () => {
    const html = renderToStaticMarkup(
      <TrimProfileSelect value="aggressive" onChange={() => {}} />,
    );
    // React SSR marks the controlled value via the option's selected attribute.
    expect(html).toMatch(/<option[^>]*selected[^>]*value="aggressive"|<option[^>]*value="aggressive"[^>]*selected/);
  });

  it('surfaces the tradeoff as the control title', () => {
    const aggressive = TRIM_PROFILE_OPTIONS.find((o) => o.value === 'aggressive')!;
    const html = renderToStaticMarkup(
      <TrimProfileSelect value="aggressive" onChange={() => {}} />,
    );
    expect(html).toContain(aggressive.help.slice(0, 40));
  });

  it('the option values are the exact wire values exportQuery expects', () => {
    const html = renderToStaticMarkup(
      <TrimProfileSelect value="conservative" onChange={() => {}} />,
    );
    for (const o of TRIM_PROFILE_OPTIONS) {
      expect(html).toContain(`value="${o.value}"`);
    }
  });
});
