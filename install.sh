#!/bin/bash
set -e

GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}${GREEN}┌────────────────────────────────────────────────────────┐${RESET}"
echo -e "${BOLD}${GREEN}│               Smarter-Dia CLI Installer                │${RESET}"
echo -e "${BOLD}${GREEN}└────────────────────────────────────────────────────────┘${RESET}"
echo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_BIN="$HOME/.local/bin/smarter-dia"

mkdir -p "$HOME/.local/bin"
cp "$SCRIPT_DIR/smarter-dia" "$TARGET_BIN"
chmod +x "$TARGET_BIN"

echo -e "  ${GREEN}✓ Installed smarter-dia to $TARGET_BIN${RESET}"

if command -v smarter-dia &> /dev/null; then
    echo -e "  ${BOLD}${GREEN}✓ Ready! Run anywhere:${RESET}"
    echo -e "  ${BOLD}${YELLOW}smarter-dia status${RESET}"
    echo -e "  ${BOLD}${YELLOW}smarter-dia supercharge${RESET}"
else
    echo -e "  ${YELLOW}Note: Ensure ~/.local/bin is in your PATH.${RESET}"
fi
echo
