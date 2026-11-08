import { setThemeMode, useThemeMode } from '../../lib/themeMode';
import { MoonIcon, SunIcon } from './icons';

/** Switches the whole site between dark and light appearance. */
export function ThemeToggle() {
  const mode = useThemeMode();
  const next = mode === 'dark' ? 'light' : 'dark';
  const Icon = mode === 'dark' ? SunIcon : MoonIcon;
  return (
    <button
      type="button"
      onClick={() => setThemeMode(next)}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
