import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  EvidenceBadge,
  PlaceholderBadge,
  Stat,
  Tabs,
  WithheldBanner,
} from './index';

describe('UI primitives', () => {
  it('renders WithheldBanner with decline reasons', () => {
    render(
      <WithheldBanner
        reasons={[
          'Policy rate change (+20pp) exceeds validated historical maximum (15pp).',
          'SCOPE-001 blocking check failed.',
        ]}
      />,
    );

    expect(
      screen.getByRole('alert', { name: /Quantitative forecast withheld/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/exceeds validated historical maximum/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/SCOPE-001 blocking check failed/i)).toBeInTheDocument();
  });

  it('hides numeric value when Stat is in withheld state', () => {
    render(
      <Stat
        label="Behavioural Revenue"
        value="£3.1bn"
        withheld
        withheldReason="Out of scope"
      />,
    );

    expect(screen.queryByText('£3.1bn')).not.toBeInTheDocument();
    expect(screen.getByText('Forecast withheld')).toBeInTheDocument();
    expect(screen.getByText('Out of scope')).toBeInTheDocument();
  });

  it('renders EvidenceBadge and PlaceholderBadge with accessible labels', () => {
    render(
      <div>
        <EvidenceBadge evidenceClass="ai_interpretation" />
        <PlaceholderBadge />
      </div>,
    );

    expect(
      screen.getByLabelText('Evidence class: AI interpretation'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Data status: Placeholder (unverified)'),
    ).toBeInTheDocument();
  });

  it('supports keyboard navigation (ArrowRight, ArrowLeft, Home, End) on Tabs while skipping disabled tabs', () => {
    const onChange = vi.fn();
    render(
      <Tabs
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'research', label: 'Research' },
          { id: 'scenarios', label: 'Scenarios', disabled: true },
          { id: 'report', label: 'Report' },
        ]}
        activeId="research"
        onChange={onChange}
      />,
    );

    const researchTab = screen.getByRole('tab', { name: 'Research' });
    fireEvent.keyDown(researchTab, { key: 'ArrowRight' });
    expect(onChange).toHaveBeenCalledWith('report');

    fireEvent.keyDown(researchTab, { key: 'ArrowLeft' });
    expect(onChange).toHaveBeenCalledWith('overview');

    fireEvent.keyDown(researchTab, { key: 'End' });
    expect(onChange).toHaveBeenCalledWith('report');

    fireEvent.keyDown(researchTab, { key: 'Home' });
    expect(onChange).toHaveBeenCalledWith('overview');
  });
});
