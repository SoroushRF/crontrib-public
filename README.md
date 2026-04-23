# 🔍 Crontrib

**Crontrib** is an automated open-source contribution watcher. It scans a curated list of GitHub repositories every hour, scores new issues and PRs using Google Gemini AI, and delivers a ranked intelligence digest directly to your Telegram.

Designed for students and developers hunting for high-quality contribution opportunities (like GSoC), Crontrib eliminates manual repo browsing and surfaces the most relevant tasks based on your specific skills.

---

## 🚀 Features

- **Hourly Intelligence**: Automatically monitors multiple repositories every hour via GitHub Actions.
- **AI-Powered Scoring**: Uses Google Gemini to rank tasks from 1–10 based on complexity, relevance, and "good first issue" status.
- **🚨 High-Signal Alerts**: Instant Telegram notifications for "perfect match" items (Score 9+).
- **☕ Daily Morning Digest**: A ranked "Top 10" summary of all findings from the last 24 hours delivered at 6:00 AM EDT.
- **Skill-Based Filtering**: Highly customizable scoring criteria based on your specific tech stack.
- **Zero Maintenance**: Runs entirely on GitHub Actions with no server to manage.

---

## 🛠 Setup

### 1. Repository Configuration
- Add your target repositories to `repos.md` (one `owner/repo` per line).
- Customize your skills and thresholds in `config.json`.

### 2. GitHub Secrets
Add the following secrets to your repository (**Settings > Secrets and variables > Actions**):

| Secret | Description |
| --- | --- |
| `GEMINI_API_KEY` | Your Google AI Studio API key. |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather. |
| `TELEGRAM_CHAT_ID` | Your Telegram user/group ID. |
| `GH_PAT` | Personal Access Token with `contents: write` and `actions: write` permissions. |

---

## 📁 Project Structure

- `.github/workflows/watcher.yml`: The automation engine.
- `scripts/watcher.py`: The core logic (fetching, scoring, notifying).
- `data/seen.json`: Persistent state to prevent duplicate alerts.
- `data/daily_buffer.json`: Stores issues for the 24-hour digest.
- `config.json`: AI parameters and notification schedule.
- `repos.md`: Your curated watch list.

---

## ⚙️ Configuration (`config.json`)

```json
{
  "score_threshold": 9,      // Threshold for instant alerts
  "lookback_hours": 1,       // How far back to scan each hour
  "digest_hour_utc": 10,     // 10 AM UTC = 6 AM EDT
  "skills": ["Python", ...]  // Keywords for AI scoring
}
```

---

## 📜 License
MIT
