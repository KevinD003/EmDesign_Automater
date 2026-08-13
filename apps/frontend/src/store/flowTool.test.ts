/**
 * Stitch Flow editing contract in the store (v2 Part 62).
 *
 * The canvas commits a drawn line via `updateObject(seq, { flowLine })` and the
 * panel removes it with `{ flowLine: null }`. These tests pin what the feature
 * relies on: the line lands on the right object only, every edit is undoable,
 * 'flow' is a capture mode (not a draw tool), and a stale flow mode can never
 * leak onto a freshly loaded design.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useDesignStore, MANUAL_TOOLS } from './designStore';
import type { Design, DesignObject } from '../types/design';
import { StitchType, UnderlayType, ConnectMethod } from '../types/design';

const makeObject = (seq: number): DesignObject => ({
  sequenceOrder: seq,
  name: `Fill ${seq}`,
  stitchType: StitchType.Tatami,
  colorStop: 1,
  density: 4,
  stitchAngle: 37,
  underlayType: UnderlayType.None,
  pullCompensation: 0.2,
  connectMethod: ConnectMethod.Trim,
  penetrationCount: 100,
  contour: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }],
});

const makeDesign = (): Design => ({
  name: 't',
  widthMm: 10,
  heightMm: 10,
  stitchCount: 200,
  version: 1,
  status: 'digitized',
  colorStops: [{ stopNumber: 1, threadBrand: 'M', catalogNumber: '1', threadName: 'Red', hex: '#ff0000', penetrationCount: 200 }],
  objects: [makeObject(0), makeObject(1)],
  stitches: [],
});

beforeEach(() => {
  useDesignStore.setState({
    design: null,
    selectedStop: null,
    selectedObject: null,
    activeTool: 'select',
    draft: [],
    past: [],
    future: [],
  });
});

const LINE = [{ x: 1, y: 2 }, { x: 8, y: 6 }];

describe('stitch flow line edits', () => {
  it('setting a line touches only the target object and records history', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowLine: LINE });
    const s = useDesignStore.getState();
    expect(s.design?.objects[0].flowLine).toEqual(LINE);
    expect(s.design?.objects[1].flowLine).toBeUndefined();
    expect(s.past).toHaveLength(1);
    expect(s.future).toEqual([]);
  });

  it('undo removes the line; redo restores it', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowLine: LINE });
    useDesignStore.getState().undo();
    expect(useDesignStore.getState().design?.objects[0].flowLine).toBeUndefined();
    useDesignStore.getState().redo();
    expect(useDesignStore.getState().design?.objects[0].flowLine).toEqual(LINE);
  });

  it('removing the line (flowLine: null) is itself an undoable edit', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowLine: LINE });
    useDesignStore.getState().updateObject(0, { flowLine: null });
    expect(useDesignStore.getState().design?.objects[0].flowLine).toBeNull();
    useDesignStore.getState().undo();
    expect(useDesignStore.getState().design?.objects[0].flowLine).toEqual(LINE);
  });

  it('moving an endpoint replaces the whole line in one history step', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowLine: LINE });
    const moved = [LINE[0], { x: 9, y: 9 }];
    useDesignStore.getState().updateObject(0, { flowLine: moved });
    expect(useDesignStore.getState().design?.objects[0].flowLine).toEqual(moved);
    expect(useDesignStore.getState().past).toHaveLength(2);
  });
});

describe('divided flow edits (v2 Part 63)', () => {
  const DIVIDE = [{ x: 5, y: -1 }, { x: 5, y: 11 }];

  it('setting a divide is an undoable edit on the target object only', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowDivide: DIVIDE });
    const s = useDesignStore.getState();
    expect(s.design?.objects[0].flowDivide).toEqual(DIVIDE);
    expect(s.design?.objects[1].flowDivide).toBeUndefined();
    expect(s.past).toHaveLength(1);
    useDesignStore.getState().undo();
    expect(useDesignStore.getState().design?.objects[0].flowDivide).toBeUndefined();
  });

  it('removing the divide clears the second line with it in one step', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().updateObject(0, { flowDivide: DIVIDE, flowLine: LINE });
    useDesignStore.getState().updateObject(0, { flowLineB: [{ x: 7, y: 1 }, { x: 9, y: 9 }] });
    // the panel's Remove divide patch: divide and side line go together
    useDesignStore.getState().updateObject(0, { flowDivide: null, flowLineB: null });
    const o = useDesignStore.getState().design?.objects[0];
    expect(o?.flowDivide).toBeNull();
    expect(o?.flowLineB).toBeNull();
    expect(o?.flowLine).toEqual(LINE); // the first line survives
    useDesignStore.getState().undo();
    expect(useDesignStore.getState().design?.objects[0].flowDivide).toEqual(DIVIDE);
  });
});

describe('the flow tool mode', () => {
  it("'flow' is not a manual draw tool — it never creates an object", () => {
    expect(MANUAL_TOOLS).not.toContain('flow');
    expect(MANUAL_TOOLS).not.toContain('divide');
  });

  it('entering flow mode clears any draft; leaving it clears the capture click', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().addDraftPoint({ x: 1, y: 1 });
    useDesignStore.getState().setTool('flow');
    expect(useDesignStore.getState().draft).toEqual([]);
    useDesignStore.getState().addDraftPoint({ x: 2, y: 2 }); // first capture click
    useDesignStore.getState().setTool('select');
    expect(useDesignStore.getState().draft).toEqual([]);
  });

  it('loading a new design drops a stale flow or divide mode', () => {
    useDesignStore.getState().setDesign(makeDesign());
    useDesignStore.getState().setTool('flow');
    useDesignStore.getState().setDesign(makeDesign());
    expect(useDesignStore.getState().activeTool).toBe('select');
    useDesignStore.getState().setTool('divide');
    useDesignStore.getState().setDesign(makeDesign());
    expect(useDesignStore.getState().activeTool).toBe('select');
  });
});
