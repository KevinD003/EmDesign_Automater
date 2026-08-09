/**
 * Command palette (⌘K / Ctrl-K).
 *
 * Mount once, next to <Toasts /> in App.tsx:
 *
 *     import { CommandPalette } from './components/command/CommandPalette';
 *     …
 *     <Toasts />
 *     <CommandPalette />
 *
 * Commands are assembled from the live design store, so the entries reflect
 * what is actually loaded (no design → the design-scoped rows disappear rather
 * than failing when chosen). Navigation goes through lib/routes' `navigate`,
 * which keeps every jump in the hash and therefore refresh-survivable.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { navigate } from '../../lib/routes';
import { useDesignStore } from '../../store/designStore';
import { useTheme } from '../../lib/useTheme';

export interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  run: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const design = useDesignStore((s) => s.design);
  const setTool = useDesignStore((s) => s.setTool);
  const { theme, toggle } = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
        setQuery('');
        setActive(0);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [
      { id: 'go-studio', group: 'GO', label: 'Studio', run: () => navigate('studio') },
      { id: 'go-overview', group: 'GO', label: 'Dashboard overview', run: () => navigate('dashboard') },
      { id: 'go-analytics', group: 'GO', label: 'Design analytics', run: () => navigate('dashboard/analytics') },
      { id: 'go-account', group: 'GO', label: 'Account & plan', run: () => navigate('dashboard/account') },
      {
        id: 'theme',
        group: 'VIEW',
        label: `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`,
        run: toggle,
      },
    ];

    // Design-scoped commands only exist when something is loaded — offering
    // "Optimize path" with no design was how the old toolbar produced a 400.
    if (design) {
      list.unshift(
        { id: 'tool-select', group: 'TOOL', label: 'Select tool', hint: 'Esc', run: () => setTool('select') },
        { id: 'tool-run', group: 'TOOL', label: 'Run tool', run: () => setTool('run') },
        { id: 'tool-satin', group: 'TOOL', label: 'Satin tool', run: () => setTool('satin') },
        { id: 'tool-fill', group: 'TOOL', label: 'Fill tool', run: () => setTool('fill') },
      );
    }
    return list;
  }, [design, setTool, theme, toggle]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => `${c.group} ${c.label}`.toLowerCase().includes(q));
  }, [commands, query]);

  if (!open) return null;

  const choose = (c: Command) => {
    c.run();
    setOpen(false);
  };

  return (
    <div
      className="sq-cmd-scrim"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={() => setOpen(false)}
    >
      <div className="sq-cmd sq-card" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="sq-cmd-input"
          value={query}
          placeholder="Search commands…"
          aria-label="Search commands"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setOpen(false);
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActive((i) => Math.min(results.length - 1, i + 1));
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((i) => Math.max(0, i - 1));
            }
            if (e.key === 'Enter' && results[active]) choose(results[active]);
          }}
        />
        <ul className="sq-cmd-list">
          {results.map((c, i) => (
            <li key={c.id}>
              <button
                type="button"
                className="sq-cmd-item"
                aria-selected={i === active}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(c)}
              >
                <span className="sq-cmd-group">{c.group}</span>
                <span style={{ flex: 1 }}>{c.label}</span>
                {c.hint ? <span className="sq-cmd-hint">{c.hint}</span> : null}
              </button>
            </li>
          ))}
          {results.length === 0 ? (
            <li style={{ padding: '0.9rem 0.75rem', color: 'var(--sq-muted)' }}>No matching command.</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}
