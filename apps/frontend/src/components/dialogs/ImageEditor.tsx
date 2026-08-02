import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type ImageAnalysis } from '../../api/client';

/**
 * Image editor (v2 Part 36) — the prep step in front of digitizing.
 *
 * Every slider maps to one server-side operation, and the preview is produced
 * by the SAME code path the digitizer will consume, so what you see is what
 * gets stitched. "Analyze" measures the image and says what to fix, quoting
 * the number behind each suggestion rather than offering an opinion.
 */

export interface ImageEditorProps {
  file: File;
  onCancel: () => void;
  /** Receives the edited image, ready to hand to the digitizer. */
  onApply: (edited: File) => void;
}

const DEFAULTS = {
  rotate_deg: 0,
  scale: 1,
  brightness: 0,
  contrast: 0,
  gamma: 1,
  saturation: 0,
  hue_shift: 0,
  sharpen: 0,
  denoise: 0,
  posterize: 0,
  auto_levels: false,
  flip_h: false,
  flip_v: false,
  remove_background: false,
  threshold_bw: false,
};

type Params = typeof DEFAULTS;

export function ImageEditor({ file, onCancel, onApply }: ImageEditorProps) {
  const [params, setParams] = useState<Params>(DEFAULTS);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ImageAnalysis | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const urlRef = useRef<string | null>(null);

  const set = <K extends keyof Params>(k: K, v: Params[K]) => setParams((p) => ({ ...p, [k]: v }));

  const render = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const blob = await api.editImage(file, params as unknown as Record<string, string | number | boolean>);
      blobRef.current = blob;
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = URL.createObjectURL(blob);
      setPreview(urlRef.current);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [file, params]);

  // Debounced: sliders fire continuously, and each render is a server round
  // trip on a full-size image.
  useEffect(() => {
    const t = setTimeout(render, 320);
    return () => clearTimeout(t);
  }, [render]);

  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  const analyze = async () => {
    setErr(null);
    try {
      const a = await api.analyzeImage(file);
      setAnalysis(a);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const applySuggestions = () => {
    if (!analysis) return;
    setParams((p) => ({
      ...p,
      auto_levels: analysis.suggested.autoLevels,
      sharpen: analysis.suggested.sharpen,
      denoise: analysis.suggested.denoise,
      posterize: analysis.suggested.posterize,
    }));
  };

  const apply = () => {
    if (!blobRef.current) return;
    const name = file.name.replace(/\.[^.]+$/, '') + '-edited.png';
    onApply(new File([blobRef.current], name, { type: 'image/png' }));
  };

  const slider = (
    label: string,
    key: keyof Params,
    min: number,
    max: number,
    step: number,
    fmt: (v: number) => string = (v) => String(v),
  ) => (
    <label className="ie-slider" key={key as string}>
      <span>
        {label} <em>{fmt(params[key] as number)}</em>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={params[key] as number}
        onChange={(e) => set(key, Number(e.target.value) as Params[typeof key])}
      />
    </label>
  );

  const toggle = (label: string, key: keyof Params) => (
    <label className="ie-toggle" key={key as string}>
      <input
        type="checkbox"
        checked={params[key] as boolean}
        onChange={(e) => set(key, e.target.checked as Params[typeof key])}
      />
      {label}
    </label>
  );

  return (
    <div className="dialog-overlay" role="dialog" aria-label="Prepare image">
      <div className="dialog ie-dialog">
        <h2 className="panel-title">Prepare “{file.name}” before digitizing</h2>
        <div className="ie-body">
          <div className="ie-preview">
            {preview ? <img src={preview} alt="Edited preview" /> : <div className="ie-loading">Rendering…</div>}
            {busy ? <div className="ie-busy">working…</div> : null}
          </div>
          <div className="ie-controls">
            <div className="ie-group">
              <h3>Geometry</h3>
              {slider('Rotate', 'rotate_deg', -180, 180, 1, (v) => `${v}°`)}
              {slider('Scale', 'scale', 0.25, 2, 0.05, (v) => `${v.toFixed(2)}×`)}
              <div className="ie-row">
                {toggle('Flip H', 'flip_h')}
                {toggle('Flip V', 'flip_v')}
              </div>
            </div>
            <div className="ie-group">
              <h3>Tone</h3>
              {slider('Brightness', 'brightness', -1, 1, 0.02)}
              {slider('Contrast', 'contrast', -0.9, 1, 0.02)}
              {slider('Gamma', 'gamma', 0.3, 2.5, 0.05)}
              {toggle('Auto levels', 'auto_levels')}
            </div>
            <div className="ie-group">
              <h3>Colour</h3>
              {slider('Saturation', 'saturation', -1, 2, 0.05)}
              {slider('Hue shift', 'hue_shift', 0, 350, 10, (v) => `${v}°`)}
              {slider('Posterize', 'posterize', 0, 16, 1, (v) => (v < 2 ? 'off' : `${v} levels`))}
            </div>
            <div className="ie-group">
              <h3>Structure</h3>
              {slider('Sharpen', 'sharpen', 0, 1, 0.05)}
              {slider('Denoise', 'denoise', 0, 1, 0.05)}
              {toggle('Remove background', 'remove_background')}
              {toggle('Black & white', 'threshold_bw')}
            </div>
            <div className="ie-group">
              <h3>Auto prep</h3>
              <button type="button" onClick={analyze}>
                Analyze this image
              </button>
              {analysis ? (
                <div className="ie-analysis">
                  <ul>
                    {analysis.tips.length ? (
                      analysis.tips.map((t) => <li key={t}>{t}</li>)
                    ) : (
                      <li>Nothing to fix — this image is already well-suited to digitizing.</li>
                    )}
                  </ul>
                  {analysis.tips.length ? (
                    <button type="button" className="primary" onClick={applySuggestions}>
                      Apply suggestions
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
        {err ? <p className="ie-err" role="alert">{err}</p> : null}
        <div className="dialog-actions">
          <button type="button" onClick={() => setParams(DEFAULTS)}>
            Reset
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="primary" onClick={apply} disabled={!blobRef.current || busy}>
            Use this image
          </button>
        </div>
      </div>
    </div>
  );
}
