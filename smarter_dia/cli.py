"""
smarter_dia/cli.py
Pure UX layer — all display, prompts, and flow.
Never calls sys directly; always calls engine functions.
"""

from __future__ import annotations

import sys
import time
from typing import Optional

from smarter_dia import __version__
from smarter_dia.engine import (
    ActionResult,
    CheckResult,
    append_prompt_rules,
    check_status,
    fix_path_links,
    restore_defaults,
    sync_skills,
    unlock_sandbox,
)

# ─── Terminal styling ──────────────────────────────────────────────────────────

CLEAR  = "\033[2J\033[H"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
RED    = "\033[31m"
MAGENTA= "\033[35m"

CMD = "smarter-dia"

# ─── UI Primitives ────────────────────────────────────────────────────────────

def banner(subtitle: str = "") -> None:
    title = f"SMARTER·DIA  v{__version__}  {subtitle}".strip()
    pad = max(0, 54 - len(title))
    print(f"{BOLD}{CYAN}┌────────────────────────────────────────────────────────┐{RESET}")
    print(f"{BOLD}{CYAN}│  {title}{' ' * pad}│{RESET}")
    print(f"{BOLD}{CYAN}│  Dia AI Intelligence & Sandbox Supercharger{' ' * 13}│{RESET}")
    print(f"{BOLD}{CYAN}└────────────────────────────────────────────────────────┘{RESET}")
    print()


def tick(label: str, ok: bool, detail: str = "") -> None:
    icon = f"{GREEN}✔{RESET}" if ok else f"{YELLOW}⚠{RESET}"
    print(f"  {icon}  {label}", end="")
    if detail:
        print(f"  {DIM}{detail}{RESET}", end="")
    print()


def step(n: int, total: int, label: str) -> None:
    print(f"\n  {BOLD}{CYAN}STEP {n} of {total}{RESET}  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {label}\n")


def loader(label: str, frames=("✻", "✳", "·"), loops: int = 2, delay: float = 0.07) -> None:
    for _ in range(loops):
        for ch in frames:
            print(f"\r  {CYAN}{ch}{RESET}  {label}", end="", flush=True)
            time.sleep(delay)


def show_result(r: ActionResult) -> None:
    if r.ok:
        print(f"  {GREEN}✔  {r.message}{RESET}")
    else:
        print(f"  {RED}✘  {r.message}{RESET}")
    if r.detail:
        for line in r.detail.splitlines():
            print(f"     {DIM}{line}{RESET}")


def prompt_choice(prompt: str, options: dict[str, str]) -> str:
    for key, label in options.items():
        print(f"    {BOLD}[{key}]{RESET}  {label}")
    print()
    while True:
        choice = input(f"  {prompt}: ").strip().lower()
        if choice in options:
            return choice
        print(f"  {RED}Pick one of: {', '.join(options)}{RESET}")

# ─── Status dashboard ─────────────────────────────────────────────────────────

def cmd_status() -> None:
    print(CLEAR)
    banner("· status")

    r = check_status()

    print(f"  {BOLD}[ 1 ]  Sandbox{RESET}")
    tick("agent-claude-code.sb   exec unlock", r.sandbox_cc_unlocked,
         "full shell" if r.sandbox_cc_unlocked else "RESTRICTED")
    tick("agent.sb               server unlock", r.sandbox_as_unlocked,
         "full exec" if r.sandbox_as_unlocked else "RESTRICTED")
    tick("sandbox-constraints.md prompt unlock", r.prompt_unlocked,
         "open" if r.prompt_unlocked else "blocked")

    print(f"\n  {BOLD}[ 2 ]  Prompt Appends{RESET}")
    tick("/Users/ganidhu path override", r.path_override_injected)
    tick("AGENTS.md persona injected", r.persona_injected)

    print(f"\n  {BOLD}[ 3 ]  AGY Skills in Dia{RESET}")
    print(f"      {GREEN}{r.skills_count} skill directories active{RESET}")

    print(f"\n  {BOLD}[ 4 ]  Binary PATH Links{RESET}")
    for name, path in r.binaries.items():
        tick(f"{name:<12}", bool(path), path or "not found")

    print()

# ─── Individual action commands ───────────────────────────────────────────────

def cmd_unlock() -> None:
    print(CLEAR)
    banner("· unlock")
    loader("Patching Seatbelt sandbox profiles…")
    print()
    show_result(unlock_sandbox())
    print()


def cmd_fix_path() -> None:
    print(CLEAR)
    banner("· fix-path")
    loader("Scanning and linking binaries…")
    print()
    show_result(fix_path_links())
    print()


def cmd_sync_skills() -> None:
    print(CLEAR)
    banner("· sync-skills")
    loader("Copying AGY skills into Dia…", loops=3)
    print()
    show_result(sync_skills())
    print()


def cmd_append_prompt() -> None:
    print(CLEAR)
    banner("· append-prompt")
    loader("Appending rules to chat-base.md…")
    print()
    show_result(append_prompt_rules())
    print()


def cmd_restore() -> None:
    print(CLEAR)
    banner("· restore")
    confirm = input(f"  {YELLOW}Restore original Dia sandbox defaults? [y/N]: {RESET}").strip().lower()
    if confirm != "y":
        print(f"  {DIM}Cancelled.{RESET}\n")
        return
    show_result(restore_defaults())
    print()

# ─── Interactive supercharge pipeline ─────────────────────────────────────────

def cmd_supercharge() -> None:
    """Guided step-by-step full supercharge experience."""
    print(CLEAR)
    banner()

    step(1, 4, "Unlock Dia's Seatbelt sandbox (requires sudo)")
    loader("Patching sandbox profiles…")
    print()
    show_result(unlock_sandbox())

    step(2, 4, "Fix PATH — symlink Homebrew & system binaries to /usr/local/bin")
    loader("Linking binaries…")
    print()
    show_result(fix_path_links())

    step(3, 4, "Sync your AGY skills into Dia")
    loader("Copying skills…", loops=3)
    print()
    show_result(sync_skills())

    step(4, 4, "Append path rules & persona to Dia's system prompt")
    loader("Appending to chat-base.md…")
    print()
    show_result(append_prompt_rules())

    print(f"\n  {GREEN}{BOLD}✨  Done! Restart Dia (Cmd+Q → reopen) to load all changes.{RESET}\n")

# ─── Help & about ─────────────────────────────────────────────────────────────

def cmd_help() -> None:
    print(f"\n  {BOLD}{CMD}{RESET}  —  Dia AI Intelligence & Sandbox Supercharger  v{__version__}")
    print(f"\n  {CYAN}Usage:{RESET}")
    print(f"    {CMD}                  Launch interactive status dashboard")
    print(f"    {CMD} supercharge       Full guided upgrade (unlock + path + skills + prompt)")
    print(f"    {CMD} status            Quick diagnostic check")
    print(f"    {CMD} unlock            Unlock Seatbelt sandbox profiles")
    print(f"    {CMD} fix-path          Symlink binaries to /usr/local/bin")
    print(f"    {CMD} sync-skills        Sync AGY skills into Dia")
    print(f"    {CMD} append-prompt     Append path override & persona to chat-base.md")
    print(f"    {CMD} restore           Restore original Dia factory defaults")
    print(f"    {CMD} --help            Show this message")
    print(f"    {CMD} --version         Show version\n")
    sys.exit(0)


def cmd_version() -> None:
    print(f"  smarter-dia v{__version__}")
    sys.exit(0)

# ─── Main entrypoint ──────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        cmd_status()
        return

    arg = argv[0].lower()

    dispatch = {
        "supercharge": cmd_supercharge,
        "status":      cmd_status,
        "check":       cmd_status,
        "unlock":      cmd_unlock,
        "fix-path":    cmd_fix_path,
        "fix_path":    cmd_fix_path,
        "sync-skills": cmd_sync_skills,
        "sync_skills": cmd_sync_skills,
        "append-prompt": cmd_append_prompt,
        "persona":     cmd_append_prompt,
        "restore":     cmd_restore,
        "--help":      cmd_help,
        "-h":          cmd_help,
        "help":        cmd_help,
        "--version":   cmd_version,
        "-v":          cmd_version,
    }

    fn = dispatch.get(arg)
    if fn:
        try:
            fn()
        except KeyboardInterrupt:
            print(f"\n\n  {YELLOW}Cancelled.{RESET}\n")
    else:
        print(f"\n  {RED}Unknown command: {arg}{RESET}")
        print(f"  Run  {BOLD}{CMD} --help{RESET}  for usage.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
