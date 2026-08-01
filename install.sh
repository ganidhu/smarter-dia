#!/bin/bash
set -e

GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}${CYAN}┌────────────────────────────────────────────────────────┐${RESET}"
echo -e "${BOLD}${CYAN}│               Smarter-Dia CLI Installer                │${RESET}"
echo -e "${BOLD}${CYAN}│       Dia AI Intelligence & Sandbox Supercharger       │${RESET}"
echo -e "${BOLD}${CYAN}└────────────────────────────────────────────────────────┘${RESET}"
echo

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 &> /dev/null; then
    echo -e "  ${RED}Error: Python 3 is required but not found.${RESET}"
    exit 1
fi

if command -v pipx &> /dev/null; then
    echo -e "  ${CYAN}Installing via pipx (isolated environment)…${RESET}"
    pipx install "$SCRIPT_DIR" --force
elif command -v pip3 &> /dev/null; then
    echo -e "  ${CYAN}Installing via pip3…${RESET}"
    pip3 install -e "$SCRIPT_DIR" --break-system-packages
else
    echo -e "  ${RED}Error: Neither pipx nor pip3 found.${RESET}"
    exit 1
fi

echo
if command -v smarter-dia &> /dev/null; then
    echo -e "  ${BOLD}${GREEN}✓ Installed! Run from any terminal:${RESET}"
    echo -e "  ${BOLD}${YELLOW}smarter-dia${RESET}                  — status dashboard"
    echo -e "  ${BOLD}${YELLOW}sudo smarter-dia supercharge${RESET}  — full upgrade"
else
    echo -e "  ${YELLOW}Installed but not on PATH yet. Ensure pipx/pip scripts dir is in PATH.${RESET}"
fi
echo
