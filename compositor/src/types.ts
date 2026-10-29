// The overlay timeline the Python side writes (engine/compose.py). Frames are video frames at `fps`;
// screen positions are 0..1 of the frame (x across, y DOWN), as projected by Blender per frame.

export type Word = {text: string; startMs: number; endMs: number; emphasis?: boolean};

export type Track = {start: number; xy: [number, number][]}; // xy[i] is the position at frame start + i

export type Label = {text: string; from: number; to: number; anchor?: string; at?: [number, number]};

export type Title = {text: string; from: number; to: number; sub?: string};

export type Callout = {kind: 'counter' | 'stamp'; text: string; from: number; to: number; tone?: 'good' | 'bad'};

export type PunchIn = {from: number; to: number; scale?: number; focus?: [number, number]};

export type Checklist = {title?: string; from: number; to: number; items: {text: string; from: number}[]};

// VHS rewind: frames [from, to] show the source frames sourceFrom -> sourceTo (played backwards when
// sourceTo < sourceFrom), with scanlines and a REWIND badge.
export type Rewind = {from: number; to: number; sourceFrom: number; sourceTo: number};

export type Grade = {saturate?: number; contrast?: number; brightness?: number};

export type Style = {accent: string; good: string; bad: string; font: string};

export type ShortProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  video?: string; // file in the public dir (the beauty pass)
  audio?: string; // final mix in the public dir
  style?: Partial<Style>;
  hook?: Title; // big question over the first seconds
  chapters?: Title[];
  words?: Word[];
  labels?: Label[];
  anchors?: Record<string, Track>;
  callouts?: Callout[];
  punchIns?: PunchIn[];
  checklist?: Checklist;
  endCard?: Title; // closing card (next episode tease)
  grain?: number; // 0..1 film grain strength
  rewind?: Rewind;
  grade?: Grade;
};

export const DEFAULT_STYLE: Style = {accent: '#FFD23F', good: '#3DDC84', bad: '#FF4D4D', font: 'Montserrat'};
