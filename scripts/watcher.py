import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparser
from dotenv import load_dotenv

# Load local .env if it exists
load_dotenv()

# ── config ──────────────────────────────────────────────────────────────────

GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
GH_PAT             = os.environ.get("GH_PAT")

SEEN_PATH   = "data/seen.json"
REPOS_PATH  = "repos.md"
CONFIG_PATH = "config.json"
BUFFER_PATH = "data/daily_buffer.json"

# ── helpers ──────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def load_seen():
    if not os.path.exists(SEEN_PATH):
        return {"seen_ids": [], "last_run": None}
    with open(SEEN_PATH) as f:
        return json.load(f)

def save_seen(seen):
    seen["last_run"] = datetime.now(timezone.utc).isoformat()
    with open(SEEN_PATH, "w") as f:
        json.dump(seen, f, indent=2)

def load_buffer():
    if not os.path.exists(BUFFER_PATH):
        return []
    with open(BUFFER_PATH) as f:
        try:
            return json.load(f)
        except:
            return []

def save_buffer(items):
    with open(BUFFER_PATH, "w") as f:
        json.dump(items, f, indent=2)

def parse_repos():
    """Extract owner/repo strings from repos.md"""
    repos = []
    if not os.path.exists(REPOS_PATH):
        return repos
    with open(REPOS_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("- "):
                repo = line[2:].strip()
                if "/" in repo:
                    repos.append(repo)
    return repos

# ── github fetching ──────────────────────────────────────────────────────────

def fetch_new_items(repo, since_iso, seen_ids):
    """
    Fetch issues and PRs from a repo opened since `since_iso`.
    Returns list of dicts with id, title, body, labels, url, type.
    """
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json"
    }
    params = {
        "state": "open",
        "since": since_iso,
        "per_page": 50
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        if response.status_code != 200:
            print(f"Warning: failed to fetch {repo} — {response.status_code}")
            return []

        items = []
        for item in response.json():
            if item["id"] in seen_ids:
                continue
            items.append({
                "id": item["id"],
                "number": item["number"],
                "title": item["title"],
                "body": (item.get("body") or "")[:300],
                "labels": [l["name"] for l in item.get("labels", [])],
                "url": item["html_url"],
                "repo": repo,
                "type": "pr" if "pull_request" in item else "issue"
            })
        return items
    except Exception as e:
        print(f"Error fetching {repo}: {e}")
        return []

# ── ai scoring ───────────────────────────────────────────────────────────────

def score_items(items, skills, config):
    """
    Send all items to Gemma 4 in one batch call.
    Returns list of scored dicts.
    """
    if not items:
        return []

    # build a clean list for the prompt (no noise)
    prompt_items = [
        {
            "id": item["id"],
            "title": item["title"],
            "body": item["body"],
            "labels": item["labels"],
            "type": item["type"]
        }
        for item in items
    ]

    prompt = f"""You are helping a computer engineering student find great open source 
contribution opportunities for Google Summer of Code.

Score each item from 0 to 100 based on this matrix:
1. Skill Match (Max 40 pts): How well does it align with: {", ".join(skills)}?
2. Scope & Doability (Max 30 pts): Is it suitable for a student? Not too big, but not a 5-minute typo fix.
3. Clarity (Max 20 pts): Is the issue well-described with clear reproduction steps or goals?
4. Signal (Max 10 pts): Does it have "good first issue" or "help wanted" labels?

Items:
{json.dumps(prompt_items, indent=2)}

Respond ONLY with a valid JSON array, no markdown fences, no explanation:
[
  {{
    "id": <same id from input>,
    "score": <0-100>,
    "reason": "<one sentence explanation of the score breakdown>",
    "skills_needed": ["skill1", "skill2"],
    "good_first_issue": <true or false>
  }}
]"""

    model = "gemma-4-31b-it"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(3):
        resp = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if resp.status_code == 429:
            print("Rate limited, waiting 60s...")
            time.sleep(60)
            continue
        if resp.status_code == 200:
            break
        print(f"Gemini error {resp.status_code}: {resp.text}")
        return []

    try:
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        scores = json.loads(raw)
    except Exception as e:
        print(f"Failed to parse Gemini response: {e}")
        print(f"Raw response from AI: {resp.text[:500]}...") # Print the first 500 chars of the error
        return []

    # merge scores back into original items
    score_map = {s["id"]: s for s in scores}
    result = []
    for item in items:
        if item["id"] in score_map:
            item.update(score_map[item["id"]])
            result.append(item)
    return result

# ── filtering ────────────────────────────────────────────────────────────────

def filter_and_rank(scored_items, config):
    threshold = config["score_threshold"]
    top_n = config["top_n_per_run"]
    always_top = config["always_send_top_n"]

    sorted_items = sorted(scored_items, key=lambda x: x.get("score", 0), reverse=True)

    top_3 = sorted_items[:always_top]
    above_threshold = [x for x in sorted_items if x.get("score", 0) >= threshold]

    # merge without duplicates, preserve order
    seen_ids = set()
    combined = []
    for item in top_3 + above_threshold:
        if item["id"] not in seen_ids:
            combined.append(item)
            seen_ids.add(item["id"])

    return combined[:top_n]

# ── telegram ─────────────────────────────────────────────────────────────────

def format_message(items, title=None):
    # Convert UTC to EDT (UTC-4)
    now = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d %I:%M %p EDT")
    
    if not title:
        title = f"🔍 *Crontrib* — {len(items)} new match{'es' if len(items) != 1 else ''}"
    
    lines = [f"{title}\n"]

    for i, item in enumerate(items, 1):
        score = item.get("score", "?")
        gfi = "✅ `good-first-issue`" if item.get("good_first_issue") else ""
        skills = ", ".join(item.get("skills_needed", []))
        item_type = "PR" if item["type"] == "pr" else "Issue"

        lines.append(
            f"{i}. ⭐ *{score}/100* {gfi}\n"
            f"*{item['title']}*\n"
            f"📂 `{item['repo']}` — #{item['number']} ({item_type})\n"
            f"🛠 {skills}\n"
            f"💡 {item.get('reason', '')}\n"
            f"🔗 {item['url']}\n"
        )

    lines.append(f"_ran at {now}_")
    return "\n".join(lines)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"Telegram error: {resp.text}")
    except Exception as e:
        print(f"Error sending Telegram: {e}")

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if not all([GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GH_PAT]):
        print("Error: Missing required environment variables.")
        return

    config = load_config()
    seen = load_seen()
    seen_ids = set(seen.get("seen_ids", []))

    repos = parse_repos()
    since = (datetime.now(timezone.utc) - timedelta(hours=config["lookback_hours"])).isoformat()

    print(f"Watching {len(repos)} repos since {since}")

    all_new_items = []
    for repo in repos:
        items = fetch_new_items(repo, since, seen_ids)
        print(f"  {repo}: {len(items)} new items")
        all_new_items.extend(items)

    print(f"Total new unseen items: {len(all_new_items)}")

    if not all_new_items:
        print("Nothing new. Exiting.")
        save_seen(seen)
        return

    # Process in batches to avoid Gemini prompt size limits or timeouts
    batch_size = config.get("batch_size", 50)

    # Process in batches
    all_scored = []
    for i in range(0, len(all_new_items), batch_size):
        batch = all_new_items[i:i+batch_size]
        print(f"Scoring batch {i//batch_size + 1} ({len(batch)} items)...")
        scored_batch = score_items(batch, config["skills"], config)
        all_scored.extend(scored_batch)

    # 1. Update Daily Buffer
    buffer = load_buffer()
    buffer.extend(all_scored)
    
    # 2. Logic: Immediate Alert for high-score items found in THIS run
    urgent_items = [x for x in all_scored if x.get("score", 0) >= config["score_threshold"]]
    if urgent_items:
        print(f"Found {len(urgent_items)} urgent items. Sending instant alert.")
        msg = format_message(urgent_items, title="🚨 *Crontrib High-Signal Alert*")
        send_telegram(msg)
        
    # 3. Logic: Daily Digest at 6 AM EDT (10 AM UTC)
    current_hour_utc = datetime.now(timezone.utc).hour
    if current_hour_utc == config.get("digest_hour_utc", 10):
        print("Scheduled Digest Time (6 AM EDT). Sending daily top 10.")
        # Rank the entire buffer by score
        top_10_daily = sorted(buffer, key=lambda x: x.get("score", 0), reverse=True)[:10]
        if top_10_daily:
            msg = format_message(top_10_daily, title="☕ *Your Morning Contrib Digest*")
            send_telegram(msg)
        # Clear buffer after sending the morning digest
        buffer = []
        
    save_buffer(buffer)

    # update seen with ALL processed IDs regardless of score
    new_ids = [item["id"] for item in all_new_items]
    seen["seen_ids"] = list(seen_ids | set(new_ids))
    save_seen(seen)

    print("Done.")

if __name__ == "__main__":
    main()
