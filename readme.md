Archie 🏠
A self-hosted home and family knowledge base powered by Discord. Store and retrieve anything about your home — appliance models, filter sizes, family preferences, gift ideas, paint colors, and more.
What it does
Talk to Archie in Discord like a person:
"My washer is an LG WM6500HBA in the laundry room"
"My wife Sarah loves tulips but hates carnations"
"The upstairs HVAC filter is 16x25x1"
Then ask questions:
"What appliances do I have?"
"What are all my LG products?"
"What should I get my wife for her birthday?"
"What's in the laundry room?"
Archie reasons across all stored entries to answer — asking about a room returns everything in it, asking about a brand returns every item with that brand.
Features
Multi-provider LLM — swap between Gemini, Claude, OpenAI, or local Ollama via one .env line
Persistent JSON database — stored locally on your machine, never in the repo
Smart deduplication — Python-side filtering before LLM calls
Discord commands — !reset, !status, !dump, !list
Runs as a systemd service — survives reboots, auto-restarts on failure
Raspberry Pi friendly — runs headlessly on Pi 4 with a cloud LLM provider
Requirements
Python 3.11+
A Discord bot token (discord.com/developers)
An API key for your chosen LLM provider (or local Ollama)
Setup
1. Clone and install
Bash
2. Configure
Bash
Fill in your Discord token, allowed user ID, and LLM provider key.
3. Discord Developer Portal
Go to discord.com/developers/applications
Create a new application → Bot → Reset Token → copy it
Enable Message Content Intent under Privileged Gateway Intents
OAuth2 → URL Generator → scope: bot → permissions: Send Messages, Read Messages, Read Message History
Use the generated URL to invite the bot to your server
Enable Developer Mode in Discord settings → right-click your username → Copy User ID
4. Run
Bash
LLM Providers
Provider
Free Tier
Set LLM_PROVIDER=
Gemini
Yes — generous free tier
gemini
Claude
No — pay per use, very cheap
claude
OpenAI
No — pay per use
openai
Ollama
Yes — fully local
ollama
Recommended: Gemini for free usage, Claude Haiku for best reasoning per dollar.
For Gemini, get a free API key at aistudio.google.com.
Commands
Command
Description
!status
Show number of entries in database
!dump
Print raw database contents
!reset
Clear the entire database
Running on Raspberry Pi
Works on Pi 4 with any cloud LLM provider. Local Ollama models are too slow for real-time chat on Pi hardware — use a cloud provider and keep Ollama as a fallback option.
Project structure
Code

