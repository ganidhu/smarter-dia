from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from smarter_dia import engine
from smarter_dia.engine import (
    PATH_OVERRIDE_SENTINEL,
    append_prompt_rules,
    create_snapshot,
    fix_path_links,
    restore_snapshot,
    supercharge,
    sync_skills,
    unlock_sandbox,
)


class ReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="smarter-dia-"))
        self.addCleanup(self._cleanup)
        self.dia = self.tmp / "Dia.app"
        dist = self.dia / "Contents/Resources/agent-server-resources/dist"
        prompts = dist / "prompts"
        (prompts / "mixins").mkdir(parents=True)
        (prompts / "skills" / "stock-skill").mkdir(parents=True)
        (dist / "agents" / "demo").mkdir(parents=True)
        (dist / "agent-claude-code.sb").write_text("RESTRICTED CC\n")
        (dist / "agent.sb").write_text("RESTRICTED AS\n")
        (prompts / "mixins" / "sandbox-constraints.md").write_text("RESTRICTED PROMPT\n")
        (prompts / "chat-base.md").write_text("base prompt\n")
        (dist / "agents" / "demo" / "spec.yaml").write_text(
            "name: demo\n    <sandbox_constraints>old</sandbox_constraints>\n"
        )
        (prompts / "skills" / "stock-skill" / "SKILL.md").write_text("stock\n")

        self.home = self.tmp / "home"
        self.backup = self.home / ".smarter-dia" / "backups"
        self.state = self.home / ".smarter-dia" / "state.json"
        self.path_bin = self.tmp / "usr" / "local" / "bin"
        self.path_bin.mkdir(parents=True)
        self.real_bin = self.tmp / "realbin"
        self.real_bin.mkdir()
        for name in ("ffmpeg", "yt-dlp"):
            p = self.real_bin / name
            p.write_text("#!/bin/sh\n")
            p.chmod(0o755)
        (self.path_bin / "git").write_text("real-git-binary\n")
        foreign = self.tmp / "foreign-node"
        foreign.write_text("foreign\n")
        foreign.chmod(0o755)
        (self.path_bin / "node").symlink_to(foreign)

        self.agy = self.home / ".agents" / "skills"
        (self.agy / "agy-skill").mkdir(parents=True)
        (self.agy / "agy-skill" / "SKILL.md").write_text("agy\n")
        self.agents_md = self.home / "AGENTS.md"
        self.agents_md.write_text("Ganidhu Context\nhello\n")
        self.claude = self.home / ".claude" / "settings.json"
        self.claude.parent.mkdir(parents=True)
        self.claude.write_text("{}\n")

        self._old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.real_bin}{os.pathsep}{self._old_path}"

        engine.configure(
            real_home=self.home,
            dia_bundle=self.dia,
            backup_root=self.backup,
            state_file=self.state,
            path_bin_dir=self.path_bin,
            agy_skills=self.agy,
            agents_md=self.agents_md,
            claude_settings=self.claude,
            require_root=False,
        )

    def _cleanup(self) -> None:
        os.environ["PATH"] = self._old_path
        engine.reset_configure()
        if self.tmp.exists():
            for root, dirs, files in os.walk(self.tmp, topdown=False):
                for name in files:
                    p = Path(root) / name
                    try:
                        p.chmod(p.stat().st_mode | stat.S_IWUSR)
                    except OSError:
                        pass
                for name in dirs:
                    p = Path(root) / name
                    try:
                        p.chmod(0o755)
                    except OSError:
                        pass
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_label_snapshot_recaptures_current_bytes(self) -> None:
        chat = engine.DIA_CHAT_BASE
        chat.write_text("first-bytes\n")
        first = create_snapshot("pre-supercharge")
        self.assertTrue(first.ok, first.message)
        self.assertIsNotNone(first.detail)
        chat.write_text("second-bytes\n")
        second = create_snapshot("pre-supercharge")
        self.assertTrue(second.ok, second.message)
        self.assertNotEqual(first.detail, second.detail)
        chat.write_text("mutated-after\n")
        restored = restore_snapshot(Path(second.detail).name)
        self.assertTrue(restored.ok, restored.message)
        self.assertEqual(chat.read_text(), "second-bytes\n")

    def test_restore_reports_not_ok_when_write_skipped_or_fails(self) -> None:
        snap = create_snapshot("manual")
        self.assertTrue(snap.ok, snap.message)
        snap_dir = Path(snap.detail)
        (snap_dir / "files" / "chat-base.md").unlink()
        engine.DIA_CHAT_BASE.write_text("changed\n")
        result = restore_snapshot(snap_dir.name)
        self.assertFalse(result.ok, result.message)
        self.assertIn("chat-base.md", (result.detail or "") + result.message)

        snap2 = create_snapshot("manual")
        self.assertTrue(snap2.ok, snap2.message)
        parent = engine.DIA_CHAT_BASE.parent
        mode = parent.stat().st_mode
        os.chmod(parent, 0o555)
        try:
            engine.DIA_CHAT_BASE.write_text("changed-again\n")
        except OSError:
            pass
        try:
            denied = restore_snapshot(Path(snap2.detail).name)
        finally:
            os.chmod(parent, mode)
        if os.geteuid() == 0:
            note = Path(os.environ.get("SMARTER_DIA_RESTORE_NOTE", ""))
            if note:
                note.write_text(
                    "restore permission-denied could not be simulated as root; "
                    "missing-bytes restore still asserts not-ok.\n"
                )
        else:
            self.assertFalse(denied.ok, denied.message)

    def test_path_link_leaves_regular_file_and_restore_skips_foreign(self) -> None:
        git_before = (self.path_bin / "git").read_text()
        node_before = (self.path_bin / "node").resolve()
        before = create_snapshot("manual")
        self.assertTrue(before.ok, before.message)
        linked = fix_path_links()
        self.assertTrue(linked.ok, linked.message)
        self.assertTrue((self.path_bin / "ffmpeg").is_symlink())
        self.assertTrue((self.path_bin / "git").is_file())
        self.assertFalse((self.path_bin / "git").is_symlink())
        self.assertEqual((self.path_bin / "git").read_text(), git_before)
        self.assertEqual((self.path_bin / "node").resolve(), node_before)
        restored = restore_snapshot(Path(before.detail).name)
        self.assertTrue(restored.ok, restored.message)
        self.assertFalse((self.path_bin / "ffmpeg").exists())
        self.assertTrue((self.path_bin / "git").is_file())
        self.assertEqual((self.path_bin / "git").read_text(), git_before)
        self.assertTrue((self.path_bin / "node").is_symlink())
        self.assertEqual((self.path_bin / "node").resolve(), node_before)

    def test_supercharge_aborts_later_steps_on_first_failure(self) -> None:
        chat_before = engine.DIA_CHAT_BASE.read_text()
        cc_before = engine.DIA_SANDBOX_CC.read_text()
        os.chmod(engine.DIA_DIST, 0o555)
        try:
            result = supercharge()
        finally:
            os.chmod(engine.DIA_DIST, 0o755)
        self.assertFalse(result.ok, result.message)
        self.assertIn("failed at unlock-sandbox", result.message)
        self.assertEqual(engine.DIA_CHAT_BASE.read_text(), chat_before)
        self.assertEqual(engine.DIA_SANDBOX_CC.read_text(), cc_before)
        self.assertNotIn(PATH_OVERRIDE_SENTINEL, engine.DIA_CHAT_BASE.read_text())
        self.assertFalse((self.path_bin / "ffmpeg").is_symlink())
        self.assertFalse((self.path_bin / "ffmpeg").exists())
        self.assertFalse((engine.DIA_SKILLS / "agy-skill").exists())
        self.assertTrue((self.path_bin / "git").is_file())

    def test_missing_bundle_and_files_return_failed_result(self) -> None:
        engine.configure(
            dia_bundle=self.tmp / "Missing.app",
            backup_root=self.backup,
            state_file=self.state,
            path_bin_dir=self.path_bin,
            require_root=False,
        )
        snap = create_snapshot("pre-supercharge")
        self.assertFalse(snap.ok)
        self.assertIn("not found", snap.message.lower())
        unlocked = unlock_sandbox()
        self.assertFalse(unlocked.ok)
        charged = supercharge()
        self.assertFalse(charged.ok)

        engine.configure(
            dia_bundle=self.dia,
            backup_root=self.backup,
            state_file=self.state,
            path_bin_dir=self.path_bin,
            agy_skills=self.agy,
            agents_md=self.agents_md,
            claude_settings=self.claude,
            require_root=False,
        )
        engine.DIA_CHAT_BASE.unlink()
        missing_file = unlock_sandbox()
        self.assertFalse(missing_file.ok)
        self.assertIn("missing", missing_file.message.lower())
        self.assertFalse(append_prompt_rules().ok)
        self.assertFalse(sync_skills().ok)
        self.assertFalse(supercharge().ok)


if __name__ == "__main__":
    unittest.main()
