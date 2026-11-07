import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAnalysisEvents, type AnalysisEvent } from './hooks';

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  closed = false;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  private listeners = new Map<string, ((ev: Event) => void)[]>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (ev: Event) => void) {
    const arr = this.listeners.get(type) ?? [];
    arr.push(listener);
    this.listeners.set(type, arr);
  }

  emit(type: string, data: AnalysisEvent) {
    const msg = new MessageEvent(type, { data: JSON.stringify(data) });
    if (type === 'message' && this.onmessage) {
      this.onmessage(msg);
    }
    const list = this.listeners.get(type) ?? [];
    for (const fn of list) {
      fn(msg);
    }
  }

  close() {
    this.closed = true;
  }
}

describe('useAnalysisEvents', () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal('EventSource', MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('tracks stage events, researchSteps, invalidates query on stage_completed, and closes on completed', () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useAnalysisEvents('ana-123'), { wrapper });

    expect(MockEventSource.instances).toHaveLength(1);
    const es = MockEventSource.instances[0];
    expect(es.url).toBe('/api/analyses/ana-123/events?after_seq=0');

    act(() => {
      es.emit('stage_started', {
        analysis_id: 'ana-123',
        seq: 1,
        ts: '2026-11-07T16:45:00Z',
        type: 'stage_started',
        stage: 'researching',
        message: 'Started researching',
      });
    });

    expect(result.current.stage).toBe('researching');

    act(() => {
      es.emit('research_step', {
        analysis_id: 'ana-123',
        seq: 2,
        ts: '2026-11-07T16:45:01Z',
        type: 'research_step',
        stage: 'researching',
        message: 'Search step',
        data: {
          step_id: 1,
          ts: '2026-11-07T16:45:01Z',
          kind: 'search',
          title: 'Searching OBR corporation tax elasticity',
          detail: 'Grounded Google Search',
          query: 'OBR corporation tax elasticity',
          source_ids: ['S1'],
          evidence_ids: [],
        },
      });
    });

    expect(result.current.researchSteps).toHaveLength(1);
    expect(result.current.researchSteps[0].title).toBe(
      'Searching OBR corporation tax elasticity',
    );

    act(() => {
      es.emit('stage_completed', {
        analysis_id: 'ana-123',
        seq: 3,
        ts: '2026-11-07T16:45:02Z',
        type: 'stage_completed',
        stage: 'researching',
        message: 'Completed researching',
      });
    });

    expect(result.current.stagesDone).toContain('researching');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['analysis', 'ana-123'] });

    act(() => {
      es.emit('completed', {
        analysis_id: 'ana-123',
        seq: 4,
        ts: '2026-11-07T16:45:05Z',
        type: 'completed',
        stage: null,
        message: 'Analysis completed',
      });
    });

    expect(result.current.done).toBe(true);
    expect(es.closed).toBe(true);
  });
});
