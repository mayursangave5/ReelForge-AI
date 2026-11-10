# What If animation: a free skill for Claude Code and OpenCode

Type one line, "What if you could rewind 10 seconds?", and get a finished 15-25 second animated episode in the
dusk-lit stick-figure style of the "What If" channels that took off on YouTube in October 2026.

Every frame is drawn in code: the AI writes the scenes as SVG and Remotion renders them. The voice and the sound
effects come from ElevenLabs. No image model, no video model, no drawing. It runs in Claude Code, or for free in
OpenCode with a free model. Made by [FreshStack](https://freshstack.ai).

## What it does

1. **Writes the script** on the seven-beat What If formula (decoded from five scripts across four channels): a cold
   open of quick demos, the premise as a title card, the fun, and a turn built on one real, checked fact.
2. **Voices it** with ElevenLabs, with word timings, and tightens the pauses to the genre's pace.
3. **Lays out a shot list** on the words, at the genre's pace (about 27 cuts a minute in the opening and up).
4. **Renders a storyboard** of one still per shot, before any animation.
5. **Checks its own stills** against an 11-point checklist and fixes what reads wrong.
6. **Animates** an original cast on one rig, in rooms drawn in real perspective, lit by their own lamps and windows.
7. **Generates and syncs the sound:** an effect on every action, lined up by its attack, ambience per place, a
   music bed, levels set against the voice.
8. **Masters** the episode to -14 LUFS and reports what it cost.

Why the character never changes: it isn't generated, it's a rig in code. The same function draws Pip in every
shot, so there is nothing to drift.

## What you need

- [Claude Code](https://claude.com/claude-code), or [OpenCode](https://opencode.ai) with a free model (see
  [Use it in OpenCode](#use-it-in-opencode-with-a-free-model))
- Node 18 or newer, ffmpeg (with ffprobe), Python 3.9+ with `numpy` and `Pillow`
- An [ElevenLabs](https://elevenlabs.io) API key in your environment or a `.env` file as `ELEVENLABS_API_KEY`.
  The copy-paste episode cost 152 credits: 78 for the voice and 74 for 12 new sound effects. It reused 9 clips from
  the starter library that ships in `studio/library/sfx/`, and every clip you generate joins it for the next
  episode. Later runs cost 170 to 242 credits. ElevenLabs' free plan (10,000 credits a month when we checked, in
  October 2026) covers about 40 episodes, but it's for non-commercial use and asks you to credit ElevenLabs, so
  check its terms before you monetise.

## Install in Claude Code

Clone it into your skills folder, then set up the studio once:

```bash
git clone https://github.com/kelano86/what-if-animation ~/.claude/skills/what-if-animation
cp -r ~/.claude/skills/what-if-animation/studio ./what-if-studio
cd what-if-studio && npm install
```

Then, in Claude Code, from that folder:

> Make a What If episode: what if you could pause everyone but you?

Claude follows `SKILL.md`: script, voice, shot list, storyboard (you'll see it before anything is animated), self-
check, animation, sound, master. You get `out/<slug>/<slug>-final.mp4` and `out/<slug>/storyboard.jpg`.

To see the examples first: `npx remotion studio src/index.ts` and open `Rewind` (the proof clip: three demos, each
undone by playing the shot backwards) or `CopyPaste` (the skill's first full run). Both render straight away.

## Use it in OpenCode, with a free model

[OpenCode](https://opencode.ai) is a free, open-source coding agent. In October 2026 it offers GLM-5.3-Flash Free at
no cost, for a limited time, with no account or key. With this skill, that model made a full episode from one line:
28 minutes, one render, nothing typed in between, and $0 for the model (the voice and sound still use your
ElevenLabs credits).

1. Install the tools above, then OpenCode: `npm install -g opencode-ai`
2. Make a folder for your episodes, put the skill in it under `.claude/skills/`, and add the `/what-if` command
   (OpenCode doesn't list skills when you type `/`, so the command loads it for you).

   Windows (PowerShell):

   ```powershell
   mkdir what-if; cd what-if
   git clone https://github.com/kelano86/what-if-animation .claude/skills/what-if-animation
   mkdir .opencode/commands
   copy .claude/skills/what-if-animation/opencode/commands/what-if.md .opencode/commands/
   ```

   Mac or Linux:

   ```bash
   mkdir what-if && cd what-if
   git clone https://github.com/kelano86/what-if-animation .claude/skills/what-if-animation
   mkdir -p .opencode/commands && cp .claude/skills/what-if-animation/opencode/commands/what-if.md .opencode/commands/
   ```

   No git? Download the ZIP from GitHub and unzip it into `.claude/skills/` (the folder's name doesn't matter), then
   copy `opencode/commands/what-if.md` from it into `.opencode/commands/`.
3. Put your key in a file called `.env` in the same folder, one line: `ELEVENLABS_API_KEY=your-key`
4. Start OpenCode **from inside that folder**: `cd` into it (on Windows you can right-click the folder and choose
   Open in Terminal), then type `opencode`. Started anywhere else, it won't find the skill or the command.
5. Type `/models`, choose GLM-5.3-Flash Free, and press Ctrl+T until the reasoning level reads high.
6. Type `/what-if What if you could pause everyone but you?` and leave it running. The first run copies the studio
   into `what-if-studio/` and installs it, which adds a few minutes.

Tips for the free model:

- One session per episode. An episode can fill most of its 200K context; start fresh for the next one.
- Search YouTube for your premise yourself. The free model's search can miss episodes that already exist, and the
  skill wants an original title.
- Open the source of the episode's fact (`science` in its `episode.json`) before you post.

## What's in the folder

| Path | What |
|---|---|
| `SKILL.md` | The pipeline the AI follows |
| `references/` | The formula, the measured look and checklists, the building-block catalogue, sound, traps |
| `studio/` | The Remotion project: the engine (rig, sets, light, UI, the episode engine) and two example episodes |
| `scripts/` | voice, plan, stills, board, sfx, mixcheck, motiongrid, master |
| `opencode/commands/what-if.md` | The `/what-if` command for OpenCode |

## The rules it follows

- Original characters only: never a channel's hero, nothing that resembles a famous cartoon character.
- Original stories: the formula is shared, the episodes aren't anyone's.
- It never claims the viral channels are made with Claude or any other tool; nobody has said how they're made.
- Every fact in a script is worked out and sourced before it's voiced.

## Honest limits

- Walk cycles and acting are simple next to a hand-animated channel; the look carries it.
- Painted, textured styles (the ink-and-paper explainers) aren't realistic in pure code; they need an image model.
- It's not one prompt: the storyboard step is where the episode gets good. Look at it.

## Licences

- Fonts load from Google Fonts at render time (Bricolage Grotesque, Fragment Mono, Kalam: SIL Open Font License).
  To use your own title face, put it in `studio/public/fonts/` and set `titleFont` in `src/studio.config.ts`.
- [Remotion](https://www.remotion.dev/license) is free for individuals and for companies of up to three people;
  larger companies need a Remotion company licence.
- Voices and sound effects are generated by your ElevenLabs account under its terms. The example episodes' audio
  and the starter clips in `studio/library/sfx/` were generated on a paid plan.
- The code is free to use, change and share.
