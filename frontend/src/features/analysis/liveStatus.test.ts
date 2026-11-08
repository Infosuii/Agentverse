import { describe, expect, it } from 'vitest';
import type { Analysis } from '../../api/hooks';
import { resolveActiveStage, stageStatus, tabStatus } from './liveStatus';

function analysisWith(partial: Partial<Analysis>): Analysis {
  return {
    analysis_id: 'live-1',
    created_at: '2026-11-07T12:00:00Z',
    updated_at: '2026-11-07T12:00:05Z',
    status: 'researching',
    mode: 'mock',
    request: { query: 'Raise CT from 25% to 28%' },
    stage_timings_ms: { parsing: 12 },
    ...partial,
  } as Analysis;
}

describe('live analysis status', () => {
  it('prefers the live SSE stage and reports no active stage once terminal', () => {
    const running = analysisWith({ status: 'researching' });
    expect(resolveActiveStage(running, 'precedents')).toBe('precedents');
    expect(resolveActiveStage(running, null)).toBe('researching');
    expect(resolveActiveStage(analysisWith({ status: 'completed' }), 'reporting')).toBeNull();
  });

  it('maps stages to Waiting / Generating / Complete', () => {
    const running = analysisWith({ status: 'researching' });
    expect(stageStatus('parsing', running, [], 'researching')).toBe('complete');
    expect(stageStatus('researching', running, [], 'researching')).toBe('generating');
    expect(stageStatus('verifying', running, [], 'researching')).toBe('waiting');
    expect(stageStatus('verifying', analysisWith({ status: 'failed' }), [], null)).toBe('not_run');
  });

  it('derives view status from the stages that feed each view', () => {
    const running = analysisWith({ status: 'modelling' });
    const done = ['parsing', 'researching', 'precedents'] as const;
    expect(tabStatus('research', running, [...done], 'modelling')).toBe('complete');
    expect(tabStatus('scenarios', running, [...done], 'modelling')).toBe('generating');
    expect(tabStatus('report', running, [...done], 'modelling')).toBe('waiting');
    expect(tabStatus('overview', running, [...done], 'modelling')).toBe('generating');
    expect(tabStatus('overview', analysisWith({ status: 'completed' }), [], null)).toBe('complete');
  });
});
