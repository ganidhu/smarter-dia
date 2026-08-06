# smarter-dia

A clean, modular CLI tool to unlock and supercharge Dia AI Browser's agent capabilities. Inspired by the clean project structure of `sprite-separator`.

> ⚠️ **WARNING**: This tool is **NOT an official product of TheBrowserCompany**. It modifies Dia's internals (sandbox profiles, prompts, skills, signing state). Use at your own risk — the authors are not responsible for any damage to your browser.

## Features
- **Sandbox Unlock**: Unlocks macOS Seatbelt profiles (`agent-claude-code.sb` & `agent.sb`).
- **PATH Auto-Fix**: Automatically symlinks system binaries (`yt-dlp`, `ffmpeg`, `node`, `python3`, `git`, `bun`, `uv`) to `/usr/local/bin`.
- **Skills Sync**: Syncs all 28+ AGY skills from `~/.agents/skills` directly into Dia's agent resources (protecting original Dia skills).
- **Prompt & Path Append**: Appends `/Users/ganidhu` home path rules and `AGENTS.md` persona to Dia's `chat-base.md` system prompt safely without overwriting anything.
- **Auto-Backup**: Every action snapshots the state it is about to touch into `~/.smarter-dia/backups/` — outside the app bundle, so the code seal isn't broken by backup files.
- **Restore**: Roll back any change from the CLI, then re-verifies Dia's code signature.
- **Signature & Keychain Checks**: `status` and `verify` report whether Dia's code seal is intact and the login keychain is unlocked.
- **Keychain Safety**: No longer runs `set-key-partition-list` with an empty password (that's what locked the keychain and broke profile loading).

## Installation
Run from inside this directory:
```bash
./install.sh
```

## Usage
Run from anywhere in your terminal:
```bash
smarter-dia status
smarter-dia backup
smarter-dia supercharge
smarter-dia restore
smarter-dia verify
sudo smarter-dia append-prompt
```
