from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import edge_tts
from reels.config import DB_PATH, OUTPUT_DIR, PREVIEWS_DIR, RUNS_DIR, VIDEOS_DIR, settings
from reels.db import init_db, session, topic_hash
from reels.video.qc import run_qc

TOPIC = "क्या होगा अगर एक विशाल एस्टेरॉयड पृथ्वी से टकरा जाए?"
RUN_ID = "run_asteroid_impact_3d"
VOICE = "hi-IN-MadhurNeural"

SCRIPT_BEATS = [
    {"index": 1, "text": "क्या होगा अगर एक विशाल एस्टेरॉयड पृथ्वी से टकरा जाए?", "bg": "deep_space"},
    {"index": 2, "text": "70,000 की रफ्तार से आते इस दानव की कोई चेतावनी नहीं होगी।", "bg": "earth_orbit"},
    {"index": 3, "text": "वायुमंडल में घुसते ही यह भयानक आग का गोला बन जाएगा!", "bg": "earth_orbit"},
    {"index": 4, "text": "आसमान सूरज से भी दस गुना ज़्यादा चमकेगा।", "bg": "city"},
    {"index": 5, "text": "टकराने से पहले, ज़मीन कांप उठेगी!", "bg": "deep_space"},
    {"index": 6, "text": "धमाका! दस करोड़ मेगाटन ऊर्जा एक साथ फूटेगी!", "bg": "impact_crater"},
    {"index": 7, "text": "सुपरसोनिक शॉकवेव हज़ारों किलोमीटर तक सब राख कर देगी।", "bg": "impact_crater"},
    {"index": 8, "text": "अंतरिक्ष तक उड़ता मलबा पिघले पत्थर बरसाएगा।", "bg": "impact_crater"},
    {"index": 9, "text": "अंतरिक्ष से, तबाही की लहर पूरी पृथ्वी पर फैलेगी।", "bg": "earth_orbit"},
    {"index": 10, "text": "अरबों टन राख पूरे वायुमंडल को ढक लेगी।", "bg": "science"},
    {"index": 11, "text": "सूरज गायब, और पूरी धरती बर्फ में जम जाएगी।", "bg": "city"},
    {"index": 12, "text": "लेकिन वैज्ञानिक अब प्लैनेटरी डिफेंस बना रहे हैं।", "bg": "science"},
    {"index": 13, "text": "काइनेटिक इम्पैक्टर्स से इसका रास्ता मोड़ा जा सकता है।", "bg": "deep_space"},
    {"index": 14, "text": "क्या हम बच पाएंगे? पार्ट 2 के लिए सब्सक्राइब करें!", "bg": "earth_orbit"},
]


from reels.tts.edge import synthesize


def synthesize_voice(text: str, out_path: Path) -> list[dict]:
    audio, words = synthesize(text, VOICE, rate="+18%")
    out_path.write_bytes(audio)
    word_cues = []
    for w in words:
        word_cues.append({
            "word": w["text"],
            "start": w["start"],
            "end": w["end"],
        })
    return word_cues


def generate_cinematic_music(dest: Path, duration: float) -> None:
    # Low frequency cosmic rumble drone + harmonic resonance
    ffmpeg = str(settings.ffmpeg())
    cmd = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=55:duration={duration:.2f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=110:duration={duration:.2f}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=164.81:duration={duration:.2f}",
        "-filter_complex",
        "[0:a]volume=0.35[a0];[1:a]volume=0.25[a1];[2:a]volume=0.18[a2];"
        "[a0][a1][a2]amix=inputs=3:normalize=0,lowpass=f=450,volume=0.6,afade=t=in:st=0:d=2,afade=t=out:st="
        + f"{max(0.0, duration - 2.5):.2f}:d=2.5[m]",
        "-map",
        "[m]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(dest),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    print(f"--- Generating New 3D Animated Reel: '{TOPIC}' ---")
    run_dir = RUNS_DIR / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)

    # 1. Synthesize Voice
    full_script_text = " ".join(beat["text"] for beat in SCRIPT_BEATS)
    voice_path = run_dir / "voice.mp3"
    print(f"[1/6] Synthesizing voiceover with EdgeTTS ({VOICE})...")
    word_cues = synthesize_voice(full_script_text, voice_path)
    print(f"      Voice generated: {voice_path} ({len(word_cues)} words detected)")

    # Probe voice duration
    probe_cmd = [
        str(settings.ffprobe()),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(voice_path),
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
    voice_dur = float(json.loads(probe_res.stdout)["format"]["duration"])
    total_dur_s = max(45.0, min(58.0, round(voice_dur + 0.8, 1)))
    fps = 30
    total_frames = int(round(total_dur_s * fps))
    print(f"      Audio duration: {voice_dur:.2f}s, target video duration: {total_dur_s:.2f}s ({total_frames} frames)")

    # 2. Cinematic Music Bed
    music_path = run_dir / "music.mp3"
    print("[2/6] Generating cinematic cosmic tension music bed...")
    generate_cinematic_music(music_path, total_dur_s)

    # Copy audio to Remotion public directory so staticFile can serve it
    anim_dir = ROOT / "animation"
    media_dir = anim_dir / "public" / "media" / "asteroid"
    media_dir.mkdir(parents=True, exist_ok=True)
    public_voice = media_dir / "voice.mp3"
    public_music = media_dir / "music.mp3"
    public_voice.write_bytes(voice_path.read_bytes())
    public_music.write_bytes(music_path.read_bytes())

    # 3. Assemble 14 Distinct Shots
    print("[3/6] Building 14-shot 3D cartoon storyboard...")
    shots = []
    cur_frame = 0
    shot_dur_frames = total_frames // len(SCRIPT_BEATS)

    for i, beat in enumerate(SCRIPT_BEATS, 1):
        dur = shot_dur_frames if i < len(SCRIPT_BEATS) else (total_frames - cur_frame)
        shot_id = f"S{i}"
        bg = beat["bg"]
        cam = {
            "zoom": 1.1 + (i % 3) * 0.12,
            "panY": -25 if i % 2 == 0 else 25,
            "shake": 18 if i in (6, 7) else 6 if i in (3, 4, 5) else 0,
            "durationFrames": dur,
        }
        shots.append({
            "id": shot_id,
            "index": i,
            "startFrame": cur_frame,
            "durationFrames": dur,
            "narration": beat["text"],
            "background": bg,
            "camera": cam,
            "style": "3d_cartoon",
        })
        cur_frame += dur

    timeline_props = {
        "title": TOPIC,
        "topic": TOPIC,
        "style": "3d_cartoon",
        "fps": fps,
        "width": 1080,
        "height": 1920,
        "totalDurationFrames": total_frames,
        "shots": shots,
        "captions": word_cues,
        "audio": {
            "voiceUrl": "media/asteroid/voice.mp3",
            "musicUrl": "media/asteroid/music.mp3",
        },
    }

    props_file = run_dir / "timeline.json"
    props_file.write_text(json.dumps(timeline_props, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. Render with Remotion
    out_video = VIDEOS_DIR / "reel_asteroid_impact.mp4"
    raw_video = run_dir / "raw_render.mp4"
    print(f"[4/6] Rendering 1080x1920 @ 30fps animated MP4 with Remotion...")
    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
    render_cmd = [
        npx_cmd,
        "remotion",
        "render",
        "src/index.ts",
        "AsteroidImpact",
        str(raw_video.resolve()),
        f"--props={props_file.resolve()}",
        "--concurrency=2",
        "--gl=angle",
    ]
    subprocess.run(render_cmd, cwd=anim_dir, check=True)
    print(f"      Visual render complete! ({raw_video.stat().st_size / (1024**2):.1f} MB)")

    # 5. Audio Mastering & Final Mix (-14 LUFS)
    print("[5/6] Mastering audio and muxing final video...")
    master_cmd = [
        str(settings.ffmpeg()),
        "-y",
        "-v",
        "error",
        "-i",
        str(raw_video),
        "-i",
        str(voice_path),
        "-i",
        str(music_path),
        "-filter_complex",
        "[1:a]volume=1.0[v];[2:a]volume=0.35[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]",
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-t",
        f"{total_dur_s:.3f}",
        "-movflags",
        "+faststart",
        str(out_video),
    ]
    subprocess.run(master_cmd, check=True)
    print(f"      Master complete! File: {out_video} ({out_video.stat().st_size / (1024**2):.1f} MB)")

    # 6. Thumbnail Generation
    print("      Generating video thumbnail...")
    thumb_path = PREVIEWS_DIR / "reel_asteroid_impact_thumb.jpg"
    thumb_cmd = [
        str(settings.ffmpeg()),
        "-y",
        "-v",
        "error",
        "-ss",
        "22.0",  # Frame during impact blast
        "-i",
        str(out_video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(thumb_path),
    ]
    subprocess.run(thumb_cmd, check=True)
    print(f"      Thumbnail saved: {thumb_path}")

    # 6. Quality Control Check
    print("[6/6] Executing Automated Quality Control (Part 9)...")
    qc = run_qc(out_video)
    print(f"      QC Score: {qc['score']}/100 | Status: {qc['status'].upper()}")
    if qc["critical_failures"]:
        print(f"      Critical Failures: {qc['critical_failures']}")
    if qc["warnings"]:
        print(f"      Warnings: {qc['warnings']}")

    # 7. Register in Database
    with session(DB_PATH) as conn:
        # Check or insert topic
        t_hash = topic_hash(TOPIC)
        conn.execute(
            "INSERT OR IGNORE INTO topics (topic_hash, title, source, score, status) "
            "VALUES (?, ?, 'ai_studio', 9.8, 'scripted')",
            (t_hash, TOPIC),
        )
        row = conn.execute("SELECT id FROM topics WHERE topic_hash = ?", (t_hash,)).fetchone()
        topic_id = row["id"]

        # Insert script
        conn.execute(
            "INSERT INTO scripts (topic_id, language, hook, scenes_json, style, storyboard_json, model) "
            "VALUES (?, 'hi', ?, ?, '3d_cartoon', ?, 'gemini-3.6-flash')",
            (
                topic_id,
                SCRIPT_BEATS[0]["text"],
                json.dumps(SCRIPT_BEATS, ensure_ascii=False),
                json.dumps(shots, ensure_ascii=False),
            ),
        )
        script_row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        script_id = script_row["id"]

        # Insert video
        conn.execute(
            "INSERT INTO videos (script_id, run_id, path, duration_s, width, height, style, quality_score, quality_report_json, status) "
            "VALUES (?, ?, ?, ?, 1080, 1920, '3d_cartoon', ?, ?, 'rendered') "
            "ON CONFLICT(run_id) DO UPDATE SET script_id = excluded.script_id, path = excluded.path, duration_s = excluded.duration_s, "
            "quality_score = excluded.quality_score, quality_report_json = excluded.quality_report_json, status = 'rendered'",
            (
                script_id,
                RUN_ID,
                str(out_video),
                total_dur_s,
                qc["score"],
                json.dumps(qc, ensure_ascii=False),
            ),
        )

    print("\nSUCCESS: Brand-New 3D Animated Reel Created and Registered in Database!")
    print(f"File: {out_video}")
    print(f"Duration: {total_dur_s}s | Shots: {len(shots)} | QC Score: {qc['score']}/100")


if __name__ == "__main__":
    main()
