import { useState } from 'react';

export interface DigitizeParams {
  fabricType: string;
  hoopSize: string;
  maxColors: number;
}

interface DigitizeDialogProps {
  filename: string;
  onCancel: () => void;
  onConfirm: (params: DigitizeParams) => void;
  /** Opens the image editor first (v2 Part 36) — prep is optional. */
  onPrepare?: () => void;
}

const FABRICS = ['cotton', 'polo/knit', 'denim', 'fleece', 'cap', 'towel'];
const HOOPS = ['100x100', '130x180', '200x200', '260x160'];

/** Pre-digitize parameters (spec §4.2: fabric + hoop are digitizing inputs). */
export function DigitizeDialog({ filename, onCancel, onConfirm, onPrepare }: DigitizeDialogProps) {
  const [fabricType, setFabricType] = useState('cotton');
  const [hoopSize, setHoopSize] = useState('100x100');
  const [maxColors, setMaxColors] = useState(6);

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true">
      <div className="dialog">
        <h2 className="panel-title">Digitize “{filename}”</h2>
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
        <label className="prop-row">
          <span>Hoop (mm)</span>
          <select value={hoopSize} onChange={(e) => setHoopSize(e.target.value)}>
            {HOOPS.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </label>
        <label className="prop-row">
          <span>Max colors</span>
          <input
            type="number"
            min={2}
            max={8}
            value={maxColors}
            onChange={(e) => setMaxColors(Math.max(2, Math.min(8, Number(e.target.value) || 6)))}
          />
        </label>
        <div className="dialog-actions">
          {onPrepare ? (
            <button type="button" onClick={onPrepare} title="Crop, straighten, levels, posterize before digitizing">
              Prepare image…
            </button>
          ) : null}
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="primary" onClick={() => onConfirm({ fabricType, hoopSize, maxColors })}>
            Digitize
          </button>
        </div>
      </div>
    </div>
  );
}
