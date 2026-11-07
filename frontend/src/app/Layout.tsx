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
      <header
        data-print-hide="true"
        className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-xs"
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-6">
            <NavLink
              to="/"
              className="flex items-center gap-2 text-base font-bold tracking-tight text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-none rounded"
            >
              <span className="inline-flex h-6 w-6 items-center justify-center rounded bg-slate-900 text-xs font-bold text-white">
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
                      'rounded-md px-3 py-1.5 text-xs font-semibold transition-colors focus:ring-2 focus:ring-blue-500 focus:outline-none',
                      isActive
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
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

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 pt-6 pb-16 sm:px-6 lg:px-8">
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
