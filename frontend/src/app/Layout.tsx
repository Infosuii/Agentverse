import { Link, NavLink, Outlet, useLocation } from 'react-router';
import clsx from 'clsx';
import { ErrorBoundary, ModeBadge, SearchIcon, Wordmark, buttonClasses } from '../components/ui';

const NAV_LINKS = [
  { to: '/history', label: 'History' },
  { to: '/evaluation', label: 'Evaluation' },
];

export function Layout() {
  const location = useLocation();
  const isLanding = location.pathname === '/';
  // Reset the error boundary when the user moves to another view, but keep one analysis
  // mounted while switching its tabs (the shell owns the live event stream).
  const segments = location.pathname.split('/').filter(Boolean);
  const boundaryKey =
    segments[0] === 'analyses' ? `analyses/${segments[1] ?? ''}` : location.pathname;

  return (
    <div className="flex min-h-screen flex-col text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      <header
        data-print-hide="true"
        className={clsx(
          'z-40',
          // The landing page wordmark is the hero, so its bar is a quiet, non-sticky strip.
          isLanding
            ? 'relative bg-transparent'
            : 'sticky top-0 border-b border-border bg-background/95 backdrop-blur-sm',
        )}
      >
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3 sm:gap-5">
            {!isLanding && (
              <Link
                to="/"
                className="shrink-0 rounded-sm text-base whitespace-nowrap focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
              >
                <Wordmark />
              </Link>
            )}

            <nav aria-label="Main navigation" className="flex items-center gap-1">
              {NAV_LINKS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    clsx(
                      'rounded-md px-2 py-1.5 text-sm transition-colors focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none sm:px-2.5',
                      isActive
                        ? 'bg-secondary text-foreground'
                        : 'text-muted-foreground hover:text-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-flex">
              <ModeBadge />
            </span>
            {!isLanding && (
              <Link
                to="/"
                aria-label="New Policy Analysis"
                className={buttonClasses('primary', 'sm')}
              >
                <SearchIcon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">New Policy Analysis</span>
              </Link>
            )}
          </div>
        </div>
      </header>

      <main
        id="main-content"
        tabIndex={-1}
        className={clsx(
          'mx-auto w-full flex-1 focus:outline-none',
          isLanding ? 'max-w-none' : 'max-w-7xl px-4 pt-6 pb-20 sm:px-6',
        )}
      >
        {/* Keyed by view so an error in one view never sticks after navigating away. */}
        <ErrorBoundary key={boundaryKey}>
          <Outlet />
        </ErrorBoundary>
      </main>

      <footer
        data-print-hide="true"
        className="fixed right-0 bottom-0 left-0 z-30 border-t border-border bg-background/95 px-4 py-2 text-center font-mono text-[11px] text-muted-foreground backdrop-blur-sm"
      >
        Prototype. Not official government analysis.
      </footer>
    </div>
  );
}

export default Layout;
