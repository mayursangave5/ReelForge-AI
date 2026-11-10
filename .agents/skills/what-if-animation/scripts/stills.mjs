// Step 4: the storyboard stills. Renders one still per shot at its key frame from the <Id>Board composition,
// bundling once. Run from the studio folder:
//   node <skill>/scripts/stills.mjs <slug> [S1 S4 ...] [--scale 0.5]
// Writes out/<slug>/board/<shot>.png. With shot ids, renders only those (after a fix).
// Also: node <skill>/scripts/stills.mjs <slug> --frames 120 300   renders frames of the main composition
// (out/<slug>/frames/f0120.png), for checking a moment inside a shot.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

// Remotion is installed in the studio, not next to this script: resolve it from the folder we run in.
const require = createRequire(path.resolve('package.json'));
const { bundle } = require('@remotion/bundler');
const { renderStill, selectComposition } = require('@remotion/renderer');

const args = process.argv.slice(2);
const slug = args[0];
const scaleAt = args.indexOf('--scale');
const scale = scaleAt >= 0 ? Number(args[scaleAt + 1]) : 0.5;
const framesAt = args.indexOf('--frames');
const rest = args.slice(1).filter((a, i, all) => !a.startsWith('--') && all[i - 1] !== '--scale');
const ep = JSON.parse(fs.readFileSync(path.resolve('src/episodes', slug, 'episode.json'), 'utf8'));
const tl = JSON.parse(fs.readFileSync(path.resolve('src/episodes', slug, 'timeline.json'), 'utf8'));

const serveUrl = await bundle({ entryPoint: path.resolve('src/index.ts'), publicDir: path.resolve('public') });
if (framesAt >= 0) {
  const outDir = path.resolve('out', slug, 'frames');
  fs.mkdirSync(outDir, { recursive: true });
  const composition = await selectComposition({ serveUrl, id: ep.id });
  for (const fr of rest.map(Number)) {
    const output = path.join(outDir, `f${String(fr).padStart(4, '0')}.png`);
    await renderStill({ serveUrl, composition, frame: fr, output, overwrite: true, scale });
    process.stdout.write(`${fr} `);
  }
} else {
  const outDir = path.resolve('out', slug, 'board');
  fs.mkdirSync(outDir, { recursive: true });
  const composition = await selectComposition({ serveUrl, id: `${ep.id}Board` });
  const want = rest.length ? rest : tl.shots.map((s) => s.id);
  for (const id of want) {
    const i = tl.shots.findIndex((s) => s.id === id);
    if (i < 0) throw new Error(`No shot ${id} in the timeline`);
    await renderStill({ serveUrl, composition, frame: i, output: path.join(outDir, `${id}.png`), overwrite: true, scale });
    process.stdout.write(`${id} `);
  }
}
console.log('\ndone');
