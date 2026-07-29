import { useState } from 'react';

export interface LetteringParams {
  text: string;
  heightMm: number;
  fabricType: string;
  letterSpacingMm: number;
}

interface LetteringDialogProps {
  onCancel: () => void;
  onConfirm: (params: LetteringParams) => void;
}

const FABRICS = ['cotton', 'polo/knit', 'denim', 'fleece', 'cap', 'towel'];

/** Text-to-embroidery parameters (spec §4.10). v1 renders TATAMI-filled letters. */
export function LetteringDialog({ onCancel, onConfirm }: LetteringDialogProps) {
  const [text, setText] = useState('');
  const [heightMm, setHeightMm] = useState(20);
  const [fabricType, setFabricType] = useState('cotton');
  const [letterSpacingMm, setLetterSpacingMm] = useState(0);
  const valid =
    text.trim().length > 0 && heightMm >= 5 && heightMm <= 100 && letterSpacingMm >= -2 && letterSpacingMm <= 10;

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true">
      <div className="dialog">
        <h2 className="panel-title">Lettering</h2>
        <label className="prop-row">
          <span>Text</span>
          <input
            type="text"
            value={text}
            maxLength={64}
            autoFocus
            placeholder="e.g. STITCHIQ"
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        <label className="prop-row">
          <span>Height (mm)</span>
          <input
            type="number"
            min={5}
            max={100}
            value={heightMm}
            onChange={(e) => setHeightMm(Number(e.target.value) || 20)}
          />
        </label>
        <label className="prop-row">
          <span>Letter spacing (mm)</span>
          <input
            type="number"
            min={-2}
            max={10}
            step={0.1}
            value={letterSpacingMm}
            onChange={(e) => setLetterSpacingMm(Number(e.target.value) || 0)}
          />
        </label>
        <label className="prop-row">
          <span>Fabric</span>
          <select value={fabricType} onChange={(e) => setFabricType(e.target.value)}>
            {FABRICS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        <p className="muted small">v1 fills letters with tatami + edge-walk underlay; satin strokes come later.</p>
        <div className="dialog-actions">
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            disabled={!valid}
            onClick={() => onConfirm({ text: text.trim(), heightMm, fabricType, letterSpacingMm })}
          >
            Generate
          </button>
        </div>
      </div>
    </div>
  );
}
