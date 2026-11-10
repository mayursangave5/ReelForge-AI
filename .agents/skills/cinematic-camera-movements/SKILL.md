---
name: cinematic-camera-movements
description: Cinematic camera directing in Remotion and SVG. Covers camera push-ins, tracking zooms, Dutch angles, pans, impact shakes with exponential decay, and depth-of-field focus simulation.
---

# Cinematic Camera Movements Skill

## Directing Grammar
- **Push-in**: `scale(1 + 0.12 * t / totalFrames)` into the subject's face for psychological tension.
- **Tracking Pan**: Translate the world coordinate space smoothly as the hero or projectile moves.
- **Decaying Shake**: For impacts, detonations, or heavy footsteps:
  `x = sin(t * 2.9) * amp * (1 - progress); y = cos(t * 3.7) * amp * 0.7 * (1 - progress)`.
- **Dutch Angle**: 4-8 degree slight rotate to signal danger or disorientation.
- **Depth Layers**: Blurred dark foreground (0.35 opacity, 12px blur), sharp mid-ground subject, soft distant background (4px blur).
