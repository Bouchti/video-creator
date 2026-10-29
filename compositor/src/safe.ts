// Platform safe zones for a 1080x1920 short (TikTok / YouTube Shorts / Reels), as shares of the frame.
// Bottom: caption + description + music bar. Right: like/comment/share rail. Top: tabs / search.
export const SAFE = {top: 0.09, bottom: 0.2, left: 0.05, right: 0.15};

// Where each kind of text lives, so nothing ever collides:
//   hook + chapter titles  top band
//   pinned labels          upper two thirds (clamped)
//   captions               ~62% down: above the bottom UI, below the subject's centre
export const ZONES = {
  titleY: 0.15,
  captionY: 0.66,
  labelMinY: SAFE.top + 0.02,
  labelMaxY: 0.56,
  calloutY: 0.32,
};

export const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
