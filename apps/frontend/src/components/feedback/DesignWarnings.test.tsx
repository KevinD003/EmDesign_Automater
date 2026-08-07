/**
 * Gate 3 of Part 60: the backend's warnings are visible when present and
 * absent when not — including the Part 59 colour-limit message, verbatim.
 *
 * Rendered with react-dom/server so the test runs in the repo's node test
 * environment with no DOM harness: what is asserted is the actual markup the
 * component produces, not a stubbed abstraction of it.
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { DesignWarnings } from './DesignWarnings';

const COLOUR_LIMIT_WARNING =
  'Colour limit: 12 colours were requested, but colour planning uses at most 8 — ' +
  'this design was planned with 8. Values above 8 do not change the result.';

describe('DesignWarnings', () => {
  it('renders every backend warning verbatim, colour-limit message included', () => {
    const html = renderToStaticMarkup(
      <DesignWarnings warnings={[COLOUR_LIMIT_WARNING, 'Another warning']} />,
    );
    expect(html).toContain('design-warnings');
    expect(html).toContain('role="status"');
    expect(html).toContain('colour planning uses at most 8');
    expect(html).toContain('Values above 8 do not change the result.');
    expect(html).toContain('Another warning');
  });

  it('renders nothing at all when there are no warnings', () => {
    expect(renderToStaticMarkup(<DesignWarnings warnings={[]} />)).toBe('');
    expect(renderToStaticMarkup(<DesignWarnings warnings={undefined} />)).toBe('');
    expect(renderToStaticMarkup(<DesignWarnings warnings={null} />)).toBe('');
  });
});
