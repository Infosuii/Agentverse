import { useTypewriterPlaceholder } from '../../lib/useTypewriterPlaceholder';
import { ArrowUpIcon, LoaderIcon } from '../ui/icons';

export interface SearchBarProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Enter (without Shift) or the arrow button. */
  onSubmit: () => void;
  onBlur?: () => void;
  /** Prompts cycled by the typing indicator while the field is empty. */
  suggestions?: readonly string[];
  placeholder?: string;
  submitLabel?: string;
  busy?: boolean;
  minLength?: number;
}

/**
 * Large natural-language prompt box (Forecast Confidence Studio search bar).
 * Enter submits; Shift+Enter adds a new line.
 *
 * While the field is empty, `suggestions` are typed out behind the caret as a decorative
 * overlay (never as the textarea's own placeholder), so screen readers still read the
 * label and the animation can be tuned independently of the input.
 */
export function SearchBar({
  id,
  label,
  value,
  onChange,
  onSubmit,
  onBlur,
  suggestions = [],
  placeholder = 'Propose a UK corporation tax policy…',
  submitLabel = 'Start policy analysis',
  busy = false,
  minLength = 3,
}: SearchBarProps) {
  const canSubmit = value.trim().length >= minLength && !busy;
  const showTyping = value.length === 0 && suggestions.length > 0;
  const typed = useTypewriterPlaceholder(suggestions, { paused: !showTyping });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit();
      }}
      className="flex items-end gap-2 rounded-sm border border-input bg-card p-3 transition-colors focus-within:border-primary"
    >
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative min-h-[3.5rem] flex-1">
        <textarea
          id={id}
          rows={2}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              if (canSubmit) onSubmit();
            }
          }}
          placeholder={showTyping ? undefined : placeholder}
          className="h-full min-h-[3.5rem] w-full resize-none bg-transparent px-2 py-1.5 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground"
        />
        {showTyping && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-2 top-1.5 overflow-hidden text-base leading-6 whitespace-pre text-muted-foreground"
          >
            {typed}
            <span className="search-typing-caret" />
          </span>
        )}
      </div>
      <button
        type="submit"
        disabled={!canSubmit}
        aria-label={submitLabel}
        title={submitLabel}
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? <LoaderIcon className="h-5 w-5" /> : <ArrowUpIcon className="h-5 w-5" />}
      </button>
    </form>
  );
}

export default SearchBar;
