#!/bin/bash
set -e

echo "Installing Archie..."

mkdir -p ~/home-bot
cp bot.py ~/home-bot/
cp requirements.txt ~/home-bot/

# Only copy .env if one doesn't already exist
if [ ! -f ~/home-bot/.env ]; then
    cp .env ~/home-bot/.env
    echo "Edit ~/home-bot/.env before starting."
fi

cd ~/home-bot
python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/archie.service << SERVICE
[Unit]
Description=Archie Home Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/$USER/home-bot
EnvironmentFile=/home/$USER/home-bot/.env
ExecStart=/home/$USER/home-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable archie
sudo loginctl enable-linger "$USER"

echo ""
echo "Done. Next:"
echo "  1. nano ~/home-bot/.env  (add your keys)"
echo "  2. systemctl --user start archie"
echo "  3. journalctl --user -u archie -f"
