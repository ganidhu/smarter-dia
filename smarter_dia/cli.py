"""
smarter_dia/cli.py
Pure UX layer — all display, prompts, and flow.
Never calls sys directly; always calls engine functions.
"""

from __future__ import annotations

import os
import random
import re
import select
import shutil
import subprocess
import sys
import termios
import textwrap
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from smarter_dia import __version__
from smarter_dia.engine import (
    APP_MANAGEMENT_MESSAGE,
    ActionResult,
    CheckResult,
    append_prompt_rules,
    check_status,
    create_snapshot,
    fix_path_links,
    keychain_status,
    list_snapshots,
    restore_defaults,
    restore_snapshot,
    supercharge,
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


def _join_english(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"

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


def show_fill_bar(width: int = 56, duration: float = 0.85, animate: bool = True) -> None:
    indent = "  "

    def frame(n: int, done: bool = False) -> str:
        n = max(0, min(width, n))
        if done or n >= width:
            return f"{indent}{CYAN}{'━' * width}{RESET}"
        body = max(0, n - 1)
        head = "━" if n else ""
        return (
            f"{indent}{CYAN}{'━' * body}{RESET}"
            f"{BOLD}{MAGENTA}{head}{RESET}"
            f"{DIM}{'-' * (width - n)}{RESET}"
        )

    if not animate or not sys.stdout.isatty():
        print(frame(width, done=True))
        print()
        return

    steps = 38
    for i in range(steps + 1):
        t = i / steps
        eased = 1.0 - (1.0 - t) ** 3
        print(f"\r{frame(int(round(width * eased)))}", end="", flush=True)
        time.sleep(duration / steps)
    print(f"\r{frame(width, done=True)}")
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


def print_app_management_warning() -> None:
    print(f"  {YELLOW}⚠  macOS needs App Management permission to let this tool edit Dia.app.{RESET}")
    print(f"  {YELLOW}   System Settings > Privacy & Security > App Management, turn it ON{RESET}")
    print(f"  {YELLOW}   for your terminal, then re-run with sudo. Quit Dia first.{RESET}")
    print()


def offer_open_app_management() -> None:
    if _prompt(f"  Open System Settings to App Management now? [y/N]: ").strip().lower() != "y":
        return
    try:
        subprocess.run(["open", "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_AppManagement"], check=False)
    except Exception:
        print(f"  {DIM}Could not open Settings automatically. Open it manually.{RESET}")


def handle_bundle_result(r: ActionResult) -> None:
    show_result(r)
    if not r.ok and r.message == APP_MANAGEMENT_MESSAGE:
        print()
        offer_open_app_management()
    print()


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


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    blurb: str = ""
    tooltip: str = ""
    risk: str = ""
    tag: str = ""


MENU_ITEMS = (
    MenuItem(
        key="1",
        label="Supercharge Dia",
        blurb="unlock + path + skills + prompt (full run)",
        tooltip=(
            "Full upgrade: snapshot → sandbox unlock → PATH links → AGY skills → "
            "prompt & persona. Restart Dia with Cmd+Q when it finishes. A snapshot "
            "is taken first so you can roll back."
        ),
        risk="sudo · breaks signature · reversible",
    ),
    MenuItem(
        key="2",
        label="Unlock sandbox only",
        tooltip=(
            "Replaces agent-claude-code.sb, agent.sb, and sandbox-constraints.md "
            "so the agent can exec a full shell. Rewrites spec.yaml blocks and "
            "clears cached AgentServer contexts."
        ),
        risk="sudo · breaks signature · reversible",
        tag="recommended",
    ),
    MenuItem(
        key="3",
        label="Fix binary PATH links",
        tooltip=(
            "Symlinks yt-dlp, ffmpeg, python3, node, bun, git, uv, and gh into "
            "/usr/local/bin so Dia's agent can find them. Restore unlinks the ones "
            "this tool created."
        ),
        risk="sudo · reversible",
    ),
    MenuItem(
        key="4",
        label="Sync AGY skills into Dia",
        tooltip=(
            "Copies ~/.agents/skills into Dia's prompts/skills. Original Dia "
            "skills are left alone; only extra AGY folders are added or replaced."
        ),
        risk="sudo · reversible",
    ),
    MenuItem(
        key="5",
        label="Inject prompt rules & persona",
        tooltip=(
            "Appends a /Users/ganidhu path override and your AGENTS.md persona to "
            "the end of chat-base.md without overwriting existing prompt text."
        ),
        risk="sudo · reversible",
    ),
    MenuItem(
        key="6",
        label="View full status",
        tooltip=(
            "Read-only diagnostic: code signature, login keychain, snapshots, "
            "sandbox unlock, prompt injects, skill count, and binaries on PATH. "
            "Makes no changes."
        ),
        risk="read-only",
    ),
    MenuItem(
        key="7",
        label="Backup current state",
        tooltip=(
            "Copies every managed file, the current skills list, PATH links, and "
            "agent spec.yamls into ~/.smarter-dia/backups/. Does not modify Dia."
        ),
        risk="safe · no Dia writes",
    ),
    MenuItem(
        key="8",
        label="Restore from snapshot",
        tooltip=(
            "Reverts managed files, synced skills, and PATH links from a snapshot, "
            "then re-checks Dia's code signature. Next screen: Enter = baseline."
        ),
        risk="reverts changes",
    ),
    MenuItem(
        key="9",
        label="Unlock login keychain",
        tooltip=(
            "Unlocks the login keychain so Dia can load profiles. Does not patch "
            "Dia files. If it needs a password, you get the exact command to run."
        ),
        risk="no Dia writes",
    ),
    MenuItem(
        key="0",
        label="Restore Dia factory defaults",
        tooltip=(
            "Restores the baseline snapshot and reverts every smarter-dia change "
            "(sandbox, PATH links, skills, prompt). Stronger than a named restore."
        ),
        risk="reverts ALL changes",
    ),
    MenuItem(
        key="q",
        label="Quit",
        tooltip="Leave the menu. Nothing is changed.",
        risk="no changes",
    ),
)

_ANSI_RE = re.compile(r"(?:\033\[[0-9;?]*[A-Za-z])|(?:\033\]8;;.*?(?:\033\\|\x07))")
_SGR_MOUSE_RE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")
_DSR_RE = re.compile(rb"\x1b\[(\d+);(\d+)R")


def _vis_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _pad_vis(text: str, width: int) -> str:
    extra = width - _vis_len(text)
    return text if extra <= 0 else text + (" " * extra)


def _tooltip_box(item: MenuItem, width: int) -> list[str]:
    box_w = width - 2
    inner = max(40, box_w - 4)
    title = f" {item.label} "
    risk_plain = f" {item.risk} " if item.risk else ""
    fill = box_w - 2 - len(title) - len(risk_plain)
    if fill < 1:
        risk_plain = ""
        fill = max(1, box_w - 2 - len(title))
    if risk_plain:
        color = YELLOW if ("breaks signature" in item.risk or "ALL" in item.risk) else GREEN if ("read-only" in item.risk or "no " in item.risk or "safe" in item.risk) else DIM
        risk_bit = f"{color}{risk_plain}{RESET}"
    else:
        risk_bit = ""
    top = f"{CYAN}┌{RESET}{BOLD}{title}{RESET}{CYAN}{'─' * fill}{RESET}{risk_bit}{CYAN}┐{RESET}"
    body: list[str] = []
    for para in item.tooltip.split("\n"):
        body.extend(wrap(para, width=inner) if para.strip() else [""])
    while len(body) < 3:
        body.append("")
    body = body[:3]
    lines = [f"  {top}"]
    for ln in body:
        lines.append(f"  {CYAN}│{RESET} {_pad_vis(ln, inner)} {CYAN}│{RESET}")
    lines.append(f"  {CYAN}└{'─' * (box_w - 2)}┘{RESET}")
    return lines


def _tag_bit(item: MenuItem) -> str:
    if not item.tag:
        return ""
    return f"  {GREEN}{item.tag}{RESET}"


def _menu_item_line(item: MenuItem, selected: bool, width: int) -> str:
    key = f"[{item.key}]"
    tag = _tag_bit(item)
    if selected:
        core = f"▸ {key}  {item.label}"
        if item.blurb:
            core += f"  — {item.blurb}"
        line = f"  {BOLD}{CYAN}{core}{RESET}{tag}"
    else:
        core = f"  {BOLD}{key}{RESET}  {item.label}"
        if item.blurb:
            core += f"  {DIM}— {item.blurb}{RESET}"
        line = f"  {core}{tag}"
    return _pad_vis(line, width)


def _draw_menu_frame(items: tuple[MenuItem, ...], index: int, width: int) -> int:
    box = _tooltip_box(items[index], width)
    for i, item in enumerate(items):
        print(_menu_item_line(item, i == index, width))
    print()
    for ln in box:
        print(ln)
    print()
    print(f"  {DIM}↑/↓ or hover for details  ·  Enter or click to run  ·  q to quit{RESET}")
    sys.stdout.write("\033[J")
    sys.stdout.flush()
    return len(items) + 3 + len(box)


def _menu_interactive_ok() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def _query_cursor_row(fd: int) -> tuple[Optional[int], bytes]:
    sys.stdout.write("\033[6n")
    sys.stdout.flush()
    buf = bytearray()
    deadline = time.time() + 0.2
    while time.time() < deadline:
        wait = max(0.0, deadline - time.time())
        ready, _, _ = select.select([fd], [], [], wait)
        if not ready:
            break
        chunk = os.read(fd, 64)
        if not chunk:
            break
        buf.extend(chunk)
        m = _DSR_RE.search(bytes(buf))
        if m:
            leftover = bytes(buf)[m.end():]
            return int(m.group(1)), leftover
    return None, bytes(buf)


def _parse_event(buf: bytearray) -> Optional[tuple]:
    if not buf:
        return None
    if buf[0] != 0x1B:
        ch = bytes([buf.pop(0)]).decode("utf-8", errors="ignore")
        if ch in ("\r", "\n"):
            return ("confirm",)
        if ch in ("q", "Q"):
            return ("select", "q")
        if ch in ("k", "K"):
            return ("move", -1)
        if ch in ("j", "J"):
            return ("move", 1)
        if ch in "0123456789":
            return ("select", ch)
        return None
    raw = bytes(buf)
    if raw.startswith(b"\x1b[<"):
        m = _SGR_MOUSE_RE.match(raw)
        if not m:
            return None
        del buf[: m.end()]
        btn, x, y, kind = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        if kind == b"M" and btn == 0:
            return ("click", x, y)
        if btn in (32, 33, 34, 35, 64, 65) or (kind == b"M" and btn >= 32):
            return ("hover", x, y)
        return None
    if raw.startswith(b"\x1b[A") or raw.startswith(b"\x1bOA"):
        del buf[:3]
        return ("move", -1)
    if raw.startswith(b"\x1b[B") or raw.startswith(b"\x1bOB"):
        del buf[:3]
        return ("move", 1)
    if raw.startswith(b"\x1b[H") or raw.startswith(b"\x1b[F"):
        del buf[:3]
        return ("edge", 0 if raw.startswith(b"\x1b[H") else -1)
    if len(raw) >= 2 and raw[1] not in (0x5B, 0x4F):
        del buf[0]
        return ("select", "q")
    if len(raw) > 32:
        del buf[0]
    return None


def pick_from_menu(items: tuple[MenuItem, ...] = MENU_ITEMS) -> Optional[str]:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    index = 0
    width = min(76, max(56, shutil.get_terminal_size().columns - 4))
    start_row = None
    buf = bytearray()
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[?25l\033[?1000h\033[?1003h\033[?1006h")
        sys.stdout.flush()
        row, leftover = _query_cursor_row(fd)
        start_row = row
        if leftover:
            buf.extend(leftover)
        if start_row:
            sys.stdout.write(f"\033[{start_row};1H")
        frame_h = _draw_menu_frame(items, index, width)
        n = len(items)
        while True:
            ready, _, _ = select.select([fd], [], [], 0.12)
            if ready:
                chunk = os.read(fd, 256)
                if not chunk:
                    break
                buf.extend(chunk)
            if len(buf) > 512:
                buf.clear()
            if buf == bytearray(b"\x1b"):
                more, _, _ = select.select([fd], [], [], 0.05)
                if more:
                    buf.extend(os.read(fd, 256))
                elif buf == bytearray(b"\x1b"):
                    buf.clear()
                    return "q"
            event = _parse_event(buf)
            if event is None:
                if buf and not bytes(buf).startswith(b"\x1b"):
                    buf.pop(0)
                continue
            etype = event[0]
            changed = False
            if etype == "move":
                index = (index + event[1]) % n
                changed = True
            elif etype == "edge":
                index = 0 if event[1] == 0 else n - 1
                changed = True
            elif etype in ("hover", "click"):
                y = event[2]
                if start_row and start_row <= y < start_row + n:
                    new_index = y - start_row
                    if new_index != index:
                        index = new_index
                        changed = True
                    if etype == "click":
                        return items[index].key
            elif etype == "confirm":
                return items[index].key
            elif etype == "select":
                return event[1]
            if changed:
                width = min(76, max(56, shutil.get_terminal_size().columns - 4))
                if start_row:
                    sys.stdout.write(f"\033[{start_row};1H")
                else:
                    sys.stdout.write(f"\033[{frame_h}A")
                frame_h = _draw_menu_frame(items, index, width)
    except (termios.error, OSError):
        return None
    finally:
        sys.stdout.write("\033[?1000l\033[?1003l\033[?1006l\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return None


def _print_static_menu(items: tuple[MenuItem, ...] = MENU_ITEMS) -> None:
    for item in items:
        line = f"    {BOLD}[{item.key}]{RESET}  {BOLD}{item.label}{RESET}" if item.key == "1" else f"    {BOLD}[{item.key}]{RESET}  {item.label}"
        if item.blurb:
            line += f"  {DIM}— {item.blurb}{RESET}"
        line += _tag_bit(item)
        print(line)
    print()


# ─── Interactive pipeline (the default experience) ────────────────────────────

def run_pipeline() -> None:
    """Full interactive menu — loops until user quits."""
    show_logo_loader()
    first = True
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
            bits = []
            if not (r.sandbox_cc_unlocked and r.sandbox_as_unlocked and r.prompt_unlocked):
                bits.append("the sandbox is still locked")
            if not r.path_override_injected or not r.persona_injected:
                bits.append("prompt rules aren't injected yet")
            if r.signature_valid is False:
                bits.append("the code signature is invalid")
            if r.keychain_ok is False:
                bits.append("the login keychain is locked")
            detail = _join_english(bits)
            detail = detail[0].upper() + detail[1:] + "."
            print(f"  {YELLOW}⚡  {BOLD}Not fully supercharged yet{RESET}")
            print(f"  {YELLOW}   {detail}{RESET}\n")

        show_fill_bar(animate=first)
        first = False

        choice = None
        if _menu_interactive_ok():
            choice = pick_from_menu(MENU_ITEMS)
        if choice is None:
            _print_static_menu(MENU_ITEMS)
            choice = _prompt("  Select option: ").strip().lower()
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
                handle_bundle_result(unlock_sandbox())
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
                handle_bundle_result(sync_skills())
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
                handle_bundle_result(append_prompt_rules())
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
    """Guided full supercharge — called from pipeline or direct command."""
    labels = {
        "snapshot": "Snapshot current state (safe rollback point)",
        "unlock-sandbox": "Unlock Dia's Seatbelt sandbox",
        "path-links": "Fix PATH — symlink binaries to /usr/local/bin",
        "sync-skills": "Sync your AGY skills into Dia",
        "append-prompt": "Append path rules & persona to Dia's system prompt",
    }
    loaders = {
        "snapshot": "Snapshotting…",
        "unlock-sandbox": "Patching sandbox profiles…",
        "path-links": "Linking binaries…",
        "sync-skills": "Copying skills…",
        "append-prompt": "Appending to chat-base.md…",
    }

    def on_step(index: int, name: str) -> None:
        step(index, 5, labels.get(name, name))
        loader(loaders.get(name, name), loops=3 if name == "sync-skills" else 2)

    result = supercharge(on_step=on_step)
    handle_bundle_result(result)
    if not result.ok:
        return

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
    print_app_management_warning()

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
    handle_bundle_result(unlock_sandbox())


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
    print_app_management_warning()
    loader("Copying AGY skills into Dia…", loops=3)
    print()
    handle_bundle_result(sync_skills())


def cmd_append_prompt() -> None:
    print(CLEAR)
    banner("· append-prompt")
    show_disclaimer()
    print_app_management_warning()
    loader("Appending rules to chat-base.md…")
    print()
    handle_bundle_result(append_prompt_rules())


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


def cmd_about() -> None:
    print(f"\n  {BOLD}{CYAN}SMARTER·DIA  v{__version__}{RESET}")
    print(f"  {CYAN}──────────────────────────────────────────────{RESET}")
    print("  CLI to unlock and supercharge Dia AI Browser's agent capabilities.")
    print("\n  • Unlocks macOS Seatbelt sandbox profiles (full shell/exec)")
    print("  • Fixes PATH — symlinks bundled binaries into /usr/local/bin")
    print("  • Syncs your AGY skills into Dia's agent resources")
    print("  • Injects path rules + AGENTS.md persona into Dia's system prompt")
    print("  • Auto-backups every change; restores instantly if Dia misbehaves")
    print(f"\n  {BOLD}Author:{RESET} ganidhu")
    print(f"  {BOLD}License:{RESET} MIT")
    print(f"  {BOLD}Source:{RESET} https://github.com/ganidhu/smarter-dia")
    print(f"  {BOLD}Install:{RESET} brew install ganidhu/smarter-dia/smarter-dia\n")
    sys.exit(0)


def _brew_installed() -> bool:
    tap = subprocess.run(["brew", "list", "--versions", "smarter-dia"], capture_output=True, text=True)
    return tap.returncode == 0


def cmd_update() -> None:
    print(f"\n  {CYAN}Updating smarter-dia…{RESET}")
    if shutil.which("brew") and _brew_installed():
        print(f"  {DIM}Upgrading via Homebrew tap…{RESET}")
        subprocess.run(["brew", "update"], check=False)
        subprocess.run(["brew", "upgrade", "ganidhu/smarter-dia/smarter-dia"], check=False)
    else:
        root = Path(__file__).resolve().parent.parent
        if (root / "pyproject.toml").exists():
            print(f"  {DIM}Reinstalling from local source…{RESET}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(root), "--break-system-packages"],
                check=False,
            )
        else:
            print(f"  {DIM}Running pip install --upgrade…{RESET}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "smarter-dia", "--break-system-packages"],
                check=False,
            )
    print(f"  {GREEN}Update complete!{RESET}\n")
    sys.exit(0)


def cmd_uninstall() -> None:
    print(f"\n  {CYAN}Uninstalling smarter-dia…{RESET}")
    if shutil.which("brew") and _brew_installed():
        print(f"  {DIM}Uninstalling via Homebrew…{RESET}")
        subprocess.run(["brew", "uninstall", "smarter-dia"], check=False)
    else:
        print(f"  {DIM}Running pip uninstall…{RESET}")
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "smarter-dia", "-y", "--break-system-packages"],
            check=False,
        )
    print(f"  {GREEN}Successfully uninstalled!{RESET}\n")
    sys.exit(0)


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
    print(f"    {CMD} --about           Show project info")
    print(f"    {CMD} --update          Upgrade / reinstall")
    print(f"    {CMD} --uninstall       Remove the package")
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
        "--about":        cmd_about,
        "-about":         cmd_about,
        "about":          cmd_about,
        "--update":       cmd_update,
        "-update":        cmd_update,
        "update":         cmd_update,
        "--uninstall":    cmd_uninstall,
        "-uninstall":     cmd_uninstall,
        "uninstall":      cmd_uninstall,
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
