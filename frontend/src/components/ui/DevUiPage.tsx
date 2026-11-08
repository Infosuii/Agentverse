import { useState } from 'react';
import {
  Badge,
  Card,
  EmptyState,
  ErrorBoundary,
  EvidenceBadge,
  InlineError,
  ModeBadge,
  PlaceholderBadge,
  Skeleton,
  SourceChip,
  Spinner,
  Stat,
  Table,
  Tabs,
  Tooltip,
  VerificationBadge,
  WithheldBanner,
} from './index';
import type { Source } from '../../api/hooks';
import { fmtDate, fmtFiscalYear, fmtGbpBn, fmtPct, fmtPp } from '../../lib/format';
import {
  EVIDENCE_CLASS_TOKENS,
  SCENARIO_COLORS,
  VERIFICATION_STATUS_TOKENS,
  type EvidenceClassKey,
  type ScenarioColorKey,
  type VerificationStatusKey,
} from '../../lib/theme';

const SAMPLE_SOURCES: Source[] = [
  {
    source_id: 'S1',
    title: 'Economic and Fiscal Outlook — March 2026',
    url: 'https://obr.uk/efo/economic-and-fiscal-outlook-march-2026/',
    publisher: 'OBR',
    publisher_type: 'obr',
    published_date: '2026-03-15',
    retrieved_at: '2026-11-07T16:45:00Z',
    access_method: 'url_fetch',
    reliability_tier: 1,
    url_verified: true,
    content_sha256: 'abc123',
    is_placeholder: false,
  },
  {
    source_id: 'S2',
    title: 'Taxable income elasticities and corporate tax responses in the UK',
    url: 'https://ifs.org.uk/publications/ct-elasticities',
    publisher: 'IFS',
    publisher_type: 'ifs',
    published_date: '2023-06-01',
    retrieved_at: '2026-11-07T16:45:00Z',
    access_method: 'google_search',
    reliability_tier: 2,
    url_verified: true,
    content_sha256: null,
    is_placeholder: false,
  },
  {
    source_id: 'D-obr-baseline',
    title: 'Curated OBR Baseline Projection',
    url: 'https://obr.uk/data/',
    publisher: 'OBR',
    publisher_type: 'obr',
    published_date: '2026-03-15',
    retrieved_at: null,
    access_method: 'curated_dataset',
    reliability_tier: 1,
    url_verified: true,
    content_sha256: null,
    is_placeholder: true,
  },
];

export function DevUiPage() {
  const [activeTab, setActiveTab] = useState('tab-1');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">
          UI Primitives & Design System Gallery (`/dev/ui`)
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Reference gallery for shared primitives in <code>src/components/ui/</code>,
          tokens in <code>src/lib/theme.ts</code>, and formatters in{' '}
          <code>src/lib/format.ts</code>.
        </p>
      </div>

      <Card title="1. Evidence-Class Badges & Theme Tokens">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {(Object.keys(EVIDENCE_CLASS_TOKENS) as EvidenceClassKey[]).map((key) => (
              <EvidenceBadge key={key} evidenceClass={key} />
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            {(Object.keys(SCENARIO_COLORS) as ScenarioColorKey[]).map((key) => (
              <span
                key={key}
                className="inline-flex items-center gap-1.5 rounded border border-border px-2.5 py-1 font-medium"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: SCENARIO_COLORS[key] }}
                />
                <span>
                  {key}: <code>{SCENARIO_COLORS[key]}</code>
                </span>
              </span>
            ))}
          </div>
        </div>
      </Card>

      <Card title="2. Mode, Verification, Placeholder & Generic Badges">
        <div className="flex flex-wrap items-center gap-2">
          <ModeBadge mode="mock" />
          <ModeBadge mode="cached" />
          <ModeBadge mode="live" />
          <PlaceholderBadge />
          <VerificationBadge overall="approved" />
          <VerificationBadge overall="approved_with_warnings" />
          <VerificationBadge overall="forecast_withheld" />
          {(Object.keys(VERIFICATION_STATUS_TOKENS) as VerificationStatusKey[]).map(
            (st) => (
              <VerificationBadge key={st} status={st} />
            ),
          )}
          <Badge variant="slate">Slate</Badge>
          <Badge variant="blue">Blue</Badge>
          <Badge variant="violet">Violet</Badge>
          <Badge variant="rose">Rose</Badge>
        </div>
      </Card>

      <Card title="3. SourceChip & Tooltip">
        <div className="flex flex-wrap items-center gap-3">
          <SourceChip sourceId="S1" sources={SAMPLE_SOURCES} />
          <SourceChip sourceId="S2" sources={SAMPLE_SOURCES} />
          <SourceChip sourceId="D-obr-baseline" sources={SAMPLE_SOURCES} />
          <SourceChip sourceId="S99" sources={SAMPLE_SOURCES} />
          <Tooltip content="Explicit provenance hover tooltip">
            <span className="cursor-help underline decoration-dotted text-xs text-foreground/85">
              Hover or focus for tooltip
            </span>
          </Tooltip>
        </div>
      </Card>

      <Card title="4. Stat Tiles (Standard, Low Confidence, Withheld)">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Stat
            label="Behavioural Revenue (2027-28)"
            value={fmtGbpBn(3.1)}
            range={`${fmtGbpBn(2.1)} to ${fmtGbpBn(4.0)}`}
            sublabel="Exchequer impact (+ = revenue raised)"
            evidenceClass="model_scenario"
            confidence="medium"
            provenance="Step rev.behav.2027-28 · Sources [S1, D-obr-baseline]"
          />
          <Stat
            label="GDP Level (Year 5)"
            value={fmtPct(-0.08)}
            sublabel="Partial equilibrium capital-stock channel"
            evidenceClass="model_scenario"
            confidence="low"
            isPlaceholder
          />
          <Stat
            label="Withheld Metric Example"
            value={fmtGbpBn(9.9)}
            evidenceClass="model_scenario"
            withheld
            withheldReason="Policy change (+20pp) exceeds validated historical range"
          />
        </div>
      </Card>

      <Card title="5. Tabs, Table & Formatters">
        <div className="space-y-4">
          <Tabs
            items={[
              { id: 'tab-1', label: 'Formatted Values' },
              { id: 'tab-2', label: 'Second Tab' },
              { id: 'tab-3', label: 'Disabled Tab', disabled: true },
            ]}
            activeId={activeTab}
            onChange={setActiveTab}
          />
          <Table>
            <thead className="bg-muted/40 text-xs font-semibold text-muted-foreground uppercase">
              <tr>
                <th className="px-4 py-2.5">Helper</th>
                <th className="px-4 py-2.5">Input</th>
                <th className="px-4 py-2.5">Output</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border text-xs">
              <tr>
                <td className="px-4 py-2 font-mono">fmtGbpBn(-0.4)</td>
                <td className="px-4 py-2">-0.4</td>
                <td className="px-4 py-2 font-semibold">{fmtGbpBn(-0.4)}</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono">fmtPct(-0.05)</td>
                <td className="px-4 py-2">-0.05</td>
                <td className="px-4 py-2 font-semibold">{fmtPct(-0.05)}</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono">fmtPp(3)</td>
                <td className="px-4 py-2">3</td>
                <td className="px-4 py-2 font-semibold">{fmtPp(3)}</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono">fmtFiscalYear(&apos;2027-04-01&apos;)</td>
                <td className="px-4 py-2">2027-04-01</td>
                <td className="px-4 py-2 font-semibold">{fmtFiscalYear('2027-04-01')}</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono">fmtDate(&apos;2027-04-01&apos;)</td>
                <td className="px-4 py-2">2027-04-01</td>
                <td className="px-4 py-2 font-semibold">{fmtDate('2027-04-01')}</td>
              </tr>
            </tbody>
          </Table>
        </div>
      </Card>

      <Card title="6. WithheldBanner, EmptyState, Skeleton, InlineError & ErrorBoundary">
        <div className="space-y-4">
          <WithheldBanner
            reasons={[
              'Proposed rate change (+20pp) exceeds the 15pp maximum supported bound.',
              'SCOPE-001 blocking check failed.',
            ]}
          />
          <InlineError
            title="Request failed"
            message="Could not reach simulation service."
            reasons={['Timeout after 2000ms']}
            onRetry={() => undefined}
          />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <EmptyState
              title="No precedents matched"
              description="Adjust the policy parameters to find comparable historical UK tax changes."
            />
            <ErrorBoundary>
              <div className="space-y-3 rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <Spinner size="xs" />
                  <span>Skeleton loading state preview</span>
                </div>
                <Skeleton lines={3} />
              </div>
            </ErrorBoundary>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default DevUiPage;
