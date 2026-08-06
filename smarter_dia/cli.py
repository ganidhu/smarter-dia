"""
smarter_dia/cli.py
Pure UX layer — all display, prompts, and flow.
Never calls sys directly; always calls engine functions.
"""

from __future__ import annotations

import os
import random
import sys
import textwrap
import time
from typing import Optional

from smarter_dia import __version__
from smarter_dia.engine import (
    ActionResult,
    CheckResult,
    append_prompt_rules,
    check_status,
    create_snapshot,
    fix_path_links,
    keychain_status,
    list_snapshots,
    restore_snapshot,
    sync_skills,
    unlock_keychain,
    unlock_sandbox,
    verify_signature,
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

HYPERLINK_BEGIN = "\033]8;;"
HYPERLINK_END = "\033\\"
HYPERLINK_RESET = "\033]8;;\033\\"

def hyperlink(text: str, url: str) -> str:
    """Wrap text in an OSC-8 terminal hyperlink (clickable in most terminals)."""
    return f"{HYPERLINK_BEGIN}{url}{HYPERLINK_END}{text}{HYPERLINK_RESET}"

DISCLAIMER = (
    "WARNING: This tool is NOT an official product of TheBrowserCompany. "
    "It modifies Dia's internals. Use at your own risk — the authors are not "
    "responsible for any damage to your browser. A snapshot is taken before "
    "every change; roll back anytime with: smarter-dia restore"
)

def wrap(text: str, width: int = 74) -> list[str]:
    """Word-wrap a plain string into lines at word boundaries."""
    return textwrap.wrap(" ".join(str(text).split()), width=width) or [""]

def print_wrapped(text: str, indent: int = 0, width: int = 74, style: str = "") -> None:
    """Print text wrapped, applying style to every line, with a hanging indent."""
    pad = " " * indent
    for i, ln in enumerate(wrap(text, width=width - indent)):
        lead = pad if i == 0 else " " * (indent + 3)
        print(f"{lead}{style}{ln}{RESET}")


# ─── ASCII logo & loading animation ───────────────────────────────────────────

ORB = (
    "                .:;rrsXXXXri;, \n"
    "            .is2533333333333332Xi, \n"
    "         .iA3hh3333333333333333hh3Ai. \n"
    "       .s5h333333333333333333333333h5r. \n"
    "      r5h3333333333333333333333333333h5i \n"
    "    ,2h33333333333333333333333333333333hA. \n"
    "   :5h3333333333333333333333333333333333h5: \n"
    "  ,5333333333333333333333333333333333333333: \n"
    "  2h3333333333333333333333333333333333333335. \n"
    " ;h3333333333333333333333333333333333333333hr \n"
    " 23333333333333333333333333333333333333333333, \n"
    " 23333333333333333333333333333333333333333333: \n"
    " Xh333333333333333333333333333333333333333335. \n"
    " ;h33333333333333333333333333333333333333333A \n"
    "  233333333333333333333333333333333333333333; \n"
    "  :333333333333333333333333333333333333333hs \n"
    "   i3333333333hhhh333355533333hhhh3333333hA \n"
    "    ;53333352Asri;:,,,....,,,:;irXA533333X \n"
    "     :A2Ar                          isAi \n"
)

LOGO_FRAMES = (
    "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏",
)

def show_logo_loader(duration: float = 2.6, statuses: tuple[str, ...] = ("Rendering the bubble…", "Patching Dia's aura…", "Loading superpowers…")) -> None:
    """Render the Dia speech-bubble logo with an animated spinner + rotating status lines."""
    lines = ORB.splitlines()
    logo_width = max(len(ln) for ln in lines) + 2  # +2 for the 2-space indent
    n_lines = len(lines) + 1  # logo + status line
    n = len(statuses)
    start = time.time()
    i = 0

    def status_line(text: str, frame: str, ok: bool = False) -> str:
        payload = f"{GREEN if ok else MAGENTA}{frame}{RESET}  {DIM}{text}{RESET}"
        pad = max(0, (logo_width - len(f"{frame}  {text}")) // 2)
        return f"{' ' * pad}{payload}".rstrip()

    # first draw
    print("\n".join(f"  {CYAN}{ln}{RESET}" for ln in lines))
    print(f"{status_line(statuses[0], LOGO_FRAMES[0])}", flush=True)
    while time.time() - start < duration:
        time.sleep(0.11)
        i += 1
        frame = LOGO_FRAMES[i % len(LOGO_FRAMES)]
        status = statuses[min(i // 4, n - 1)]
        # move up n_lines and redraw
        print(f"\033[{n_lines}A", end="", flush=True)
        print("\n".join(f"  {CYAN}{ln}{RESET}" for ln in lines))
        print(f"{status_line(status, frame)}", flush=True)
    # final static state
    print(f"\033[{n_lines}A", end="", flush=True)
    print("\n".join(f"  {CYAN}{ln}{RESET}" for ln in lines))
    print(f"{status_line('Ready', '✔', ok=True)}")
    print()

# ─── UI Primitives ────────────────────────────────────────────────────────────

def show_disclaimer() -> None:
    token = "__TBC_LINK__"
    head = " ".join(wrap(DISCLAIMER)).replace("TheBrowserCompany", token)
    for i, ln in enumerate(wrap(head)):
        ln = ln.replace(token, hyperlink("TheBrowserCompany", "https://thebrowser.company"))
        if i == 0:
            print(f"  {YELLOW}{BOLD}⚠  {ln}{RESET}")
        else:
            print(f"  {YELLOW}   {ln}{RESET}")
    print()

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
    lines = wrap(r.message)
    first = lines[0]
    if r.ok:
        print(f"\r  {GREEN}✔  {first}{RESET}                    ")
    else:
        print(f"\r  {RED}✘  {first}{RESET}")
    for ln in lines[1:]:
        print(f"  {DIM}   {ln}{RESET}")
    if r.detail:
        for line in r.detail.splitlines():
            print(f"  {DIM}   {line}{RESET}")


def _bool_label(v, ok_label="OK", bad_label="ISSUE"):
    if v is True:
        return ok_label
    if v is False:
        return bad_label
    return "unknown"


def print_status_panel(r: CheckResult) -> None:
    print(f"  {BOLD}[ 0 ]  Safety{RESET}")
    tick("code signature", r.signature_valid is True,
         _bool_label(r.signature_valid, "VALID", "INVALID — run restore"))
    tick("login keychain", r.keychain_ok is True,
         _bool_label(r.keychain_ok, "unlocked", "LOCKED"))
    tick("backup snapshot exists", r.snapshot_exists)

    print(f"\n  {BOLD}[ 1 ]  Sandbox{RESET}")
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
    show_logo_loader()
    while True:
        print(CLEAR)
        banner()
        show_disclaimer()

        r = check_status()
        all_good = (
            r.sandbox_cc_unlocked
            and r.sandbox_as_unlocked
            and r.prompt_unlocked
            and r.path_override_injected
            and r.persona_injected
        )

        if all_good and r.signature_valid is True:
            print(f"  {GREEN}{BOLD}✨  Dia is fully supercharged & intact!{RESET}\n")
        elif all_good:
            print(f"  {GREEN}{BOLD}✨  Dia is supercharged, but signature is {_bool_label(r.signature_valid)}{RESET}\n")
        else:
            missing = []
            if not (r.sandbox_cc_unlocked and r.sandbox_as_unlocked and r.prompt_unlocked):
                missing.append("sandbox unlocked")
            if not r.path_override_injected or not r.persona_injected:
                missing.append("prompt injected")
            if r.signature_valid is False:
                missing.append("code signature (run restore)")
            if r.keychain_ok is False:
                missing.append("login keychain locked (run unlock)")
            print(f"  {YELLOW}⚡  Not fully supercharged — missing: {', '.join(missing)}{RESET}\n")

        print(f"    {BOLD}[1]{RESET}  {BOLD}Supercharge Dia{RESET}  {DIM}— unlock + path + skills + prompt (full run){RESET}")
        print(f"    {BOLD}[2]{RESET}  Unlock sandbox only")
        print(f"    {BOLD}[3]{RESET}  Fix binary PATH links")
        print(f"    {BOLD}[4]{RESET}  Sync AGY skills into Dia")
        print(f"    {BOLD}[5]{RESET}  Inject prompt rules & persona")
        print(f"    {BOLD}[6]{RESET}  View full status")
        print(f"    {BOLD}[7]{RESET}  Backup current state")
        print(f"    {BOLD}[8]{RESET}  Restore from snapshot")
        print(f"    {BOLD}[9]{RESET}  Unlock login keychain")
        print(f"    {BOLD}[0]{RESET}  Restore Dia factory defaults")
        print(f"    {BOLD}[q]{RESET}  Quit")
        print()

        choice = input("  Select option: ").strip().lower()
        print()

        if choice == "1":
            if not confirm(
                "Full supercharge (unlock + path + skills + prompt)",
                "Patches Dia's internals and invalidates the bundle signature "
                "until you run a restore. A snapshot is taken first so you can "
                "roll back anytime.",
            ):
                input(f"\n  {DIM}Press Enter to return to menu…{RESET}")
            else:
                _run_supercharge()
                input(f"\n  {DIM}Press Enter to return to menu…{RESET}")

        elif choice == "2":
            if not confirm(
                "Unlock Seatbelt sandbox profiles",
                "Allows the Dia agent full shell/exec access and invalidates "
                "the bundle signature until you run a restore.",
            ):
                input(f"\n  {DIM}Press Enter to continue…{RESET}")
            else:
                loader("Patching Seatbelt sandbox profiles…")
                show_result(unlock_sandbox())
                input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "3":
            if not confirm(
                "Fix binary PATH links",
                "Symlinks bundled binaries into /usr/local/bin so the agent "
                "can find them. Reversible via restore.",
            ):
                input(f"\n  {DIM}Press Enter to continue…{RESET}")
            else:
                loader("Linking binaries to /usr/local/bin…")
                show_result(fix_path_links())
                input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "4":
            if not confirm(
                "Sync AGY skills into Dia",
                "Copies your skill folders into Dia's bundle. Reversible "
                "via restore.",
            ):
                input(f"\n  {DIM}Press Enter to continue…{RESET}")
            else:
                loader("Copying AGY skills into Dia…", loops=3)
                show_result(sync_skills())
                input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "5":
            if not confirm(
                "Inject prompt rules & persona",
                "Appends path override + AGENTS.md persona to Dia's system "
                "prompt. Reversible via restore.",
            ):
                input(f"\n  {DIM}Press Enter to continue…{RESET}")
            else:
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
            loader("Snapshotting Dia state…")
            show_result(create_snapshot("manual"))
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "8":
            print(CLEAR)
            banner("· restore")
            show_result(list_snapshots())
            print()
            name = _prompt("  Snapshot name (Enter = baseline): ") or None
            print()
            loader("Restoring from snapshot…", loops=3)
            show_result(restore_snapshot(name))
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice == "9":
            loader("Unlocking login keychain…")
            show_result(unlock_keychain())
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice in ("0", "restore"):
            confirm_defaults = _prompt(f"  {YELLOW}Restore Dia factory defaults from baseline snapshot? This reverts ALL changes. [y/N]: {RESET}").strip().lower()
            if confirm_defaults == "y":
                show_result(restore_defaults())
            else:
                print(f"  {DIM}Cancelled.{RESET}")
            input(f"\n  {DIM}Press Enter to continue…{RESET}")

        elif choice in ("q", "quit", "exit"):
            print(f"  {YELLOW}Goodbye!{RESET}\n")
            return

        else:
            print(f"  {RED}Unknown option. Pick 0–9 or q.{RESET}")
            time.sleep(0.8)


def _run_supercharge() -> None:
    """Guided 4-step full supercharge — called from pipeline or direct command."""
    step(1, 5, "Snapshot current state (safe rollback point)")
    loader("Snapshotting…")
    show_result(create_snapshot("pre-supercharge"))

    step(2, 5, "Unlock Dia's Seatbelt sandbox")
    loader("Patching sandbox profiles…")
    show_result(unlock_sandbox())

    step(3, 5, "Fix PATH — symlink binaries to /usr/local/bin")
    loader("Linking binaries…")
    show_result(fix_path_links())

    step(4, 5, "Sync your AGY skills into Dia")
    loader("Copying skills…", loops=3)
    show_result(sync_skills())

    step(5, 5, "Append path rules & persona to Dia's system prompt")
    loader("Appending to chat-base.md…")
    show_result(append_prompt_rules())

    print(f"\n  {GREEN}{BOLD}✨  Done! Restart Dia (Cmd+Q → reopen) to load all changes.{RESET}")
    sig = verify_signature()
    if sig is False:
        note = "NOTE: Dia's bundle signature is now INVALID. If Dia misbehaves, run `smarter-dia restore` to roll back instantly."
        print_wrapped(note, indent=2, style=f"{RED}⚠  ")
        print()


# ─── Direct subcommands (for power users / scripts) ───────────────────────────

def cmd_status() -> None:
    print(CLEAR)
    banner("· status")
    show_disclaimer()
    print_status_panel(check_status())
    print()


def cmd_supercharge() -> None:
    print(CLEAR)
    banner()
    show_disclaimer()
    _run_supercharge()
    print()


def cmd_unlock() -> None:
    print(CLEAR)
    banner("· unlock")
    show_disclaimer()

    running_as_root = hasattr(os, "geteuid") and os.geteuid() == 0
    who = "root (sudo)" if running_as_root else "user"
    warn = (
        "This patches Dia's Seatbelt sandbox profiles and invalidates the bundle "
        "signature until you run a restore. Backups are taken automatically, but "
        "please confirm before it runs."
    )
    print(f"  {YELLOW}⚠  Running as {BOLD}{who}{RESET}{YELLOW}. {wrap(warn)[0]}{RESET}")
    for ln in wrap(warn)[1:]:
        print(f"  {YELLOW}   {ln}{RESET}")
    print()
    if not _prompt(f"  Proceed with sandbox unlock? [y/N]: ").strip().lower() == "y":
        print(f"  {DIM}Cancelled.{RESET}\n")
        return
    print()
    loader("Patching Seatbelt sandbox profiles…")
    print()
    show_result(unlock_sandbox())
    print()


def cmd_fix_path() -> None:
    print(CLEAR)
    banner("· fix-path")
    show_disclaimer()
    loader("Scanning and linking binaries…")
    print()
    show_result(fix_path_links())
    print()


def cmd_sync_skills() -> None:
    print(CLEAR)
    banner("· sync-skills")
    show_disclaimer()
    loader("Copying AGY skills into Dia…", loops=3)
    print()
    show_result(sync_skills())
    print()


def cmd_append_prompt() -> None:
    print(CLEAR)
    banner("· append-prompt")
    show_disclaimer()
    loader("Appending rules to chat-base.md…")
    print()
    show_result(append_prompt_rules())
    print()


def cmd_backup() -> None:
    print(CLEAR)
    banner("· backup")
    show_disclaimer()
    loader("Snapshotting Dia state…", loops=3)
    print()
    show_result(create_snapshot("manual"))
    print()


def cmd_list_backups() -> None:
    print(CLEAR)
    banner("· backups")
    show_disclaimer()
    show_result(list_snapshots())
    print()


def _prompt(text: str) -> str:
    """Ask for input; return '' when stdin isn't interactive (no hang/EOF)."""
    try:
        if not sys.stdin.isatty():
            return ""
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


CONFIRM_PAIRS = (
    ("Disagree", "Agree"),
    ("Nah", "Understood"),
    ("Nope", "Yep"),
    ("Skip", "Do it"),
    ("Pass", "Let's go"),
    ("Hmm", "Fine"),
)

def confirm(action: str, consequences: str = "") -> bool:
    """Clear confirmation prompt. Returns True only on an affirmative choice.

    Shows a randomized Agree/Disagree-style pair. Non-interactive stdin
    (pipes, scripts) auto-cancels — always safe.
    """
    neg, pos = random.choice(CONFIRM_PAIRS)
    print(f"  {YELLOW}⚠  {BOLD}{action}{RESET}")
    if consequences:
        for ln in wrap(consequences):
            print(f"  {YELLOW}   {ln}{RESET}")
    print(f"  {DIM}    [1] {neg}  ·  [2] {pos}{RESET}")
    answer = _prompt(f"  Pick 1 or 2 [default {neg}]: ").strip().lower()
    print()
    go = answer in ("2", pos.lower(), pos.lower().replace("'", ""))
    if not go:
        print(f"  {DIM}Cancelled.{RESET}\n")
    return go


def cmd_restore(name: Optional[str] = None) -> None:
    print(CLEAR)
    banner("· restore")
    show_disclaimer()
    show_result(list_snapshots())
    print()
    if not name:
        name = _prompt("  Snapshot name (Enter = baseline): ") or None
        print()
    loader("Restoring from snapshot…", loops=3)
    print()
    show_result(restore_snapshot(name))
    print()


def cmd_unlock_keychain() -> None:
    print(CLEAR)
    banner("· unlock-keychain")
    show_disclaimer()
    loader("Unlocking login keychain…")
    print()
    show_result(unlock_keychain())
    print()


def cmd_verify() -> None:
    print(CLEAR)
    banner("· verify")
    show_disclaimer()
    r = check_status()
    print_status_panel(r)
    print()


def cmd_restore_defaults() -> None:
    print(CLEAR)
    banner("· restore")
    show_disclaimer()
    confirm = _prompt(f"  {YELLOW}Restore Dia factory defaults from baseline snapshot? [y/N]: {RESET}").strip().lower()
    if confirm != "y":
        print(f"  {DIM}Cancelled.{RESET}\n")
        return
    show_result(restore_defaults())
    print()


def cmd_help() -> None:
    print(f"\n  {BOLD}{CMD}{RESET}  —  Dia AI Intelligence & Sandbox Supercharger  v{__version__}")
    print(f"\n  {CYAN}Usage:{RESET}")
    print(f"    {CMD}                  Launch interactive menu")
    print(f"    {CMD} supercharge       Full guided upgrade (snapshot + unlock + path + skills + prompt)")
    print(f"    {CMD} status            Quick diagnostic check")
    print(f"    {CMD} backup            Snapshot current Dia state (safe rollback point)")
    print(f"    {CMD} restore           Restore from the latest snapshot")
    print(f"    {CMD} verify            Check signature + keychain + patch state")
    print(f"    {CMD} unlock            Unlock Seatbelt sandbox profiles")
    print(f"    {CMD} unlock-keychain   Unlock the login keychain")
    print(f"    {CMD} fix-path          Symlink binaries to /usr/local/bin")
    print(f"    {CMD} sync-skills       Sync AGY skills into Dia")
    print(f"    {CMD} append-prompt     Append path override & persona to chat-base.md")
    print(f"    {CMD} restore           Restore Dia factory defaults from snapshot")
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
        "backup":         cmd_backup,
        "backups":        cmd_list_backups,
        "list-backups":   cmd_list_backups,
        "restore":        cmd_restore,
        "unlock-keychain": cmd_unlock_keychain,
        "keychain":       cmd_unlock_keychain,
        "verify":         cmd_verify,
        "defaults":       cmd_restore_defaults,
        "--help":         cmd_help,
        "-h":             cmd_help,
        "help":           cmd_help,
        "--version":      cmd_version,
        "-v":             cmd_version,
    }

    fn = dispatch.get(arg)
    if fn:
        try:
            fn(*argv[1:])
        except KeyboardInterrupt:
            print(f"\n\n  {YELLOW}Cancelled.{RESET}\n")
    else:
        print(f"\n  {RED}Unknown command: {arg}{RESET}")
        print(f"  Run  {BOLD}{CMD} --help{RESET}  for usage.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
