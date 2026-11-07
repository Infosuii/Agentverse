import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  EvidenceBadge,
  PlaceholderBadge,
  Stat,
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
});
