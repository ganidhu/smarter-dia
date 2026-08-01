# smarter-dia

A clean, modular CLI tool to unlock and supercharge Dia AI Browser's agent capabilities. Inspired by the clean project structure of `sprite-separator`.

## Features
- **Sandbox Unlock**: Unlocks macOS Seatbelt profiles (`agent-claude-code.sb` & `agent.sb`).
- **PATH Auto-Fix**: Automatically symlinks system binaries (`yt-dlp`, `ffmpeg`, `node`, `python3`, `git`, `bun`, `uv`) to `/usr/local/bin`.
- **Skills Sync**: Syncs all 28+ AGY skills from `~/.agents/skills` directly into Dia's agent resources.
- **Prompt & Path Append**: Appends `/Users/ganidhu` home path rules and `AGENTS.md` persona to Dia's `chat-base.md` system prompt safely without overwriting anything.

## Installation
Run from inside this directory:
```bash
./install.sh
```

## Usage
Run from anywhere in your terminal:
```bash
smarter-dia status
smarter-dia supercharge
sudo smarter-dia append-prompt
```
