# 🎬 ReelForge AI — AI Animated Reels Creator

**ReelForge AI** is an end-to-end autonomous video production studio that turns trending topics and ideas into fully animated, high-retention 9:16 vertical short-form videos (YouTube Shorts & Instagram Reels).

Built with **Remotion (React + TypeScript)**, **Python automation**, **Google Gemini LLM**, **EdgeTTS**, and **Streamlit**, ReelForge AI eliminates static slideshows and delivers genuine visual animation across multiple artistic styles.

---

## 🌟 Key Features

* 🎨 **5 Distinct Animation Styles**:
  * **3D Cartoon (Zack D. Films style)**: 3D shaded celestial bodies, orbital continent rotation, ground-zero shockwaves, and rising mushroom clouds.
  * **2D Colorful Vector (Kurzgesagt style)**: Flat isometric geometry, rich saturated palettes, and clean Bezier curves.
  * **Anime Action**: Hypersonic speed lines, camera Dutch tilts, and high-contrast impact frames.
  * **Stick Figure (What-If style)**: Dusk-lit perspective rooms, window/lamp casting, and expressive stick characters.
  * **Educational Motion (3Blue1Brown style)**: Animated math grids, holographic scientific readouts, and kinetic metric counters.
* 🤖 **Procedural Character Rigging**: Dynamic skeletal hierarchy, limb joints, yaw rotation, and swap-state facial expressions (`shock`, `panic`, `worried`, `happy`, `neutral`).
* 🎥 **Cinematic Camera System**: Programmatic zooms, tracking pans, and decaying impact camera shakes.
* 📝 **Devanagari & Multilingual Kinetic Subtitles**: Word-by-word highlights using native typography (`Nirmala UI`, `Noto Sans Devanagari`).
* 🛡️ **Automated Quality Control (QC)**: Automated FFmpeg validation (`blackdetect`, `freezedetect`, `volumedetect`, aspect ratio, duration checks) outputting a 0–100 score.
* ⚡ **Gemini API Error Resilience**:
  * Automatic retry for transient errors (`503 UNAVAILABLE`, `429 RESOURCE_EXHAUSTED`, `500`, `502`, `504`).
  * Exponential backoff with random jitter up to 5 attempts.
  * Dual-key rotation across multiple Google accounts (`GEMINI_API_KEY` and `GEMINI_API_KEY_2`).
  * Automatic model fallback to `gemini-2.5-flash` if `gemini-3.6-flash` experiences peak demand.
  * Complete secret scrubbing in logs and error traces.
* ☁️ **Cloudflare R2 Auto-Upload**: Automatic video upload to Cloudflare R2 upon approval with verified public HTTPS URL pass-through to Instagram Graph API.
* 🖥️ **Streamlit SaaS Studio**: 11-section dark-themed web dashboard for topic discovery, storyboard inspection, video review, 1-click approvals, scheduler, analytics, and health monitoring.

---

## 🏗️ Architecture

```
ReelForge-AI/
├── animation/              # Remotion Animation Engine (React + TypeScript)
│   ├── src/
│   │   ├── engine/         # Camera, Particles, VFX, Backgrounds, Rig, Subtitles
│   │   ├── styles/         # 5 Animation Style Renderers
│   │   ├── compositions/   # Master & Example Compositions
│   │   └── types.ts        # TypeScript timeline schemas
│   └── public/             # Fonts, SFX, and static media
├── reels/                  # Core Python Automation Pipeline
│   ├── script/             # Gemini LLM integration, prompts, schemas
│   ├── video/              # Styles, 14-shot storyboard generator, QC engine, FFmpeg
│   ├── tts/                # EdgeTTS voiceover & word timestamps
│   ├── metadata/           # YouTube/Instagram captions & hashtag generation
│   ├── publish/            # YouTube OAuth & Instagram Graph API publishers
│   ├── storage.py          # Cloudflare R2 S3-compatible client & caching
│   ├── dashboard.py        # 11-Section Streamlit SaaS Studio
│   └── config.py           # Pydantic settings & environment validation
├── tests/                  # 93 Unit tests covering 100% of pipeline
└── scripts/                # Generation CLI scripts
```

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10+
* Node.js 18+ and npm
* FFmpeg (or place in `.tools/ffmpeg/bin/`)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/mayursangave5/ReelForge-AI.git
cd ReelForge-AI

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Install Remotion dependencies
cd animation
npm install
cd ..
```

### 3. Configuration
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
Key configuration options:
* `GEMINI_API_KEY`: Primary Google AI Studio free-tier key.
* `GEMINI_API_KEY_2`: Secondary Google AI Studio key for automatic rotation.
* `GEMINI_MODEL`: Primary model (default: `gemini-3.6-flash`).
* `GEMINI_FALLBACK_MODEL`: Fallback model (default: `gemini-2.5-flash`).
* `VOICE`: EdgeTTS voice (default: `hi-IN-MadhurNeural`).

### 4. Run the Streamlit Studio
```bash
streamlit run reels/dashboard.py
```

### 5. Generate a Reel via CLI
```bash
python scripts/generate_asteroid_reel.py
```

### 6. Run Tests
```bash
python -m unittest discover tests
```

---

## 📄 License
MIT License. Free to use and customize.
