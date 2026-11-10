---
name: react-typescript-animation
description: High-performance React and TypeScript animation patterns for Remotion. Covers deterministic time functions, interpolation, springs, pure SVG components, and type-safe composition props.
---

# React & TypeScript Animation Skill

## Best Practices
- **Pure Functions of Time**: Never use `useState` or `useEffect` for animation frames. Use `useCurrentFrame()` and compute properties deterministically from clock `t`.
- **Interpolation**: Use Remotion's `interpolate(frame, [inStart, inEnd], [outStart, outEnd], { extrapolateRight: 'clamp' })` or mathematical ease functions (`easeInOut`, `kf`).
- **Compositions**: Structure scenes into modular shot components (`Shot1`, `Shot2`, ...) wrapped in `<Sequence>` or driven by a timeline array.
- **Type Safety**: Strictly type shot durations, audio stems, and subtitle cue arrays.
