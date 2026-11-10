---
name: python-video-automation
description: End-to-end Python pipeline automation for automated daily reels production. Covers trending topic research, Gemini structured prompting, EdgeTTS audio synthesis, Remotion CLI orchestration, QC validation, and SQLite persistence.
---

# Python Video Automation Skill

## Pipeline Flow
1. **Topic Discovery**: Poll Google Trends / RSS / YouTube search for trending topics with score weighting.
2. **Script & Storyboard**: Call Gemini API with structured JSON output schemas for multi-shot pacing and visual prompts.
3. **Voiceover**: Generate natural speech with `edge-tts` and extract word-level timestamps.
4. **Render**: Assemble timeline props and invoke Remotion CLI headlessly to generate MP4.
5. **Quality Control**: Automated FFmpeg verification of motion, audio, resolution, and subtitles.
6. **Publishing**: Multi-platform upload to YouTube Shorts and Instagram Reels with idempotency.
