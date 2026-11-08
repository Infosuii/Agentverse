import clsx from 'clsx';

export interface ExamplePrompt {
  label: string;
  query: string;
}

export interface ExamplePromptsProps {
  examples: readonly ExamplePrompt[];
  /** Called with the full prompt text when an example is clicked. */
  onPick: (query: string) => void;
  /** The query currently in the search bar, used to mark the matching example. */
  selectedQuery?: string;
  className?: string;
}

/** Studio-style example prompts: ruled rows with a mono label above the full prompt. */
export function ExamplePrompts({
  examples,
  onPick,
  selectedQuery,
  className,
}: ExamplePromptsProps) {
  return (
    <div
      role="group"
      aria-label="Example policy queries"
      className={clsx('grid gap-x-5 sm:grid-cols-3', className)}
    >
      {examples.map((ex) => {
        const isSelected = selectedQuery?.trim() === ex.query;
        return (
          <button
            key={ex.query}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onPick(ex.query)}
            className={clsx(
              'group block border-t py-3 text-left transition-colors focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none',
              isSelected ? 'border-primary' : 'border-border hover:border-muted-foreground/60',
            )}
          >
            <span
              className={clsx(
                'block font-mono text-[11px] tracking-wide uppercase',
                isSelected ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground',
              )}
            >
              {ex.label}
            </span>
            <span className="mt-1 block text-sm leading-snug text-muted-foreground group-hover:text-foreground">
              {ex.query}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default ExamplePrompts;
