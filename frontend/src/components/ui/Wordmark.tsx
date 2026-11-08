import clsx from 'clsx';

/** "Jane Avenue." wordmark: display type with the primary-coloured full stop. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={clsx('font-display font-semibold tracking-tight', className)}>
      <span>Jane Avenue</span>
      <span aria-hidden="true" className="text-primary">
        .
      </span>
    </span>
  );
}

export default Wordmark;
