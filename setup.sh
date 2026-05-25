#!/bin/bash
set -e

echo "🏠 Setting up Archie..."

# Python deps
python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

# Config
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Edit .env before starting:"
    echo "    nano .env"
    exit 0
fi

# Systemd service
mkdir -p ~/.config/systemd/user
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sed "s|/home/tim/home-bot|$SCRIPT_DIR|g; s|/home/tim|$HOME|g; s|User=tim|User=$USER|g" \
    archie.service > ~/.config/systemd/user/archie.service

systemctl --user daemon-reload
systemctl --user enable archie
sudo loginctl enable-linger "$USER"

echo ""
echo "✅ Done. Start with:"
echo "   systemctl --user start archie"
echo "   journalctl --user -u archie -f"
