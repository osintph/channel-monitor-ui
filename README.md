# 📡 Channel Monitor — Standalone

A self-contained web app for monitoring Telegram channels with **auto-translation**, **media download**, and a **live log UI**.

## ✨ Features

- 🌐 Auto-translates messages to English (Farsi, Russian, Chinese, Arabic, Korean, Ukrainian + more)
- 📸 Downloads photos and videos from channels
- 🔗 Preserves message formatting (bold, links, mentions, hashtags)
- 📊 Language breakdown stats per channel
- 💾 Exports results as a self-contained ZIP (HTML + JSON + media)
- 🖥️ Live log streaming in the browser
- ⚡ Multiple concurrent scan jobs
- 🗂️ Full job history with download/delete

---

## 🚀 One-Click Install

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/channel-monitor.git
cd channel-monitor

# Install + configure
bash install.sh

# Run
bash run.sh
```

Then open **http://localhost:5000** in your browser.

---

## ⚙️ Manual Setup

### 1. Get Telegram API credentials

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click **API development tools**
4. Create a new application → copy `api_id` and `api_hash`

### 2. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in:
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+15551234567
```

### 3. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run

```bash
python app.py
```

Open **http://localhost:5000**

---

## 📖 Usage

1. Enter a channel username (e.g. `irna_1931`) or full link (e.g. `t.me/channel`)
2. Set your options:
   - **Message Limit** — how many messages to fetch (0 = all)
   - **Days Back** — only fetch messages from the last N days
   - **Force Language** — skip auto-detect and use a specific source language
   - **Max Video Size** — skip videos above this MB threshold
   - **Min Free Disk** — stop if disk space drops below this
   - **Skip English** — don't re-translate already-English messages
3. Click **▶ Start Scan**
4. Watch the live log; click **⬇ Download** when done

The ZIP contains:
- `messages.html` — self-contained readable report with translations
- `messages.json` — raw data with all fields
- `media/` — downloaded photos and videos

---

## 🔧 Configuration

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_API_ID` | — | Required. From my.telegram.org |
| `TELEGRAM_API_HASH` | — | Required. From my.telegram.org |
| `TELEGRAM_PHONE` | — | Required. Your phone number |
| `PORT` | `5000` | Web server port |
| `DATA_DIR` | `data` | Where jobs and session files are stored |
| `SECRET_KEY` | random | Flask session secret |

---

## 📦 Dependencies

- [Telethon](https://github.com/LonamiWebs/Telethon) — Telegram MTProto client
- [deep-translator](https://github.com/nidhaloff/deep-translator) — Google Translate wrapper
- [langdetect](https://github.com/Mimino666/langdetect) — Language detection
- [Flask](https://flask.palletsprojects.com/) — Web framework

---

## 📝 Notes

- On first run, Telegram will send a verification code to your phone/app. Enter it in the terminal.
- The session is saved to `data/channel_monitor.session` — keep this file private.
- All job output is stored in `data/jobs/` and can be downloaded as a ZIP via the UI.
