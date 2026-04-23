#!/bin/bash

# 🔍 Crontrib Setup Wizard
# This script helps you configure Crontrib and sync secrets to GitHub automatically.

echo "=========================================="
echo "   🔍 Welcome to the Crontrib Setup"
echo "=========================================="

# 1. Check for Dependencies
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed."
    echo "Please install it from: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo "❌ Error: You are not logged into GitHub CLI."
    echo "Please run: gh auth login"
    exit 1
fi

# 2. Collect Credentials
echo "--- Step 1: API Credentials ---"
read -p "Enter your Gemini API Key: " GEMINI_KEY
read -p "Enter your Telegram Bot Token: " TG_TOKEN
read -p "Enter your Telegram Chat ID: " TG_ID
read -p "Enter your GitHub PAT (with repo/write scopes): " GH_TOKEN

# 3. Save to local .env (optional for local testing)
echo "--- Step 2: Local Configuration ---"
cat <<EOF > .env
GEMINI_API_KEY=$GEMINI_KEY
TELEGRAM_BOT_TOKEN=$TG_TOKEN
TELEGRAM_CHAT_ID=$TG_ID
GH_PAT=$GH_TOKEN
EOF
echo "✅ Created .env for local use."

# 4. Upload Secrets to GitHub
echo "--- Step 3: Syncing Secrets to GitHub ---"
echo "Uploading GEMINI_API_KEY..."
gh secret set GEMINI_API_KEY --body "$GEMINI_KEY"
echo "Uploading TELEGRAM_BOT_TOKEN..."
gh secret set TELEGRAM_BOT_TOKEN --body "$TG_TOKEN"
echo "Uploading TELEGRAM_CHAT_ID..."
gh secret set TELEGRAM_CHAT_ID --body "$TG_ID"
echo "Uploading GH_PAT..."
gh secret set GH_PAT --body "$GH_TOKEN"

# 5. Initialize Data
echo "--- Step 4: Initializing State ---"
mkdir -p data
if [ ! -f data/seen.json ]; then
    echo '{"seen_ids": [], "last_run": null}' > data/seen.json
fi
if [ ! -f data/daily_buffer.json ]; then
    echo '[]' > data/daily_buffer.json
fi

echo "=========================================="
echo "🎉 Setup Complete!"
echo "=========================================="
echo "1. Edit repos.md to add your favorite repositories."
echo "2. Edit config.json to customize your skills."
echo "3. Run 'git add . && git commit -m \"initial setup\" && git push' to start!"
echo "=========================================="
