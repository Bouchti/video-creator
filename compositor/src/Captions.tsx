import {createTikTokStyleCaptions} from '@remotion/captions';
import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily, outline} from './font';
import {ZONES} from './safe';
import {Style, Word} from './types';

// 2-4 word pages, the spoken word lit in the accent colour with a small pop. Uppercase, heavy, outlined.
export const Captions: React.FC<{words: Word[]; style: Style}> = ({words, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const ms = (frame / fps) * 1000;

  const pages = useMemo(() => {
    const {pages} = createTikTokStyleCaptions({
      captions: words.map((w) => ({
        text: ` ${w.text}`,
        startMs: w.startMs,
        endMs: w.endMs,
        timestampMs: w.startMs,
        confidence: 1,
      })),
      combineTokensWithinMilliseconds: 900,
    });
    // a page never holds more than 4 words, so a line never wraps into the subject
    return pages.flatMap((p) => {
      const out = [];
      for (let i = 0; i < p.tokens.length; i += 4) {
        const tokens = p.tokens.slice(i, i + 4);
        out.push({startMs: tokens[0].fromMs, endMs: tokens[tokens.length - 1].toMs, tokens});
      }
      return out;
    });
  }, [words]);

  const emphasis = useMemo(() => new Set(words.filter((w) => w.emphasis).map((w) => w.startMs)), [words]);
  const page = pages.find((p, i) => ms >= p.startMs && ms < (pages[i + 1]?.startMs ?? p.endMs + 400));
  if (!page) return null;

  const enter = spring({frame: frame - Math.round((page.startMs / 1000) * fps), fps, config: {damping: 14, mass: 0.5}});
  const size = Math.round(height * 0.042);

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: height * ZONES.captionY,
          left: width * 0.06,
          width: width * 0.8,
          transform: `translateY(-50%) scale(${interpolate(enter, [0, 1], [0.85, 1])})`,
          opacity: enter,
          textAlign: 'center',
          fontFamily,
          fontWeight: 900,
          fontSize: size,
          lineHeight: 1.12,
          letterSpacing: 0.5,
          textTransform: 'uppercase',
          color: 'white',
          textShadow: outline(size * 0.07),
        }}
      >
        {page.tokens.map((t) => {
          const active = ms >= t.fromMs && ms < t.toMs;
          const key = emphasis.has(t.fromMs);
          return (
            <span
              key={t.fromMs}
              style={{
                display: 'inline-block',
                margin: '0 0.22em',
                color: active || key ? style.accent : 'white',
                transform: `scale(${active ? 1.04 : 1})`,
              }}
            >
              {t.text.trim()}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
