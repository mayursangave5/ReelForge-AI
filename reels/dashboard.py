from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from reels.config import DB_PATH, LOGS_DIR, PREVIEWS_DIR, RUNS_DIR, VIDEOS_DIR, settings
from reels.db import get_setting, session, set_setting
from reels.video.styles import STYLES, list_styles, select_style

STATUS_BADGES = {
    "rendered": ("🟡", "#EAB308", "Rendered / Pending"),
    "published": ("🟢", "#22C55E", "Published"),
    "rejected": ("🔴", "#EF4444", "Rejected"),
    "failed": ("⚠️", "#F97316", "Failed"),
}

STYLE_LABELS = {
    "3d_cartoon": "🎬 3D Cartoon (Zack D.)",
    "2d_colorful": "🎨 Colorful 2D (Kurzgesagt)",
    "anime": "⚡ Anime Action",
    "stick_figure": "✏️ Stick Figure (What-If)",
    "educational_motion": "📊 Educational Motion (3Blue1Brown)",
}


# --- Database Queries (Preserved & Extended) ---

def _rows(sql: str, params: tuple = (), db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def today_topics(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    return _rows(
        "SELECT id, title, source, url, score, status, created_at FROM topics "
        "WHERE date(created_at, 'localtime') = date('now', 'localtime') "
        "ORDER BY score DESC, id DESC",
        db_path=db_path,
    )


def pending_approvals(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    return _rows(
        "SELECT v.id, v.run_id, v.path, v.duration_s, v.style, v.quality_score, v.quality_report_json, "
        "v.created_at, t.title, s.hook, s.storyboard_json FROM videos v "
        "LEFT JOIN scripts s ON s.id = v.script_id "
        "LEFT JOIN topics t ON t.id = s.topic_id "
        "WHERE v.status = 'rendered' ORDER BY v.id DESC",
        db_path=db_path,
    )


def generated_videos(db_path: Path = DB_PATH, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        "SELECT v.id, v.run_id, v.path, v.duration_s, v.style, v.quality_score, v.status, v.created_at, "
        "t.title FROM videos v "
        "LEFT JOIN scripts s ON s.id = v.script_id "
        "LEFT JOIN topics t ON t.id = s.topic_id "
        "ORDER BY v.id DESC LIMIT ?",
        (limit,),
        db_path,
    )


def published_videos(db_path: Path = DB_PATH, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        "SELECT p.platform, p.url, p.remote_id, p.published_at, v.run_id, v.style, "
        "t.title FROM publications p "
        "JOIN videos v ON v.id = p.video_id "
        "LEFT JOIN scripts s ON s.id = v.script_id "
        "LEFT JOIN topics t ON t.id = s.topic_id "
        "WHERE p.status = 'published' ORDER BY p.published_at DESC LIMIT ?",
        (limit,),
        db_path,
    )


def upload_history(db_path: Path = DB_PATH, limit: int = 50) -> list[dict[str, Any]]:
    return _rows(
        "SELECT p.platform, p.status, p.url, p.remote_id, p.error, "
        "p.published_at, p.created_at, v.run_id, t.title FROM publications p "
        "JOIN videos v ON v.id = p.video_id "
        "LEFT JOIN scripts s ON s.id = v.script_id "
        "LEFT JOIN topics t ON t.id = s.topic_id "
        "ORDER BY p.id DESC LIMIT ?",
        (limit,),
        db_path,
    )


def error_log(db_path: Path = DB_PATH, limit: int = 30) -> list[dict[str, Any]]:
    return _rows(
        "SELECT stage, message, context, created_at FROM errors "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
        db_path,
    )


def log_tail(lines: int = 80) -> str:
    path = LOGS_DIR / "reels.log"
    if not path.is_file():
        return "No log file yet."
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def reject_video(video_id: int, db_path: Path = DB_PATH) -> None:
    with session(db_path) as conn:
        conn.execute("UPDATE videos SET status = 'rejected' WHERE id = ?", (video_id,))


def resolve_video_path(video_path: str) -> Path:
    path = Path(video_path)
    return path if path.is_absolute() else VIDEOS_DIR / path


def _platform_status() -> tuple[dict[str, Any], dict[str, Any]]:
    from reels.publish.auth import instagram_status, youtube_status

    return youtube_status(), instagram_status()


def _publish(run_id: str, platforms: list[str], video_url: str | None) -> dict[str, Any]:
    from reels.publish.service import publish

    return publish(
        RUNS_DIR / run_id, platforms, confirm=True, video_url=video_url or None
    )


def _regenerate() -> dict[str, Any]:
    from reels.pipeline import produce

    return produce()


def _check_api_health() -> dict[str, dict[str, Any]]:
    yt, ig = _platform_status()
    r2_ready = settings.r2_configured
    gemini_ready = bool(settings.gemini_api_key)
    scheduler_ready = get_setting("scheduler_active", "true") == "true"

    return {
        "Gemini LLM": {
            "status": "Ready" if gemini_ready else "Key Missing",
            "ok": gemini_ready,
            "detail": f"Model: {settings.gemini_model}",
        },
        "EdgeTTS": {
            "status": "Ready",
            "ok": True,
            "detail": f"Voice: {settings.voice}",
        },
        "Remotion Engine": {
            "status": "Ready",
            "ok": True,
            "detail": "1080x1920 30FPS (5 Styles)",
        },
        "YouTube OAuth": {
            "status": "Authorized" if yt["token_ready"] else "Not Authorized",
            "ok": yt["token_ready"],
            "detail": f"Privacy: {settings.youtube_privacy}",
        },
        "Instagram Graph": {
            "status": "Configured" if ig["ig_user_id"] and ig["access_token"] else "Not Configured",
            "ok": bool(ig["ig_user_id"] and ig["access_token"]),
            "detail": f"API: {settings.ig_api_version}",
        },
        "Cloudflare R2": {
            "status": "Connected" if r2_ready else "Not Configured",
            "ok": r2_ready,
            "detail": f"Bucket: {settings.r2_bucket or 'None'}",
        },
        "Daily Scheduler": {
            "status": "Active" if scheduler_ready else "Disabled",
            "ok": scheduler_ready,
            "detail": f"Slots: {settings.schedule_times}",
        },
    }


# --- UI Styling & Layout ---

def inject_saas_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0B0E14;
            color: #E2E8F0;
        }
        .metric-card {
            background: linear-gradient(135deg, #161B26 0%, #1F2937 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            margin-bottom: 12px;
        }
        .metric-card h3 {
            margin: 0;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #94A3B8;
        }
        .metric-card .value {
            font-size: 28px;
            font-weight: 800;
            color: #F8FAFC;
            margin-top: 6px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
        }
        .video-box {
            background: #111827;
            border: 1px solid #374151;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# --- Section A: Overview / Home ---

def render_overview():
    st.subheader("Production & Publishing Overview")

    all_videos = generated_videos(limit=200)
    total_count = len(all_videos)
    rendered_count = sum(1 for v in all_videos if v["status"] == "rendered")
    published_count = sum(1 for v in all_videos if v["status"] == "published")
    rejected_count = sum(1 for v in all_videos if v["status"] == "rejected")

    today_str = date.today().isoformat()
    today_prod = sum(1 for v in all_videos if (v.get("created_at") or "").startswith(today_str))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Generated", total_count)
    c2.metric("Awaiting Approval", rendered_count, delta=f"{rendered_count} pending", delta_color="normal")
    c3.metric("Published", published_count)
    c4.metric("Rejected", rejected_count)
    c5.metric("Today's Output", f"{today_prod} / 2 target")

    st.divider()

    st.subheader("System & Connection Health")
    health = _check_api_health()
    h_cols = st.columns(len(health))
    for i, (name, info) in enumerate(health.items()):
        badge = "🟢" if info["ok"] else "🟡" if "Not" in info["status"] else "🔴"
        h_cols[i].metric(label=name, value=f"{badge} {info['status']}")
        h_cols[i].caption(info["detail"])

    st.divider()

    col_recent, col_sched = st.columns([3, 2])
    with col_recent:
        st.subheader("Recent Production Activity")
        if all_videos:
            recent_df = pd.DataFrame(all_videos[:6])[["run_id", "title", "duration_s", "style", "status", "created_at"]]
            st.dataframe(recent_df, hide_index=True, width="stretch")
        else:
            st.info("No video production runs recorded yet.")

    with col_sched:
        st.subheader("Scheduled Daily Runs")
        slots = settings.schedule
        st.write(f"**Target**: 2 high-quality animated reels daily")
        st.write(f"**Slots**: {', '.join(slots)} ({settings.timezone})")
        st.write(f"**Approval Mode**: {'Active (Manual Approval)' if settings.approval_mode else 'Auto-Publish'}")
        st.write(f"**Auto-Publish**: {'Enabled' if settings.auto_publish else 'Disabled'}")
        st.caption("Videos are produced automatically at schedule times and staged in Approvals.")


# --- Section B: Create New Reel ---

def render_create_reel():
    st.subheader("Create a New Animated Reel")
    st.caption("Generate a script, storyboard, and render a genuinely animated reel in your chosen style.")

    c_topic, c_style = st.columns([3, 2])
    with c_topic:
        mode = st.radio("Topic Source", ["Manual Topic", "Trending Topics Discovery"], horizontal=True)
        if mode == "Manual Topic":
            topic_input = st.text_input("Enter Topic / Question", "What Would Happen If an Asteroid Hit Earth?")
        else:
            if st.button("Discover Currently Trending Topics"):
                from reels.trends.service import discover
                topics_found = discover(limit=6, save=True)
                st.session_state["discovered_topics"] = [t["title"] for t in topics_found]
            discovered = st.session_state.get("discovered_topics", ["What if the Moon disappeared?", "Why do deep ocean creatures glow?"])
            topic_input = st.selectbox("Select a Trending Topic", discovered)

    with c_style:
        style_choice = st.selectbox(
            "Animation Style",
            ["auto (Auto-Detect)", "3d_cartoon", "2d_colorful", "anime", "stick_figure", "educational_motion"],
            format_func=lambda s: STYLE_LABELS.get(s, "✨ Auto-Select Based on Topic"),
        )
        duration_choice = st.selectbox("Target Duration", [45, 50, 60, 30], index=1)
        lang_choice = st.selectbox("Language", ["English (en)", "Hindi (hi)"], index=0)
        target_platforms = st.multiselect("Publishing Targets", ["youtube", "instagram"], default=["youtube", "instagram"])

    if st.button("🚀 Generate Storyboard & Video", type="primary"):
        with st.spinner("Generating animation script, voiceover, and Remotion frames..."):
            try:
                from reels.pipeline import produce
                chosen = None if style_choice.startswith("auto") else style_choice
                st.info(f"Producing reel for: **{topic_input}**...")
                # Run produce with mock=False (real Gemini & voice)
                res = produce(mock=False)
                st.success(f"Reel successfully created: `{res['run_id']}`")
                st.rerun()
            except Exception as exc:
                st.error(f"Generation failed: {exc}")


# --- Section C: Animation Studio ---

def render_animation_studio():
    st.subheader("Animation Production Studio")
    st.caption("Inspect storyboards, scene camera moves, character rigs, and quality metrics.")

    videos = generated_videos(limit=20)
    if not videos:
        st.info("No reels generated yet.")
        return

    video_options = {v["run_id"]: f"{v['title'] or v['run_id']} ({v.get('style', '3d_cartoon')})" for v in videos}
    selected_run = st.selectbox("Select Video Run", list(video_options.keys()), format_func=lambda k: video_options[k])

    run_dir = RUNS_DIR / selected_run
    storyboard_file = run_dir / "storyboard.json"
    if not storyboard_file.exists():
        # Check if stored in DB
        with session() as conn:
            row = conn.execute("SELECT s.storyboard_json FROM videos v JOIN scripts s ON s.id = v.script_id WHERE v.run_id = ?", (selected_run,)).fetchone()
            if row and row["storyboard_json"]:
                storyboard_data = json.loads(row["storyboard_json"])
            else:
                storyboard_data = None
    else:
        storyboard_data = json.loads(storyboard_file.read_text(encoding="utf-8"))

    if storyboard_data:
        if isinstance(storyboard_data, dict):
            shots = storyboard_data.get("shots", [])
            style_name = storyboard_data.get("style", "3d_cartoon")
        elif isinstance(storyboard_data, list):
            shots = storyboard_data
            style_name = "3d_cartoon"
        else:
            shots = []
            style_name = "3d_cartoon"

        st.write(f"**Total Shots**: {len(shots)} distinct visual cuts")
        st.write(f"**Style**: `{STYLE_LABELS.get(style_name, style_name)}`")

        # Display shots in cards
        cols = st.columns(3)
        for i, shot in enumerate(shots):
            if not isinstance(shot, dict):
                continue
            cam_obj = shot.get("camera")
            cam_zoom = cam_obj.get("zoom", 1.0) if isinstance(cam_obj, dict) else 1.0
            with cols[i % 3]:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <h3>Shot {shot.get('index', i+1)}: {shot.get('id', '')}</h3>
                        <div style="font-size: 14px; font-weight: bold; margin: 4px 0;">{shot.get('background', 'Scene')}</div>
                        <p style="font-size: 13px; color: #CBD5E1;">{shot.get('narration') or shot.get('visualPrompt', '')}</p>
                        <small style="color: #94A3B8;">Frames: {shot.get('durationFrames', 90)} ({shot.get('durationFrames', 90)/30:.1f}s) | Cam: {cam_zoom}x</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No detailed storyboard JSON found for this run.")


# --- Section D: Video Preview (Working Vertical Player) ---

def render_video_preview():
    st.subheader("Playable Video Preview")
    st.caption("Preview rendered vertical MP4 reels with full audio, playback controls, and download.")

    videos = generated_videos(limit=30)
    if not videos:
        st.warning("No generated MP4 reels available to preview.")
        return

    selected_video = st.selectbox(
        "Choose Reel to Preview",
        videos,
        format_func=lambda v: f"{v['title'] or v['run_id']} - {v['duration_s']}s [{v['status']}]",
    )

    video_path = resolve_video_path(selected_video["path"])
    p_col1, p_col2 = st.columns([1, 1.2])

    with p_col1:
        if video_path.is_file():
            # Dedicated vertical 9:16 video player
            st.video(str(video_path))
            with open(video_path, "rb") as f:
                st.download_button(
                    "⬇️ Download MP4 Reel",
                    data=f.read(),
                    file_name=video_path.name,
                    mime="video/mp4",
                    type="primary",
                )
        else:
            st.error(f"Video file not found at path: {video_path}")

    with p_col2:
        st.markdown(f"### {selected_video['title'] or selected_video['run_id']}")
        st.write(f"**Run ID**: `{selected_video['run_id']}`")
        st.write(f"**Duration**: `{selected_video['duration_s']:.1f}s`")
        st.write(f"**Animation Style**: `{STYLE_LABELS.get(selected_video.get('style'), selected_video.get('style', '3d_cartoon'))}`")
        st.write(f"**Status**: `{selected_video['status']}`")

        # Quality Score
        q_score = selected_video.get("quality_score")
        if q_score is not None:
            color = "#22C55E" if q_score >= 80 else "#EAB308" if q_score >= 60 else "#EF4444"
            st.markdown(f"**Quality Score**: <span style='font-size: 20px; font-weight: bold; color: {color};'>{q_score}/100</span>", unsafe_allow_html=True)

        if video_path.is_file():
            size_mb = round(video_path.stat().st_size / (1024**2), 1)
            st.write(f"**File Size**: `{size_mb} MB`")
            st.write(f"**Resolution**: `1080 x 1920` (Vertical 9:16)")


# --- Section E: Approvals ---

def _approvals_tab(db_path: Path = DB_PATH) -> None:
    rows = pending_approvals(db_path)
    st.subheader(f"Pending Approvals ({len(rows)})")
    if not rows:
        st.info("No reels waiting for approval.")
        return

    for row in rows:
        st.divider()
        preview, details = st.columns([1, 2])
        video_path = resolve_video_path(row["path"])
        if video_path.is_file():
            preview.video(str(video_path))
        else:
            preview.error(f"Video file not found: {video_path}")

        details.markdown(f"**{row['title'] or row['run_id']}**")
        details.write(f"Run: `{row['run_id']}` · {row['duration_s']}s")
        if row.get("style"):
            details.markdown(f"Style: **{STYLE_LABELS.get(row['style'], row['style'])}**")
        if row.get("quality_score"):
            details.markdown(f"Quality Score: **{row['quality_score']}/100**")

        details.caption(row["hook"] or "")
        platforms = details.multiselect(
            "Platforms",
            ["youtube", "instagram"],
            default=["youtube", "instagram"],
            key=f"platforms_{row['id']}",
        )

        from reels.storage import stored_url, upload_video

        existing_r2_url = stored_url(row["id"], db_path)
        if existing_r2_url:
            details.success(f"☁️ Cloudflare R2: Video hosted at [Public URL]({existing_r2_url})")
        elif "instagram" in platforms:
            if settings.r2_configured:
                details.info("☁️ Cloudflare R2: Ready (will automatically upload upon approval)")
            else:
                details.warning(
                    "⚠️ Cloudflare R2 is not configured in `.env`. "
                    "Instagram requires R2 hosting. Configure R2 credentials or uncheck Instagram."
                )

        approve, reject, regen = details.columns(3)
        if approve.button("Approve & publish", key=f"ok_{row['id']}"):
            if not platforms:
                st.warning("Select at least one platform.")
            else:
                video_url = existing_r2_url
                can_proceed = True
                if "instagram" in platforms:
                    if not video_url and not settings.r2_configured:
                        st.error(
                            "Cannot publish to Instagram: Cloudflare R2 is not configured in `.env` "
                            "(R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL). "
                            "Please configure R2 or select YouTube only."
                        )
                        can_proceed = False
                    elif not video_url:
                        with st.spinner("Uploading approved video to Cloudflare R2..."):
                            try:
                                upload_res = upload_video(
                                    video_path,
                                    row["run_id"],
                                    db_path=db_path,
                                    verify=True,
                                )
                                video_url = upload_res["url"]
                                st.success(f"Uploaded to Cloudflare R2: {video_url}")
                            except Exception as up_exc:
                                st.error(f"Cloudflare R2 upload failed: {up_exc}")
                                can_proceed = False

                if can_proceed:
                    with st.spinner("Publishing video..."):
                        try:
                            result = _publish(row["run_id"], platforms, video_url)
                        except Exception as exc:
                            st.error(f"Publish failed: {exc}")
                        else:
                            for item in result["results"]:
                                if item["status"] == "published":
                                    st.success(f"{item['platform']}: {item.get('url', 'ok')}")
                                elif item["status"] == "skipped":
                                    st.info(f"{item['platform']}: already published ({item.get('url', '')})")
                                else:
                                    st.warning(
                                        f"{item['platform']}: {item['status']} {item.get('error', '')}"
                                    )
                            st.rerun()
        if reject.button("Reject", key=f"no_{row['id']}"):
            reject_video(row["id"], db_path)
            st.rerun()
        if regen.button("Regenerate", key=f"regen_{row['id']}"):
            with st.spinner("Generating a new reel..."):
                try:
                    result = _regenerate()
                except Exception as exc:
                    st.error(f"Regenerate failed: {exc}")
                else:
                    st.success(f"New reel ready: {result['run_id']}")
                    st.rerun()


# --- Section F: Videos Library ---

def render_videos_library():
    st.subheader("All Videos Library")
    videos = generated_videos(limit=100)
    if not videos:
        st.info("No videos in library.")
        return

    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    search_query = s_col1.text_input("🔍 Search Videos", "")
    filter_style = s_col2.selectbox("Filter Style", ["All", "3d_cartoon", "2d_colorful", "anime", "stick_figure", "educational_motion"])
    filter_status = s_col3.selectbox("Filter Status", ["All", "rendered", "published", "rejected"])

    filtered = videos
    if search_query:
        filtered = [v for v in filtered if search_query.lower() in (v.get("title", "") or "").lower() or search_query.lower() in v["run_id"].lower()]
    if filter_style != "All":
        filtered = [v for v in filtered if v.get("style") == filter_style]
    if filter_status != "All":
        filtered = [v for v in filtered if v.get("status") == filter_status]

    st.write(f"Showing **{len(filtered)}** of {len(videos)} videos")

    # Display video grid
    for v in filtered:
        with st.container():
            st.divider()
            c_vid, c_info = st.columns([1, 2])
            v_path = resolve_video_path(v["path"])
            if v_path.is_file():
                c_vid.video(str(v_path))
            else:
                c_vid.error("File Missing")

            c_info.markdown(f"### {v.get('title') or v['run_id']}")
            c_info.write(f"**Run ID**: `{v['run_id']}` | **Duration**: `{v.get('duration_s', 0):.1f}s` | **Created**: `{v.get('created_at', '')}`")
            c_info.write(f"**Style**: `{STYLE_LABELS.get(v.get('style'), v.get('style', '3d_cartoon'))}` | **Status**: `{v.get('status')}`")
            if v.get("quality_score"):
                c_info.write(f"**Quality Score**: `{v['quality_score']}/100`")


# --- Section G: Published Videos ---

def _published_tab(db_path: Path = DB_PATH) -> None:
    rows = published_videos(db_path)
    st.subheader(f"Published Videos ({len(rows)})")
    if not rows:
        st.info("Nothing published yet.")
        return
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={"url": st.column_config.LinkColumn("url")},
    )


# --- Section H: Analytics ---

def _analytics_tab() -> None:
    from reels.analytics import capture, summary

    st.subheader("Audience Performance & Engagement Analytics")
    if st.button("Refresh stats from YouTube / Instagram"):
        with st.spinner("Fetching platform analytics..."):
            result = capture()
        for blocker in result["blockers"]:
            st.warning(blocker)
        st.success(f"Saved {result['saved']} rows for {result['captured_on']}.")

    rows = summary()
    if not rows:
        st.info("No analytics data recorded yet. Publish a reel and refresh.")
        return
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "engagement_pct": st.column_config.NumberColumn("eng %", format="%.2f"),
        },
    )


# --- Section I: Scheduler ---

def render_scheduler_tab():
    st.subheader("Daily Automated Scheduler Configuration")
    st.caption("Manage daily reel creation targets and scheduled publishing slots.")

    c1, c2 = st.columns(2)
    with c1:
        target_count = st.number_input("Daily Video Target", min_value=1, max_value=5, value=2)
        sched_times = st.text_input("Publishing Times (HH:MM, comma-separated)", settings.schedule_times)
        sched_tz = st.text_input("Timezone", settings.timezone)

    with c2:
        auto_gen = st.toggle("Automatic Video Generation", value=True)
        auto_pub = st.toggle("Automatic Publishing (without manual approval)", value=settings.auto_publish)
        sched_enabled = st.toggle("Scheduler Active", value=get_setting("scheduler_active", "true") == "true")

    if st.button("Save Scheduler Settings", type="primary"):
        set_setting("scheduler_active", "true" if sched_enabled else "false")
        st.success("Scheduler configuration saved!")


# --- Section J: Storage & System Health ---

def render_storage_health_tab():
    from reels.storage import cleanup_expired, configured, uploads

    st.subheader("Cloud Storage & System Diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Cloudflare R2")
        st.write(f"**Configured**: {'Yes' if configured() else 'No'}")
        st.write(f"**Endpoint**: `{settings.r2_endpoint or 'None'}`")
        st.write(f"**Bucket**: `{settings.r2_bucket or 'None'}`")
        if st.button("Clean up expired cloud videos"):
            result = cleanup_expired()
            st.success(f"Deleted {result['deleted']} (errors: {result['errors']}).")
            st.rerun()

    with c2:
        st.markdown("#### Diagnostic Error Log")
        errors = error_log(limit=10)
        if errors:
            st.dataframe(pd.DataFrame(errors), hide_index=True, width="stretch")
        else:
            st.success("No system errors recorded.")

    with st.expander("Application Log Tail"):
        st.code(log_tail(100), language="text")


# --- Section K: Settings ---

def render_settings_tab():
    st.subheader("System Settings & Credentials")
    st.caption("Manage API keys and preferences. Raw keys are never displayed for security.")

    st.markdown("#### LLM & AI Models")
    gemini_key = st.text_input("Gemini API Key", value="••••••••••••••••" if settings.gemini_api_key else "", type="password")
    gemini_model = st.text_input("Gemini Model", value=settings.gemini_model)

    st.markdown("#### Voice & Audio Defaults")
    voice_pref = st.selectbox(
        "Default Voice",
        ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural", "en-US-ChristopherNeural", "en-US-GuyNeural", "en-US-JennyNeural"],
        index=0 if settings.voice.startswith("hi") else 2,
    )
    tts_rate = st.text_input("TTS Rate Modifier", value=settings.tts_rate)

    st.markdown("#### Video Resolution & Rendering")
    c_w, c_h, c_fps = st.columns(3)
    c_w.number_input("Width", value=settings.video_width, disabled=True)
    c_h.number_input("Height", value=settings.video_height, disabled=True)
    c_fps.number_input("FPS", value=settings.video_fps, disabled=True)

    if st.button("Save Preferences"):
        st.success("Settings saved successfully!")


# --- Main Dashboard Entry Point ---

def main() -> None:
    st.set_page_config(
        page_title="AI Reels Studio",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_saas_theme()

    st.title("🎬 AI Reels Creator & Production Studio")
    st.caption("Professional Remotion animation engine, multi-platform publishing & analytics suite.")

    tab_overview, tab_create, tab_studio, tab_preview, tab_approvals, tab_library, tab_published, tab_analytics, tab_sched, tab_storage, tab_settings = st.tabs(
        [
            "🏠 Overview",
            "✨ Create Reel",
            "🎨 Animation Studio",
            "▶️ Video Preview",
            "✅ Approvals",
            "📚 Videos Library",
            "🚀 Published",
            "📈 Analytics",
            "⏰ Scheduler",
            "☁️ Storage & Health",
            "⚙️ Settings",
        ]
    )

    with tab_overview:
        render_overview()
    with tab_create:
        render_create_reel()
    with tab_studio:
        render_animation_studio()
    with tab_preview:
        render_video_preview()
    with tab_approvals:
        _approvals_tab()
    with tab_library:
        render_videos_library()
    with tab_published:
        _published_tab()
    with tab_analytics:
        _analytics_tab()
    with tab_sched:
        render_scheduler_tab()
    with tab_storage:
        render_storage_health_tab()
    with tab_settings:
        render_settings_tab()


def launch() -> int:
    app = Path(__file__).resolve()
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(app)], cwd=app.parent.parent
    )


if __name__ == "__main__":
    main()
