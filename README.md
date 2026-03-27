# 📡 Channel Monitor

A standalone web app for monitoring Telegram channels with **auto-translation to English**, **media download**, and a **live log UI**.

Built by [@osintph](https://github.com/osintph)

---

## ✨ Features

- 🌐 Auto-translates messages to English (Farsi, Russian, Chinese, Arabic, Korean, Ukrainian + more)
- 📸 Downloads photos and videos from channels
- 🔗 Preserves message formatting (bold, links, mentions, hashtags)
- 📊 Language breakdown stats per scan
- 💾 Exports results as a ZIP (HTML report + JSON + media files)
- 🖥️ Live log streaming in the browser
- ⚡ Multiple concurrent scan jobs
- 🗂️ Full job history — persists across restarts
- 🔁 Runs as a background systemd service
- 🔍 Keyword scan mode — only saves messages (and their media) that match your keywords
- 🗂️ In-app archive search — full-text search across all completed scans, original and translated

---

## 🚀 Installation

### Step 1 — Get Telegram API credentials

Before anything else, you need API credentials from Telegram:

1. Go to **https://my.telegram.org**
2. Log in with your phone number
3. Click **API development tools**
4. Create a new application
5. Copy your **`api_id`** and **`api_hash`**

### Step 2 — Clone the repo

```bash
git clone https://github.com/osintph/channel-monitor-ui.git
cd channel-monitor-ui
```

### Step 3 — Configure your credentials

Copy the example env file and fill in your details **before running the installer**:

```bash
cp .env.example .env
nano .env
```

Fill in all three required fields:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+15551234567
```

Save and exit (`Ctrl+X` → `Y` → `Enter`).

> ⚠️ The installer will hard-stop if these are not filled in. You must complete this step before running `install.sh`.

### Step 4 — Run the installer

```bash
bash install.sh
```

The installer will:
1. Check Python version (3.10+ required)
2. Create a virtual environment in `.venv/`
3. Install all Python dependencies
4. Validate your `.env` credentials
5. Authenticate with Telegram — **Telegram will send a login code to your phone or app, enter it when prompted**

The session is saved to `data/channel_monitor.session` and reused on every future run — you will not need to authenticate again unless you delete the session file.

### Step 5 — Run

**Option A — Run manually in the foreground:**
```bash
bash run.sh
```

**Option B — Install as a background service (recommended):**
```bash
sudo bash install-service.sh
```

The service starts automatically on boot and runs in the background using Gunicorn.

Then open your browser at:
- **http://localhost:5000**
- **http://YOUR-HOSTNAME:5000**
- **http://YOUR-IP:5000**

---

## 🔧 Managing the service

```bash
sudo systemctl status channel-monitor     # check if running
sudo systemctl restart channel-monitor    # restart
sudo systemctl stop channel-monitor       # stop
sudo systemctl start channel-monitor      # start
sudo journalctl -u channel-monitor -f     # live logs
```

---

## ⚙️ Configuration

All settings live in `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_API_ID` | ✅ | — | From my.telegram.org |
| `TELEGRAM_API_HASH` | ✅ | — | From my.telegram.org |
| `TELEGRAM_PHONE` | ✅ | — | Your phone number e.g. +15551234567 |
| `PORT` | No | `5000` | Web server port |
| `DATA_DIR` | No | `data` | Where jobs and session files are stored |
| `SECRET_KEY` | No | random | Flask session secret |

---

## 📖 Usage

The UI has three modes, selectable via the tab bar on the left panel.

### 📡 Full Scan

Downloads all messages from a channel (up to your configured limit), translates them, and saves everything.

1. Enter a channel username (e.g. `farsna`) or full link (e.g. `t.me/farsna`)
2. Configure scan options:
   - **Message Limit** — number of messages to fetch (0 = all)
   - **Days Back** — only fetch messages from the last N days (leave blank for all)
   - **Force Language** — skip auto-detect and force a specific source language
   - **Max Video Size (MB)** — skip videos larger than this (0 = skip all videos)
   - **Min Free Disk (GB)** — stop downloading if disk space drops below this
   - **Skip translation if already English** — avoids unnecessary API calls
3. Click **▶ Start Scan**
4. Watch the live log in real time
5. Click **⬇ ZIP** to download results when complete

### 🔍 Keyword Scan

Scans the full channel history but only saves messages — and their attached media — that contain at least one of your keywords. Non-matching messages are counted in the log but never written to disk, so the output ZIP contains only relevant content.

Keyword matching checks both the **original text** and the **English translation**, so you can search a Farsi or Russian channel using English keywords and still get matches.

1. Enter a channel username or link
2. Type keywords into the tag box and press **Enter** or **,** after each one — click **×** to remove
3. Configure the same options as Full Scan (limit 0 = scan the entire channel history)
4. Click **🔍 Start Keyword Scan**
5. The live log shows a summary at the end:
   ```
   [i] Keyword filter: 1,243 messages skipped (did not match: missile, strike)
   [✓] 17 messages saved
   ```
6. Click **⬇ ZIP** to download — the ZIP contains only the matching messages and their media

Completed keyword scan jobs show their keyword tags in the job history panel so you can tell them apart at a glance.

### 🗂 Search Archive

Searches across all completed scan archives without opening any ZIP files. Matches against both the original text and the English translation, so you can query foreign-language archives in English.

- Search is **AND logic** — all terms must appear in the message (`missile strike` only matches messages containing both words)
- Use the channel dropdown to narrow results to a specific channel
- Each result shows a highlighted excerpt, language, media type, and view count
- Click **Show full message** to expand the original text and full translation inline
- Direct links to download the job ZIP or view the job log are shown per result

### What's in the ZIP

| File | Description |
|---|---|
| `messages.html` | Self-contained report — original text, English translation, inline photos/videos |
| `messages.json` | Raw data with all fields |
| `media/` | Downloaded photos and videos (keyword scan: only media from matching messages) |

---

## 🔄 Re-authenticating Telegram

If you need to log in again (e.g. session expired or phone changed):

```bash
rm data/channel_monitor.session
bash install.sh
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| [Telethon](https://github.com/LonamiWebs/Telethon) | Telegram MTProto client |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | Google Translate wrapper |
| [langdetect](https://github.com/Mimino666/langdetect) | Automatic language detection |
| [Flask](https://flask.palletsprojects.com/) | Web framework |
| [Gunicorn](https://gunicorn.org/) | Production WSGI server |

---

## 📝 Notes

- `data/channel_monitor.session` grants access to your Telegram account — keep it private and never commit it to git
- `data/` is in `.gitignore` and will never be committed
- Job history persists across service restarts in `data/jobs_index.json`
- The service runs with a single Gunicorn worker to avoid Telegram session conflicts
