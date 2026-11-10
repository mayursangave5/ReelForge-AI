---
name: 3d-cartoon-animation
description: Create cinematic 3D cartoon animations and visual storytelling inspired by Zack D. Films and Kurzgesagt 3D. Covers perspective camera fly-throughs, 3D celestial bodies (planets, asteroids), depth shading, atmospheric lighting, volumetric shockwaves, and physics-driven particle explosions in Remotion.
---

# 3D Cartoon Animation Skill

## Aesthetic Principles
- **Perspective & Depth**: Use multi-layer parallax, SVG matrix transforms, 3D perspective scales, and atmospheric haze.
- **Lighting**: Visible light sources, dynamic rims (`feDropShadow`, SVG radial gradients, screen blend modes), deep shadows, and lens reflections.
- **Scale Contrast**: Juxtapose massive celestial objects (e.g., a 10 km asteroid, Earth's planetary horizon) with grounded human/city scales.

## Core Techniques
1. **Planetary Spheres**: Layered concentric circles with radial shading, rotating continent SVG patterns, and an outer atmospheric glow ring.
2. **Asteroid Shading**: Irregular polygonal faceted path with crater textures, incandescent flame/plasma boundary layer, and particle exhaust trail.
3. **Volumetric Shockwaves**: Rapidly expanding ring with cubic ease-out, edge refraction, screen flash, and high-frequency camera shake.
4. **Cinematic Cameras**: Push-in zooms (`scale(1 + 0.15 * t)`), orbital pan, and directional tracking.
