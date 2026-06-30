const TOOLS = ['Select', 'Run', 'Satin', 'Fill', 'Lettering', 'Appliqué', 'Manual', 'Shape'];

/** Top toolbar — Wilcom-equivalent digitizing tools (spec §3). Buttons are stubs. */
export function Toolbar() {
  return (
    <header className="toolbar">
      <span className="brand">🧵 STITCHIQ</span>
      <nav className="tools">
        {TOOLS.map((tool) => (
          <button key={tool} type="button" className="tool-btn" disabled title="Stub">
            {tool}
          </button>
        ))}
      </nav>
      <div className="toolbar-actions">
        <button type="button" disabled title="Stub">
          Open
        </button>
        <button type="button" disabled title="Stub">
          Export
        </button>
      </div>
    </header>
  );
}
