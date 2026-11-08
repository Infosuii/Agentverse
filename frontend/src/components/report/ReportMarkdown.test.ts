import { describe, expect, it } from 'vitest';
import { linkCitations } from './ReportMarkdown';

const SOURCES = new Set(['S1', 'S2', 'D-obr-baseline']);

describe('linkCitations', () => {
  it('links known source markers to the source directory', () => {
    expect(linkCitations('Revenue **+£5.20bn** [S1].', SOURCES, 'A1')).toBe(
      'Revenue **+£5.20bn** [\\[S1\\]](#src-S1).',
    );
    expect(linkCitations('Baseline [D-obr-baseline].', SOURCES)).toBe(
      'Baseline [\\[D-obr-baseline\\]](#src-D-obr-baseline).',
    );
  });

  it('links adjacent markers and evidence ids, and leaves unknown sources alone', () => {
    expect(linkCitations('See [S1][S2], [S9] and [E2].', SOURCES, 'A1')).toBe(
      'See [\\[S1\\]](#src-S1)[\\[S2\\]](#src-S2), [S9] and [\\[E2\\]](/analyses/A1/research?evidence=E2).',
    );
  });

  it('does not touch existing links, reference definitions, escapes or code', () => {
    const input = '[S1](https://x) and [S1]: def and \\[S1\\] and `[S1]`';
    expect(linkCitations(input, SOURCES, 'A1')).toBe(input);
  });

  it('keeps evidence markers as text when no analysis id is known', () => {
    expect(linkCitations('Elasticity [E2].', SOURCES)).toBe('Elasticity [E2].');
  });
});
