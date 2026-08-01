"""
smarter_dia/cli.py
Pure UX layer — all display, prompts, and flow.
Never calls sys directly; always calls engine functions.
"""

from __future__ import annotations

import sys
import time

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

CLEAR   = "\033[2J\033[H"
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[32m"
CYAN    = "\033[36m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"

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
        print(f"\r  {GREEN}✔  {r.message}{RESET}                    ")
    else:
        print(f"\r  {RED}✘  {r.message}{RESET}")
    if r.detail:
        for line in r.detail.splitlines():
            print(f"     {DIM}{line}{RESET}")


def print_status_panel(r: CheckResult) -> None:
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
    count_color = GREEN if r.skills_count > 0 else YELLOW
    print(f"      {count_color}{r.skills_count} skill directories active{RESET}")

    print(f"\n  {BOLD}[ 4 ]  Binary PATH Links{RESET}")
    for name, path in r.binaries.items():
        tick(f"{name:<12}", bool(path), path or "not found")


# ─── Interactive pipeline (the default experience) ────────────────────────────

def run_pipeline() -> None:
    """Full interactive menu — loops until user quits."""
    while True:
        print(CLEAR)
        banner()

        # Live status snapshot
        r = check_status()
        all_good = (
            r.sandbox_cc_unlocked
            and r.sandbox_as_unlocked
            and r.prompt_unlocked
            and r.path_override_injected
            and r.persona_injected
        )

        if all_good:
            print(f"  {GREEN}{BOLD}✨  Dia is fully supercharged!{RESET}\n")
        else:
            missing = []
            if not (r.sandbox_cc_unlocked and r.sandbox_as_unlocked and r.prompt_unlocked):
                missing.append("sandbox unlocked")
            if not r.path_override_injected or not r.persona_injected:
                missing.append("prompt injected")
            print(f"  {YELLOW}⚡  Not fully supercharged — missing: {', '.join(missing)}{RESET}\n")

        print(f"    {BOLD}[1]{RESET}  {BOLD}Supercharge Dia{RESET}  {DIM}— unlock + path + skills + prompt (full run){RESET}")
        print(f"    {BOLD}[2]{RESET}  Unlock sandbox only")
        print(f"    {BOLD}[3]{RESET}  Fix binary PATH links")
        print(f"    {BOLD}[4]{RESET}  Sync AGY skills into Dia")
        print(f"    {BOLD}[5]{RESET}  Inject prompt rules & persona")
        print(f"    {BOLD}[6]{RESET}  View full status")
        print(f"    {BOLD}[7]{RESET}  Restore Dia factory defaults")
        print(f"    {BOLD}[q]{RESET}  Quit")
        print()

        choice = input("  Select option: ").strip().lower()
        print()

        if choice == "1":
            _run_supercharge()
            input(f"\n  {DIM}Press Enter to return to menu…{RESET}")

        elif choice == "2":
            loader("Patching Seatbelt sandbox profiles…")
            show_result(unlock_sandbox())
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "3":
            loader("Linking binaries to /usr/local/bin…")
            show_result(fix_path_links())
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "4":
            loader("Copying AGY skills into Dia…", loops=3)
            show_result(sync_skills())
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "5":
            loader("Appending rules to chat-base.md…")
            show_result(append_prompt_rules())
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "6":
            print(CLEAR)
            banner("· status")
            print_status_panel(check_status())
            print()
            input(f"  {DIM}Press Enter to return to menu…{RESET}")

        elif choice == "7":
            confirm = input(f"  {YELLOW}Restore original Dia defaults? This undoes all changes. [y/N]: {RESET}").strip().lower()
            if confirm == "y":
                show_result(restore_defaults())
            else:
                print(f"  {DIM}Cancelled.{RESET}")
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice in ("q", "quit", "exit"):
            print(f"  {YELLOW}Goodbye!{RESET}\n")
            return

        else:
            print(f"  {RED}Unknown option. Pick 1–7 or q.{RESET}")
            time.sleep(0.8)


def _run_supercharge() -> None:
    """Guided 4-step full supercharge — called from pipeline or direct command."""
    step(1, 4, "Unlock Dia's Seatbelt sandbox")
    loader("Patching sandbox profiles…")
    show_result(unlock_sandbox())

    step(2, 4, "Fix PATH — symlink binaries to /usr/local/bin")
    loader("Linking binaries…")
    show_result(fix_path_links())

    step(3, 4, "Sync your AGY skills into Dia")
    loader("Copying skills…", loops=3)
    show_result(sync_skills())

    step(4, 4, "Append path rules & persona to Dia's system prompt")
    loader("Appending to chat-base.md…")
    show_result(append_prompt_rules())

    print(f"\n  {GREEN}{BOLD}✨  Done! Restart Dia (Cmd+Q → reopen) to load all changes.{RESET}")


# ─── Direct subcommands (for power users / scripts) ───────────────────────────

def cmd_status() -> None:
    print(CLEAR)
    banner("· status")
    print_status_panel(check_status())
    print()


def cmd_supercharge() -> None:
    print(CLEAR)
    banner()
    _run_supercharge()
    print()


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


def cmd_help() -> None:
    print(f"\n  {BOLD}{CMD}{RESET}  —  Dia AI Intelligence & Sandbox Supercharger  v{__version__}")
    print(f"\n  {CYAN}Usage:{RESET}")
    print(f"    {CMD}                  Launch interactive menu")
    print(f"    {CMD} supercharge       Full guided upgrade (unlock + path + skills + prompt)")
    print(f"    {CMD} status            Quick diagnostic check")
    print(f"    {CMD} unlock            Unlock Seatbelt sandbox profiles")
    print(f"    {CMD} fix-path          Symlink binaries to /usr/local/bin")
    print(f"    {CMD} sync-skills        Sync AGY skills into Dia")
    print(f"    {CMD} append-prompt     Append path override & persona to chat-base.md")
    print(f"    {CMD} restore           Restore original Dia factory defaults")
    print(f"    {CMD} --help            Show this message")
    print(f"    {CMD} --version         Show version\n")
    print(f"  {DIM}Also works as: smarter dia [command]{RESET}\n")
    sys.exit(0)


def cmd_version() -> None:
    print(f"  smarter-dia v{__version__}")
    sys.exit(0)


# ─── Main entrypoint ──────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # No args → drop into interactive pipeline
    if not argv:
        try:
            run_pipeline()
        except KeyboardInterrupt:
            print(f"\n\n  {YELLOW}Goodbye!{RESET}\n")
        return

    arg = argv[0].lower()

    dispatch = {
        "supercharge":    cmd_supercharge,
        "status":         cmd_status,
        "check":          cmd_status,
        "unlock":         cmd_unlock,
        "fix-path":       cmd_fix_path,
        "fix_path":       cmd_fix_path,
        "sync-skills":    cmd_sync_skills,
        "sync_skills":    cmd_sync_skills,
        "append-prompt":  cmd_append_prompt,
        "persona":        cmd_append_prompt,
        "restore":        cmd_restore,
        "--help":         cmd_help,
        "-h":             cmd_help,
        "help":           cmd_help,
        "--version":      cmd_version,
        "-v":             cmd_version,
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
