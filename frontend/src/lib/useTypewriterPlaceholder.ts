import { useEffect, useState } from 'react';

/**
 * Types a phrase out character by character, holds it, deletes it, then moves to the next one.
 *
 * Used as the search bar's typing indicator: the returned string is rendered as a
 * placeholder-style overlay, so nothing here is tied to a specific input element.
 *
 * Starts empty on the first render, so it never causes a hydration mismatch; the animation
 * only begins inside the effect. `prefers-reduced-motion` shows the first phrase statically.
 */
export interface TypewriterOptions {
  /** Milliseconds per typed character. */
  typeMs?: number;
  /** Milliseconds per deleted character. */
  deleteMs?: number;
  /** Pause once a phrase is fully typed. */
  holdMs?: number;
  /** Pause before the first character appears. */
  startDelayMs?: number;
  /** Stop after the last phrase instead of cycling forever. */
  loop?: boolean;
  /** Pause the animation (e.g. while the field has content). */
  paused?: boolean;
}

export function useTypewriterPlaceholder(
  phrases: readonly string[],
  options: TypewriterOptions = {},
): string {
  const {
    typeMs = 42,
    deleteMs = 16,
    holdMs = 1700,
    startDelayMs = 500,
    loop = true,
    paused = false,
  } = options;
  const [text, setText] = useState('');

  // Depend on the phrases' content, not the array identity, so a caller that rebuilds the
  // list on every render does not restart the animation each time.
  const key = phrases.join('\u0000');

  useEffect(() => {
    const list = key.split('\u0000').filter((phrase) => phrase.length > 0);
    if (list.length === 0 || paused) {
      setText('');
      return;
    }
    const prefersReducedMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setText(list[0] ?? '');
      return;
    }

    let cancelled = false;
    let timer = 0;
    let phraseIndex = 0;
    let chars = 0;
    let deleting = false;

    const tick = () => {
      if (cancelled) return;
      const current = list[phraseIndex % list.length] ?? '';

      if (!deleting) {
        chars += 1;
        setText(current.slice(0, chars));
        if (chars >= current.length) {
          if (!loop && phraseIndex === list.length - 1) return;
          deleting = true;
          timer = window.setTimeout(tick, holdMs);
          return;
        }
        timer = window.setTimeout(tick, typeMs);
        return;
      }

      chars -= 1;
      setText(current.slice(0, Math.max(chars, 0)));
      if (chars <= 0) {
        deleting = false;
        phraseIndex += 1;
        timer = window.setTimeout(tick, typeMs);
        return;
      }
      timer = window.setTimeout(tick, deleteMs);
    };

    timer = window.setTimeout(tick, startDelayMs);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [key, typeMs, deleteMs, holdMs, startDelayMs, loop, paused]);

  return text;
}
