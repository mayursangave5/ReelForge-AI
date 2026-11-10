from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import (
    ASSETS_DIR,
    DB_PATH,
    FONTS_DIR,
    LOGS_DIR,
    MUSIC_DIR,
    OUTPUT_DIR,
    PREVIEWS_DIR,
    ROOT,
    RUNS_DIR,
    TOKENS_DIR,
    VIDEOS_DIR,
    settings,
)
from .db import get_setting, init_db, set_setting
from .logging_setup import setup_logging

OPTIONAL_KEYS = [
    ("GEMINI_API_KEY", settings.gemini_api_key),
    ("GCP_PROJECT_ID", settings.gcp_project_id),
    ("CLOUDFLARE_API_TOKEN", settings.cloudflare_api_token),
    ("FAL_KEY", settings.fal_key),
    ("ELEVENLABS_API_KEY", settings.elevenlabs_api_key),
]


def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return name, ok, detail


def _version_line(exe: Path) -> str:
    out = subprocess.run(
        [str(exe), "-version"], capture_output=True, text=True, timeout=30
    )
    text = out.stdout or out.stderr
    return text.splitlines()[0].strip() if text else "no output"


def doctor() -> int:
    results: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 11)
    results.append(_check("Python >= 3.11", py_ok, sys.version.split()[0]))

    ffmpeg_ok = ffprobe_ok = False
    try:
        ffmpeg = settings.ffmpeg()
        results.append(_check("FFmpeg", True, _version_line(ffmpeg)))
        ffmpeg_ok = True
    except FileNotFoundError as exc:
        results.append(_check("FFmpeg", False, str(exc)))

    try:
        ffprobe = settings.ffprobe()
        results.append(_check("FFprobe", True, _version_line(ffprobe)))
        ffprobe_ok = True
    except FileNotFoundError as exc:
        results.append(_check("FFprobe", False, str(exc)))

    for directory in (TOKENS_DIR, LOGS_DIR, VIDEOS_DIR, PREVIEWS_DIR, RUNS_DIR, MUSIC_DIR, FONTS_DIR):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            results.append(_check(f"Writable {directory.relative_to(ROOT)}", True))
        except OSError as exc:
            results.append(_check(f"Writable {directory.relative_to(ROOT)}", False, str(exc)))

    try:
        init_db()
        set_setting("doctor", __version__)
        value = get_setting("doctor")
        results.append(_check("SQLite", value == __version__, str(DB_PATH)))
    except (sqlite3.Error, OSError) as exc:
        results.append(_check("SQLite", False, str(exc)))

    font = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"
    font_note = "Noto Sans Devanagari present" if font.exists() else "Nirmala UI (system) fallback"
    results.append(_check("Hindi font", True, font_note))

    results.append(
        _check(
            "Content config",
            settings.language == "hi" and settings.voice.startswith("hi-IN"),
            f"lang={settings.language} voice={settings.voice} "
            f"tts={settings.tts_provider} rate={settings.tts_rate}",
        )
    )
    results.append(
        _check(
            "Schedule",
            True,
            f"{', '.join(settings.schedule)} ({settings.timezone})",
        )
    )
    results.append(
        _check(
            "Publishing safety",
            settings.approval_mode and not settings.auto_publish,
            f"approval_mode={settings.approval_mode} auto_publish={settings.auto_publish}",
        )
    )

    free_gb = shutil.disk_usage(ROOT).free / (1024**3)
    results.append(_check("Free disk on project drive", free_gb >= 5, f"{free_gb:.1f} GB"))

    print(f"\nReels Creator {__version__} - doctor\n")
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))

    configured = [name for name, value in OPTIONAL_KEYS if value]
    missing = [name for name, value in OPTIONAL_KEYS if not value]
    print("\n  Optional credentials:")
    print(f"    configured: {', '.join(configured) or 'none'}")
    print(f"    missing:    {', '.join(missing) or 'none'}")

    critical_ok = py_ok and ffmpeg_ok and ffprobe_ok
    print(f"\n  Core environment: {'READY' if critical_ok else 'NOT READY'}")
    print("  Credentials are only needed for script/voice/image/publish phases.\n")
    return 0 if critical_ok else 1


def cmd_trends(args: argparse.Namespace) -> int:
    from .trends.service import discover

    items, errors = discover(
        limit=args.limit, save=not args.no_save, allow_known=args.allow_known
    )
    if args.json:
        print(json.dumps({"items": items, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        print(f"\nTrends: {len(items)} candidates\n")
        for index, item in enumerate(items, 1):
            print(f"{index:>2}. {item['score']:.2f}  [{item['source']}]  {item['title']}")
            if item["url"]:
                print(f"    {item['url']}")
        if errors:
            print("\nSource warnings:")
            for error in errors:
                print(f"  - {error}")
    return 0 if items else 2


def cmd_script(args: argparse.Namespace) -> int:
    from .script.llm import LLMError, get_llm
    from .script.service import generate, select_topic

    try:
        llm = get_llm(force_mock=args.mock)
        topic = select_topic(args.topic_id)
        result = generate(topic, llm)
    except (LLMError, LookupError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    package = result["package"]
    print(f"\nTopic: {topic['title']}")
    print(f"Model: {llm.name}   Verdict: {result['verdict']}   Saved: {result['saved']}")
    print(f"\nHook: {package['hook_hi']}\n")
    for index, scene in enumerate(package["scenes"], 1):
        print(f"  {index}. [{scene['duration_s']}s] {scene['narration_hi']}")
    print(f"\nCTA: {package['cta_hi']}")
    print(f"Claims: {len(package['claims'])}")
    print(f"Run: {result['run_id']}")
    print(f"File: {result['script_path']}\n")
    return 0 if result["verdict"] != "fail" else 2


def cmd_render(args: argparse.Namespace) -> int:
    from .video.service import VideoError, render

    try:
        result = render(
            Path(args.voice_run), Path(args.out) if args.out else None
        )
    except (
        VideoError,
        FileNotFoundError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nVideo: {result['video']}")
    print(
        f"Duration: {result['duration_s']}s   Scenes: {result['scenes']}   "
        f"Size: {result['size_mb']} MB"
    )
    print(
        f"Images: {result['images_fetched']} fetched, "
        f"{result['images_cached']} cached, "
        f"{result['images_fallback']} fallback"
    )
    print(f"Thumbnail: {result['thumbnail']}")
    print(f"Music: {result['music']}\n")
    return 0


def cmd_auth(args: argparse.Namespace) -> int:
    from .publish.auth import (
        AuthError,
        instagram_status,
        redact,
        youtube_credentials,
        youtube_status,
    )

    print("\nPublishing credentials\n")
    if args.platform == "youtube":
        try:
            youtube_credentials(interactive=True)
        except AuthError as exc:
            print(f"  YouTube: {redact(str(exc))}")
            return 1
        print("  YouTube: authorized (token saved to data/tokens/youtube_token.json)")

    yt = youtube_status()
    ig = instagram_status()
    print(f"  YouTube client JSON: {'found' if yt['client_secrets_ready'] else 'missing'}")
    print(f"  YouTube token:       {'found' if yt['token_ready'] else 'missing'}")
    print(f"  YouTube scopes:      {', '.join(yt['scopes']) or 'none'}")
    print(f"  Instagram user id:   {'set' if ig['ig_user_id'] else 'missing'}")
    print(f"  Instagram token:     {'set' if ig['access_token'] else 'missing'}")
    print(f"  Instagram API:       {ig['api_version']}")
    print("\n  Setup guide: docs/publishing-setup.md\n")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    from .publish.service import publish

    platforms = (
        ["youtube", "instagram"] if args.platform == "both" else [args.platform]
    )
    try:
        result = publish(
            Path(args.voice_run),
            platforms,
            confirm=args.confirm,
            video_url=args.video_url,
        )
    except (LookupError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    mode = "LIVE UPLOAD" if args.confirm else "DRY RUN (nothing uploaded)"
    print(f"\nPublish {mode}: {result['run_id']}\n")
    failed = False
    for item in result["results"]:
        status = item["status"]
        print(f"  {item['platform']}: {status}")
        if item.get("url"):
            print(f"    {item['url']}")
        if item.get("remote_id"):
            print(f"    id: {item['remote_id']}")
        if item.get("blockers"):
            for blocker in item["blockers"]:
                print(f"    blocker: {blocker}")
        if item.get("error"):
            failed = True
            print(f"    error: {item['error']}")
        if status == "failed":
            failed = True
    if not args.confirm:
        print("\n  Add --confirm to publish for real (approval required).")
    print()
    return 1 if failed else 0


def cmd_metadata(args: argparse.Namespace) -> int:
    from .metadata.service import generate
    from .script.llm import LLMError, get_llm

    try:
        result = generate(Path(args.voice_run), get_llm(force_mock=args.mock))
    except (LLMError, LookupError, ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    instagram = result["instagram"]
    youtube = result["youtube"]
    print(f"\nVideo: {result['video']}  (id {result['video_id']})\n")
    print("Instagram:")
    print(f"  {instagram.full_caption}")
    print("\nYouTube:")
    print(f"  Title: {youtube.title}")
    print(f"  {youtube.caption}")
    print(f"  Hashtags: {' '.join('#' + tag for tag in youtube.hashtags)}")
    print(f"  Tags: {', '.join(youtube.tags)}")
    print(f"\nMetadata: {result['metadata']}")
    print(f"Subtitles: {result['srt']}")
    print(
        f"\nReady for review. approval_mode={settings.approval_mode} "
        f"auto_publish={settings.auto_publish} - nothing was uploaded.\n"
    )
    return 0


def cmd_produce(args: argparse.Namespace) -> int:
    from .pipeline import produce

    try:
        result = produce(
            mock=args.mock,
            discover_trends=not args.no_trends,
            publish_after=True if args.publish else None,
        )
    except (
        RuntimeError,
        LookupError,
        ValueError,
        FileNotFoundError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nReel ready: {result['run_id']}")
    print(f"Topic:   {result['topic']}")
    print(f"Video:   {result['video']}")
    print(f"Length:  {result['duration_s']}s")
    print(f"Metadata:{result['metadata']}")
    if result["publish"]:
        for item in result["publish"]["results"]:
            print(f"  {item['platform']}: {item['status']}")
            if item.get("url"):
                print(f"    {item['url']}")
    else:
        print(
            f"\nAwaiting approval (approval_mode={settings.approval_mode}, "
            f"auto_publish={settings.auto_publish})."
        )
        print(
            f"Publish: python -m reels publish --voice-run runs/{result['run_id']} --confirm"
        )
    print()
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from .scheduler import serve

    serve(mock=args.mock, run_now=args.run_now)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from .dashboard import launch

    return launch()


def cmd_analytics(args: argparse.Namespace) -> int:
    from .analytics import capture, summary

    if args.capture:
        result = capture()
        print(f"\nCaptured {result['saved']} rows for {result['captured_on']}.")
        if result["blockers"]:
            print("Warnings:")
            for blocker in result["blockers"]:
                print(f"  - {blocker}")

    rows = summary(limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("\nNo analytics yet. Publish videos, then run with --capture.\n")
        return 0
    print(f"\n{'Views':>8} {'Likes':>7} {'Cmts':>6} {'Shares':>7} {'Eng%':>6}  Topic")
    for row in rows:
        print(
            f"{row['views']:>8} {row['likes']:>7} {row['comments']:>6} "
            f"{row['shares']:>7} {row['engagement_pct']:>6}  {row['title'][:60]}"
        )
    print()
    return 0


def cmd_voice(args: argparse.Namespace) -> int:
    from .tts.edge import TTSError, hindi_voices
    from .tts.service import SAMPLE_TEXT, build_voiceover, load_script, voice_lab

    if settings.tts_provider != "edge":
        print(
            f"ERROR: TTS_PROVIDER={settings.tts_provider}. Phase 4 uses the free "
            "built-in provider; set TTS_PROVIDER=edge.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.list:
            for item in hindi_voices():
                print(f"{item['ShortName']:<26} {item['Gender']:<6} {item['Locale']}")
            return 0

        if args.text or args.compare:
            results = voice_lab(
                text=args.text or SAMPLE_TEXT,
                voices=None if args.compare else [args.voice],
                rate=args.rate,
                out_dir=args.out,
            )
            print("\nVoice lab:")
            for item in results:
                print(
                    f"  {item['voice']}  {item['duration_s']}s  "
                    f"{item['captions']} captions"
                )
                print(f"    {item['audio']}")
                print(f"    {item['srt']}")
            print()
            return 0

        meta = load_script(args.script_id)
        result = build_voiceover(
            meta["package"],
            voice=args.voice,
            rate=args.rate,
            script_id=meta["id"],
            title=meta["title"],
            out_dir=args.out,
        )
        timing = result["timing"]
        print(
            f"\nVoiceover: {timing['voice']}  rate={timing['rate']}  "
            f"total={timing['total_s']}s"
        )
        print(f"Scenes: {len(timing['scenes'])}   Captions: {timing['captions']}")
        if not settings.min_duration_s <= timing["total_s"] <= settings.max_duration_s:
            print(
                f"WARNING: voiceover {timing['total_s']}s is outside "
                f"{settings.min_duration_s}-{settings.max_duration_s}s; adjust --rate.",
                file=sys.stderr,
            )
        print(f"Audio: {result['audio']}")
        print(f"SRT:   {result['srt']}")
        print(f"Dir:   {result['run_dir']}\n")
        return 0
    except (
        TTSError,
        LookupError,
        FileNotFoundError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    setup_logging()
    parser = argparse.ArgumentParser(prog="reels", description="AI Reels Creator & Publisher")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="check environment, FFmpeg, database and config")
    sub.add_parser("init-db", help="create or upgrade the SQLite database")
    trends = sub.add_parser("trends", help="discover and rank trending topics")
    trends.add_argument("--limit", type=int, default=10)
    trends.add_argument("--json", action="store_true", help="machine-readable output")
    trends.add_argument("--no-save", action="store_true", help="do not write candidates to the DB")
    trends.add_argument("--allow-known", action="store_true", help="ignore history dedupe (debug)")
    script = sub.add_parser("script", help="generate and fact-check a Hindi script")
    script.add_argument("--topic-id", type=int, help="use a specific topic id")
    script.add_argument("--mock", action="store_true", help="offline mock provider (no API key)")
    voice = sub.add_parser("voice", help="synthesize Hindi voiceover and subtitles")
    voice.add_argument("--script-id", type=int, help="script id (default: latest)")
    voice.add_argument("--text", help="voice-lab text instead of a script")
    voice.add_argument("--voice", default=settings.voice)
    voice.add_argument("--rate", default=settings.tts_rate, help='e.g. "-4%" or "+0%"')
    voice.add_argument("--compare", action="store_true", help="voice lab: all Hindi voices")
    voice.add_argument("--list", action="store_true", help="list Hindi voices and exit")
    voice.add_argument("--out", type=Path, help="output directory override")
    render_cmd = sub.add_parser("render", help="assemble the final MP4 from a voiceover run")
    render_cmd.add_argument("--voice-run", required=True, help="e.g. runs/<run_id>_voice1")
    render_cmd.add_argument("--out", type=Path, help="output mp4 path override")
    metadata_cmd = sub.add_parser("metadata", help="generate platform captions and hashtags")
    metadata_cmd.add_argument("--voice-run", required=True, help="e.g. runs/<run_id>_voice1")
    metadata_cmd.add_argument("--mock", action="store_true", help="offline mock provider (no API key)")
    auth_cmd = sub.add_parser("auth", help="check or create publishing credentials")
    auth_cmd.add_argument(
        "--platform",
        choices=["status", "youtube", "instagram"],
        default="status",
        help="youtube runs the OAuth browser flow",
    )
    publish_cmd = sub.add_parser("publish", help="dry-run or upload to YouTube/Instagram")
    publish_cmd.add_argument("--voice-run", required=True)
    publish_cmd.add_argument(
        "--platform", choices=["both", "youtube", "instagram"], default="both"
    )
    publish_cmd.add_argument(
        "--confirm", action="store_true", help="actually upload (default is dry run)"
    )
    publish_cmd.add_argument(
        "--video-url", help="public HTTPS URL required by Instagram"
    )

    produce_cmd = sub.add_parser(
        "produce", help="run trends -> script -> voice -> render -> metadata once"
    )
    produce_cmd.add_argument("--mock", action="store_true", help="offline mock provider")
    produce_cmd.add_argument(
        "--no-trends", action="store_true", help="reuse an existing DB topic"
    )
    produce_cmd.add_argument(
        "--publish", action="store_true", help="upload after rendering (live)"
    )
    schedule_cmd = sub.add_parser("schedule", help="run the daily scheduler (blocking)")
    schedule_cmd.add_argument("--mock", action="store_true", help="offline mock provider")
    schedule_cmd.add_argument(
        "--run-now", action="store_true", help="produce one reel immediately, then wait"
    )
    sub.add_parser("dashboard", help="open the Streamlit approval dashboard")
    analytics_cmd = sub.add_parser(
        "analytics", help="capture and show views/likes/comments per topic"
    )
    analytics_cmd.add_argument(
        "--capture", action="store_true", help="fetch fresh stats from platform APIs"
    )
    analytics_cmd.add_argument("--limit", type=int, default=20)
    analytics_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "init-db":
        path = init_db()
        print(f"Database ready: {path}")
        return 0
    if args.command == "trends":
        return cmd_trends(args)
    if args.command == "script":
        return cmd_script(args)
    if args.command == "voice":
        return cmd_voice(args)
    if args.command == "render":
        return cmd_render(args)
    if args.command == "metadata":
        return cmd_metadata(args)
    if args.command == "auth":
        return cmd_auth(args)
    if args.command == "publish":
        return cmd_publish(args)
    if args.command == "produce":
        return cmd_produce(args)
    if args.command == "schedule":
        return cmd_schedule(args)
    if args.command == "dashboard":
        return cmd_dashboard(args)
    if args.command == "analytics":
        return cmd_analytics(args)
    return doctor()


if __name__ == "__main__":
    raise SystemExit(main())
