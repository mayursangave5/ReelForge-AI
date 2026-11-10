---
name: character-rigging-animation
description: SVG character rigging and skeletal hierarchy. Covers joints, limb angles, yaw rotation, mitten hands, facial expression swapping via blinks, and procedural walk/run/jump cycles in code.
---

# Character Rigging & Animation Skill

## Skeletal Structure
- **Root**: Hip center (x, y), with torso tilt and full-body tumble spin.
- **Limbs**: Segmented upper and lower segments (thigh + shin, upper arm + forearm). Angles `a` and `b` in degrees.
- **Head & Yaw**: Yaw turns the head and torso between full-face (0) and profile (-1 or +1), shrinking limb spread and shifting eye offsets.
- **Faces**: Expressions swap through 2-frame blink transitions (`faceAt`). Hand kinds: `open`, `point`, `fist`.
- **Walk/Run Cycles**: Sine-wave phase offsets between left and right limbs with hip vertical bobbing (`settle`, `kf`).
