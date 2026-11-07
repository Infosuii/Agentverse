import { NavLink, Outlet } from 'react-router';
import clsx from 'clsx';
import { ErrorBoundary, ModeBadge } from '../components/ui';

const NAV_LINKS = [
  { to: '/', label: 'New analysis', end: true },
  { to: '/history', label: 'History', end: false },
  { to: '/evaluation', label: 'Evaluation', end: false },
];

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-blue-700 focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>

      <header
        data-print-hide="true"
        className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-xs"
      >
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center gap-4 sm:gap-6">
            <NavLink
              to="/"
              className="flex items-center gap-2 rounded text-base font-bold tracking-tight text-slate-900 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
            >
              <span
                aria-hidden="true"
                className="inline-flex h-6 w-6 items-center justify-center rounded bg-slate-900 text-xs font-bold text-white"
              >
                JA
              </span>
              <span>Jane Avenue</span>
            </NavLink>

            <nav aria-label="Main navigation" className="flex items-center gap-1">
              {NAV_LINKS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    clsx(
                      'rounded-md px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none',
                      isActive
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <ModeBadge />
          </div>
        </div>
      </header>

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-7xl flex-1 px-4 pt-6 pb-16 focus:outline-none sm:px-6 lg:px-8"
      >
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      <footer
        data-print-hide="true"
        className="fixed right-0 bottom-0 left-0 z-30 border-t border-slate-200 bg-white/95 px-4 py-2 text-center text-xs font-medium text-slate-600 backdrop-blur-xs"
      >
        Prototype. Not official government analysis.
      </footer>
    </div>
  );
}

export default Layout;
