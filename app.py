"""
Channel Monitor — Standalone Web UI
Telegram channel scraper with auto-translation, media download, and live job logs.
"""

import asyncio
import io
import json
import os
import shutil
import threading
import traceback
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, Response, jsonify, render_template,
    request, send_from_directory
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = DATA_DIR / "channel_monitor"

# ── Persistent job store ─────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
JOBS_INDEX = DATA_DIR / "jobs_index.json"


def _save_jobs_index():
    """Persist job metadata to disk (excludes live log to keep it fast)."""
    try:
        snapshot = {}
        for jid, j in _jobs.items():
            snapshot[jid] = {
                "status":     j["status"],
                "config":     j["config"],
                "output_dir": j["output_dir"],
                "started_at": j["started_at"],
                "ended_at":   j.get("ended_at"),
                "error":      j.get("error"),
                "log":        j.get("log", []),
            }
        with open(JOBS_INDEX, "w") as f:
            json.dump(snapshot, f, indent=2)
    except Exception:
        pass


def _load_jobs_index():
    """Load persisted jobs on startup."""
    if not JOBS_INDEX.exists():
        return
    try:
        with open(JOBS_INDEX) as f:
            snapshot = json.load(f)
        for jid, j in snapshot.items():
            # Mark any 'running' jobs as error — they died with the process
            if j["status"] == "running":
                j["status"] = "error"
                j["error"] = "Process restarted while job was running"
                j["ended_at"] = j["ended_at"] or datetime.utcnow().isoformat()
            _jobs[jid] = j
    except Exception:
        pass


def _new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _get_telegram_creds() -> dict:
    return {
        "api_id":   os.getenv("TELEGRAM_API_ID", ""),
        "api_hash": os.getenv("TELEGRAM_API_HASH", ""),
        "phone":    os.getenv("TELEGRAM_PHONE", ""),
    }


# Load persisted jobs on startup
_load_jobs_index()


# ── Core channel monitor logic (inlined from channel_monitor.py) ──────────────

SUPPORTED_LANGUAGES = {
    "fa": {"name": "Farsi",                "flag": "🇮🇷"},
    "ru": {"name": "Russian",              "flag": "🇷🇺"},
    "zh-cn": {"name": "Chinese (Simplified)",  "flag": "🇨🇳"},
    "zh-tw": {"name": "Chinese (Traditional)", "flag": "🇹🇼"},
    "ko": {"name": "Korean",               "flag": "🇰🇵"},
    "ar": {"name": "Arabic",               "flag": "🇸🇦"},
    "uk": {"name": "Ukrainian",            "flag": "🇺🇦"},
    "de": {"name": "German",               "flag": "🇩🇪"},
    "fr": {"name": "French",               "flag": "🇫🇷"},
    "es": {"name": "Spanish",              "flag": "🇪🇸"},
    "en": {"name": "English",              "flag": "🇬🇧"},
}

LANG_DISPLAY = {
    "fa": "🇮🇷 Farsi",
    "ru": "🇷🇺 Russian",
    "zh-cn": "🇨🇳 Chinese (Simplified)",
    "zh-tw": "🇹🇼 Chinese (Traditional)",
    "ko": "🇰🇵 Korean",
    "ar": "🇸🇦 Arabic",
    "uk": "🇺🇦 Ukrainian",
    "de": "🇩🇪 German",
    "fr": "🇫🇷 French",
    "es": "🇪🇸 Spanish",
    "en": "🇬🇧 English",
}

RTL_LANGUAGES = {"fa", "ar", "he", "ur"}


def detect_language(text: str) -> str:
    from langdetect import detect, LangDetectException
    if not text or len(text.strip()) < 10:
        return "unknown"
    try:
        detected = detect(text)
        if detected in ("zh-cn", "zh-tw", "zh"):
            return "zh-cn"
        return detected
    except LangDetectException:
        return "unknown"


def get_lang_display(lang_code: str) -> str:
    return LANG_DISPLAY.get(lang_code, f"🌐 {lang_code.upper()}")


def is_rtl(lang_code: str) -> bool:
    return lang_code in RTL_LANGUAGES


_translator_cache = {}


def translate_text(text: str, source_lang: str) -> str:
    from deep_translator import GoogleTranslator
    if not text or not text.strip():
        return ""
    if source_lang in ("en", "unknown"):
        return text
    try:
        if source_lang not in _translator_cache:
            _translator_cache[source_lang] = GoogleTranslator(source=source_lang, target="en")
        translator = _translator_cache[source_lang]
        chunk_size = 4500
        if len(text) <= chunk_size:
            return translator.translate(text)
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        return " ".join([translator.translate(c) for c in chunks])
    except Exception as e:
        return f"[Translation error: {e}]"


def format_entities(text: str, entities) -> str:
    import html
    from telethon.tl.types import (
        MessageEntityBold, MessageEntityItalic, MessageEntityCode,
        MessageEntityPre, MessageEntityUrl, MessageEntityTextUrl,
        MessageEntityMention, MessageEntityHashtag,
    )
    if not text:
        return ""
    if not entities:
        return html.escape(text).replace("\n", "<br>")

    tags = []
    for ent in entities:
        s, length = ent.offset, ent.length
        seg_esc = html.escape(text[s:s+length])
        if isinstance(ent, MessageEntityBold):
            tags.append((s, s+length, "<b>", "</b>"))
        elif isinstance(ent, MessageEntityItalic):
            tags.append((s, s+length, "<i>", "</i>"))
        elif isinstance(ent, MessageEntityCode):
            tags.append((s, s+length, "<code>", "</code>"))
        elif isinstance(ent, MessageEntityPre):
            tags.append((s, s+length, "<pre>", "</pre>"))
        elif isinstance(ent, MessageEntityTextUrl):
            tags.append((s, s+length, f'<a href="{ent.url}" target="_blank">', "</a>"))
        elif isinstance(ent, MessageEntityUrl):
            tags.append((s, s+length, f'<a href="{seg_esc}" target="_blank">', "</a>"))
        elif isinstance(ent, MessageEntityMention):
            tags.append((s, s+length, '<span class="mention">', "</span>"))
        elif isinstance(ent, MessageEntityHashtag):
            tags.append((s, s+length, '<span class="hashtag">', "</span>"))

    output = html.escape(text)
    for s, e, open_t, close_t in sorted(tags, key=lambda x: x[0], reverse=True):
        seg = html.escape(text[s:e])
        output = output[:s] + open_t + seg + close_t + output[e:]

    return output.replace("\n", "<br>")


def generate_html(messages, channel_title, output_path):
    html_messages = []
    for m in reversed(messages):
        media_block = ""
        if m["media_type"] == "photo" and m["media_path"]:
            media_block = f'<img src="{m["media_path"]}" class="msg-photo" alt="photo">'
        elif m["media_type"] == "image_doc" and m["media_path"]:
            media_block = f'<img src="{m["media_path"]}" class="msg-photo" alt="image">'
        elif m["media_type"] == "video" and m["media_path"]:
            media_block = f'''<video controls class="msg-video">
                <source src="{m["media_path"]}">
                Your browser does not support video playback.
            </video>'''
        elif m["media_type"] == "video" and not m["media_path"]:
            media_block = '<div class="media-placeholder">🎥 Video (skipped)</div>'
        elif m["media_type"] == "webpage" and m.get("media_url"):
            media_block = f'<div class="webpage-preview"><a href="{m["media_url"]}" target="_blank">🔗 {m["media_url"]}</a></div>'

        text_block = ""
        lang_code = m.get("detected_lang", "unknown")
        lang_display = get_lang_display(lang_code)
        text_dir = "rtl" if is_rtl(lang_code) else "ltr"

        if m["formatted_html"]:
            already_english = lang_code == "en"
            if already_english:
                text_block = f'''
                <div class="lang-badge">{lang_display}</div>
                <div class="msg-text original" dir="{text_dir}">{m["formatted_html"]}</div>
                '''
            else:
                text_block = f'''
                <div class="lang-badge">{lang_display}</div>
                <div class="msg-text original" dir="{text_dir}">{m["formatted_html"]}</div>
                <div class="msg-divider">🔽 English Translation</div>
                <div class="msg-text translated">{m["translated_en"]}</div>
                '''
        elif not m["formatted_html"] and m["media_type"]:
            text_block = '<div class="msg-text translated" style="color:#555">[No caption]</div>'

        meta_views = f'👁 {m["views"]}' if m["views"] else ""
        reply_badge = f'<span class="reply-badge">↩ Reply to #{m["reply_to"]}</span>' if m["reply_to"] else ""

        html_messages.append(f'''
        <div class="message" id="msg-{m["id"]}">
            <div class="msg-meta">
                <span class="msg-id">#{m["id"]}</span>
                <span class="msg-date">{m["date"]}</span>
                {reply_badge}
                <span class="msg-views">{meta_views}</span>
            </div>
            {media_block}
            {text_block}
        </div>
        ''')

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{channel_title} — Channel Monitor</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0e0e0e; color: #e0e0e0; max-width: 780px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #29b6f6; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        .stats {{ color: #555; font-size: 0.85em; margin-bottom: 24px; }}
        .message {{ background: #1a1a2e; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; border-left: 3px solid #29b6f6; }}
        .msg-meta {{ font-size: 0.75em; color: #888; margin-bottom: 8px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
        .msg-id {{ color: #29b6f6; font-weight: bold; }}
        .reply-badge {{ background: #1e3a5f; padding: 2px 6px; border-radius: 4px; color: #90caf9; }}
        .lang-badge {{ display: inline-block; font-size: 0.72em; background: #0d2137; color: #81d4fa; padding: 2px 8px; border-radius: 12px; margin-bottom: 6px; border: 1px solid #1a4a6e; }}
        .msg-photo {{ max-width: 100%; border-radius: 8px; margin: 8px 0; display: block; }}
        .msg-video {{ max-width: 100%; border-radius: 8px; margin: 8px 0; display: block; background: #000; }}
        .msg-text {{ padding: 6px 0; line-height: 1.8; font-size: 0.97em; }}
        .original {{ color: #ffcc80; font-size: 1.05em; border-right: 3px solid #ff8f00; padding-right: 10px; }}
        .original[dir="ltr"] {{ border-right: none; border-left: 3px solid #ff8f00; padding-right: 0; padding-left: 10px; }}
        .msg-divider {{ color: #444; font-size: 0.75em; margin: 6px 0; }}
        .translated {{ color: #a5d6a7; }}
        .media-placeholder {{ color: #777; font-style: italic; padding: 8px 0; }}
        .webpage-preview {{ background: #111; padding: 8px 12px; border-radius: 6px; margin: 6px 0; border: 1px solid #2a2a2a; }}
        .webpage-preview a {{ color: #29b6f6; text-decoration: none; }}
        .mention {{ color: #80cbc4; }}
        .hashtag {{ color: #ce93d8; }}
        code {{ background: #2a2a2a; padding: 2px 6px; border-radius: 3px; font-family: monospace; color: #ef9a9a; }}
        pre {{ background: #2a2a2a; padding: 12px; border-radius: 6px; overflow-x: auto; }}
        b {{ color: #ffffff; }}
        a {{ color: #29b6f6; }}
    </style>
</head>
<body>
    <h1>📡 {channel_title}</h1>
    <p class="stats">Auto-translated → English &nbsp;|&nbsp; {len(messages)} messages</p>
    {"".join(html_messages)}
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


async def process_channel(client, channel_id, limit, output_dir,
                          days=None, min_space_gb=1.0, max_video_mb=50,
                          forced_lang=None, skip_english=False, log_fn=None):
    from telethon.tl.types import (
        MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
    )

    def log(msg):
        if log_fn:
            log_fn(msg)
        print(msg)

    try:
        channel = await client.get_entity(channel_id)
    except Exception as e:
        log(f"[!] Could not access '{channel_id}': {e}")
        return

    channel_title = getattr(channel, "title", str(channel_id))
    safe_name = "".join(c if c.isalnum() else "_" for c in channel_title)

    channel_dir = output_dir / safe_name
    media_dir = channel_dir / "media"
    channel_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(exist_ok=True)

    cutoff_date = None
    if days:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        log(f"[i] Fetching since: {cutoff_date.strftime('%Y-%m-%d %H:%M UTC')} ({days} days back)")

    lang_mode = f"forced={forced_lang}" if forced_lang else "auto-detect"
    log(f"[+] Processing: {channel_title} | lang: {lang_mode}")

    results = []
    fetch_limit = None if limit == 0 else limit
    lang_stats = {}

    async for message in client.iter_messages(channel, limit=fetch_limit):
        if cutoff_date and message.date < cutoff_date:
            log("[i] Reached cutoff date. Stopping.")
            break

        free_gb = shutil.disk_usage(str(output_dir)).free / (1024 ** 3)
        if free_gb < min_space_gb:
            log(f"[✗] CRITICAL: Disk space dropped below {min_space_gb} GB ({free_gb:.2f} GB free). Stopping.")
            break

        entry = {
            "id":             message.id,
            "date":           message.date.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "original":       message.text or "",
            "translated_en":  "",
            "formatted_html": "",
            "detected_lang":  "unknown",
            "forced_lang":    forced_lang,
            "media_type":     None,
            "media_path":     None,
            "media_url":      None,
            "views":          getattr(message, "views", None),
            "forwards":       getattr(message, "forwards", None),
            "reply_to":       message.reply_to_msg_id if message.reply_to else None,
        }

        if message.text:
            if forced_lang:
                lang = forced_lang
            else:
                lang = detect_language(message.text)

            entry["detected_lang"] = lang
            entry["formatted_html"] = format_entities(message.text, message.entities)
            lang_stats[lang] = lang_stats.get(lang, 0) + 1

            if skip_english and lang == "en":
                entry["translated_en"] = message.text
            else:
                entry["translated_en"] = translate_text(message.text, lang)

        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                entry["media_type"] = "photo"
                try:
                    filename = media_dir / f"{message.id}.jpg"
                    await client.download_media(message, file=str(filename))
                    entry["media_path"] = f"media/{message.id}.jpg"
                    log(f"  [+] Photo: {filename.name}")
                except Exception as e:
                    log(f"  [!] Photo error: {e}")

            elif isinstance(message.media, MessageMediaDocument):
                doc = message.media.document
                mime = getattr(doc, "mime_type", "")

                if mime.startswith("image/"):
                    entry["media_type"] = "image_doc"
                    ext = mime.split("/")[-1]
                    try:
                        filename = media_dir / f"{message.id}.{ext}"
                        await client.download_media(message, file=str(filename))
                        entry["media_path"] = f"media/{message.id}.{ext}"
                    except Exception as e:
                        log(f"  [!] Image error: {e}")

                elif mime.startswith("video/"):
                    entry["media_type"] = "video"
                    ext = mime.split("/")[-1]
                    ext = "mp4" if ext in ("mp4", "mpeg4") else ext
                    file_size_mb = getattr(doc, "size", 0) / (1024 * 1024)

                    if max_video_mb == 0:
                        log("  [i] Video skipped (max_video_mb=0)")
                    elif file_size_mb > max_video_mb:
                        log(f"  [!] Video skipped — {file_size_mb:.1f} MB > limit {max_video_mb} MB")
                    else:
                        try:
                            filename = media_dir / f"{message.id}.{ext}"
                            log(f"  [~] Video ({file_size_mb:.1f} MB): {filename.name} ...")
                            await client.download_media(message, file=str(filename))
                            entry["media_path"] = f"media/{message.id}.{ext}"
                            log(f"  [+] Video saved: {filename.name}")
                        except Exception as e:
                            log(f"  [!] Video error: {e}")
                else:
                    entry["media_type"] = f"document ({mime})"

            elif isinstance(message.media, MessageMediaWebPage):
                wp = message.media.webpage
                entry["media_type"] = "webpage"
                entry["media_url"] = getattr(wp, "url", None)

        results.append(entry)
        lang_label = get_lang_display(entry["detected_lang"])
        log(f"  [MSG {message.id}] {entry['date']} | {lang_label} | {entry['media_type'] or 'text'}")

    json_path = channel_dir / "messages.json"
    html_path = channel_dir / "messages.html"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    generate_html(results, channel_title, html_path)

    log(f"[✓] {len(results)} messages saved → {channel_dir}/")
    if lang_stats:
        log("[i] Language breakdown:")
        for lang, count in sorted(lang_stats.items(), key=lambda x: -x[1]):
            log(f"     {get_lang_display(lang):<30} {count} messages")
    log("[✓] Scan complete.")

    return str(html_path)


# ── API Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/credentials", methods=["GET"])
def api_credentials():
    creds = _get_telegram_creds()
    configured = bool(creds["api_id"] and creds["api_hash"] and creds["phone"])
    return jsonify({
        "configured":   configured,
        "has_api_id":   bool(creds["api_id"]),
        "has_api_hash": bool(creds["api_hash"]),
        "has_phone":    bool(creds["phone"]),
    })


@app.route("/api/jobs", methods=["GET"])
def api_jobs_list():
    _load_jobs_index()  # always reload from disk so all workers see same state
    with _jobs_lock:
        jobs = []
        for jid, j in _jobs.items():
            jobs.append({
                "id":         jid,
                "status":     j["status"],
                "channel":    j["config"].get("channel", ""),
                "started_at": j["started_at"],
                "ended_at":   j.get("ended_at"),
                "log_lines":  len(j["log"]),
                "error":      j.get("error"),
            })
        jobs.sort(key=lambda x: x["started_at"], reverse=True)
    return jsonify(jobs)


@app.route("/api/jobs/<job_id>", methods=["GET"])
def api_job_get(job_id):
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "id":         job_id,
        "status":     j["status"],
        "channel":    j["config"].get("channel", ""),
        "config":     j["config"],
        "started_at": j["started_at"],
        "ended_at":   j.get("ended_at"),
        "log":        j["log"],
        "error":      j.get("error"),
    })


@app.route("/api/jobs/<job_id>/log", methods=["GET"])
def api_job_log(job_id):
    _load_jobs_index()
    since = int(request.args.get("since", 0))
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": j["status"],
        "log":    j["log"][since:],
        "total":  len(j["log"]),
    })


@app.route("/api/jobs/<job_id>/download", methods=["GET"])
def api_job_download(job_id):
    _load_jobs_index()
    with _jobs_lock:
        j = _jobs.get(job_id)
    if not j:
        return jsonify({"error": "Job not found"}), 404
    if j["status"] not in ("completed", "error"):
        return jsonify({"error": "Job still running"}), 400

    output_dir = Path(j["output_dir"])
    if not output_dir.exists():
        return jsonify({"error": "Output directory not found"}), 404

    channel = j["config"].get("channel", "channel").replace("/", "_").replace("@", "")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    zip_filename = f"channel_monitor_{channel}_{ts}.zip"
    files = sorted([f for f in output_dir.rglob("*") if f.is_file()])

    # Build the full ZIP in memory then send it in one shot.
    # The incremental streaming approach corrupts the ZIP central directory.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = str(fpath.relative_to(output_dir))
            zf.write(fpath, arcname)
    buf.seek(0)

    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"},
    )


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def api_job_delete(job_id):
    with _jobs_lock:
        j = _jobs.pop(job_id, None)
    if not j:
        return jsonify({"error": "Job not found"}), 404
    try:
        if j.get("output_dir"):
            shutil.rmtree(j["output_dir"], ignore_errors=True)
    except Exception:
        pass
    _save_jobs_index()
    return jsonify({"ok": True})


@app.route("/api/start", methods=["POST"])
def api_start():
    body = request.get_json() or {}

    channel = (body.get("channel") or "").strip().lstrip("@")
    if not channel:
        return jsonify({"error": "channel is required"}), 400

    creds = _get_telegram_creds()
    if not (creds["api_id"] and creds["api_hash"] and creds["phone"]):
        return jsonify({"error": "Telegram credentials not configured. Add TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE to your .env file."}), 400

    config = {
        "channel":      channel,
        "limit":        int(body.get("limit", 200)),
        "days":         int(body.get("days")) if body.get("days") else None,
        "lang":         (body.get("lang") or "").strip() or None,
        "max_video_mb": int(body.get("max_video_mb", 50)),
        "min_space_gb": float(body.get("min_space_gb", 1.0)),
        "skip_english": bool(body.get("skip_english", False)),
    }

    job_id = _new_job_id()
    output_dir = DATA_DIR / "jobs" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    job = {
        "status":     "running",
        "config":     config,
        "output_dir": str(output_dir),
        "started_at": datetime.utcnow().isoformat(),
        "ended_at":   None,
        "log":        [],
        "error":      None,
    }

    with _jobs_lock:
        _jobs[job_id] = job

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_job(job_id, config, output_dir, creds))
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(e)
                _jobs[job_id]["ended_at"] = datetime.utcnow().isoformat()
                _jobs[job_id]["log"].append(f"[✗] Fatal: {e}")
                _jobs[job_id]["log"].append(traceback.format_exc())
        finally:
            loop.close()

    threading.Thread(target=run, daemon=True, name=f"cm_{job_id}").start()
    return jsonify({"ok": True, "job_id": job_id})


async def _run_job(job_id, config, output_dir, creds):
    from telethon import TelegramClient

    def log(msg):
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["log"].append(msg)

    log(f"[+] Starting scan for: @{config['channel']}")
    log(f"[i] limit={config['limit']}, days={config['days']}, lang={config['lang']}, max_video={config['max_video_mb']}MB, skip_english={config['skip_english']}")

    try:
        client = TelegramClient(str(SESSION_FILE), int(creds["api_id"]), creds["api_hash"])
        await client.start(phone=creds["phone"])
        me = await client.get_me()
        log(f"[+] Connected as @{me.username or me.first_name}")
    except Exception as e:
        log(f"[✗] Telegram connection failed: {e}")
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["ended_at"] = datetime.utcnow().isoformat()
        return

    try:
        await process_channel(
            client=client,
            channel_id=config["channel"],
            limit=config["limit"],
            output_dir=output_dir,
            days=config["days"],
            min_space_gb=config["min_space_gb"],
            max_video_mb=config["max_video_mb"],
            forced_lang=config["lang"],
            skip_english=config["skip_english"],
            log_fn=log,
        )
        with _jobs_lock:
            _jobs[job_id]["status"] = "completed"
        log("[✓] Done. Click Download to get your results.")
        _save_jobs_index()
    except Exception as e:
        log(f"[✗] Error: {e}")
        log(traceback.format_exc())
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(e)
    finally:
        with _jobs_lock:
            _jobs[job_id]["ended_at"] = datetime.utcnow().isoformat()
        _save_jobs_index()
        try:
            await client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[+] Channel Monitor starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
