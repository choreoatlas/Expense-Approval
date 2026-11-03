from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from close_loop.onboarding.observe import (
    REQUIRED_SOURCE_PATHS,
    browser_environment, child_environment, http_application, observe_api,
    publish, source_binding,
)


class OnboardingObserverTests(unittest.TestCase):
    @contextmanager
    def identity_fixture(self, untracked_required_path=None):
        # Synthetic identity fixture only; this is not real Expense evidence.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(["git", "-C", str(root), *args], env=child_environment(), stderr=subprocess.PIPE)

            git("init")
            git("remote", "add", "origin", "https://github.com/choreoatlas/Expense-Approval.git")
            (root / "fixture.txt").write_text("original fixture bytes\n")
            git("add", "fixture.txt")
            for path in REQUIRED_SOURCE_PATHS:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("synthetic source identity fixture: " + path + "\n")
                if path != untracked_required_path:
                    git("add", path)
            git("-c", "commit.gpgsign=false", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Synthetic identity fixture")
            revision = git("rev-parse", "HEAD").decode().strip()
            yield root, revision

    def test_selected_revision_and_actual_bytes_are_both_required(self):
        with self.identity_fixture() as (root, revision):
            self.assertEqual(revision, source_binding(revision, root)["product_git_revision"])
            with self.assertRaisesRegex(ValueError, "PRODUCT_REVISION_DOES_NOT_MATCH_CHECKOUT"):
                source_binding("0" * 40, root)
            (root / "fixture.txt").write_text("different fixture bytes\n")
            with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_MISMATCH:fixture.txt"):
                source_binding(revision, root)

    def test_observer_and_each_declaration_must_belong_to_selected_git_tree(self):
        for untracked in REQUIRED_SOURCE_PATHS[:6]:
            with self.subTest(untracked=untracked), self.identity_fixture(untracked) as (root, revision):
                self.assertTrue((root / untracked).is_file())
                with self.assertRaisesRegex(ValueError, "SOURCE_REQUIRED_PATH_NOT_PINNED:" + untracked):
                    source_binding(revision, root)

    def test_publish_preserves_existing_output_and_cleans_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "observations.json"
            output.write_bytes(b"original destination\n")
            with self.assertRaises(FileExistsError):
                publish(output, {"synthetic": "replacement"})
            self.assertEqual(b"original destination\n", output.read_bytes())
            self.assertEqual([], list(root.glob(".expense-observation-*")))

    def test_http_context_closes_on_interruption(self):
        resources = []
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                with http_application(Path(directory) / "owned.sqlite3", resources):
                    raise KeyboardInterrupt
        self.assertTrue(resources[0]["closed"])
        self.assertFalse(resources[0]["thread_alive_after_close"])

    def test_http_listener_closes_when_its_thread_cannot_start(self):
        resources = []
        with tempfile.TemporaryDirectory() as directory:
            with patch("close_loop.onboarding.observe.threading.Thread.start", side_effect=RuntimeError("synthetic thread-start failure")):
                with self.assertRaisesRegex(RuntimeError, "synthetic thread-start failure"):
                    with http_application(Path(directory) / "owned.sqlite3", resources):
                        self.fail("context yielded after failed start")
        self.assertFalse(resources[0]["thread_started"])
        self.assertTrue(resources[0]["listener_closed"])
        self.assertTrue(resources[0]["closed"])

    def test_api_observer_retains_raw_rejection_and_revision_context(self):
        observations, resources = [], []
        with tempfile.TemporaryDirectory() as directory:
            observe_api(Path(directory) / "owned.sqlite3", observations, resources)
        rows = {row["id"]: row for row in observations}
        denied = rows["api-main.employee-final"]
        self.assertEqual(403, denied["response"]["status"])
        self.assertIn("own expense", denied["response"]["body"]["error"])
        self.assertEqual(denied["before"], denied["after"])
        self.assertEqual("manager_pending", denied["before"]["revisions"][0]["status"])
        for prefix in ["api-gm-rework", "api-first-rework"]:
            old = rows[prefix + ".stale-final"]
            self.assertEqual(400, old["response"]["status"])
            self.assertEqual("1", old["request"]["path"].split("/")[-2])
            self.assertEqual(old["before"], old["after"])
            self.assertEqual(2, old["before"]["revisions"][-1]["revision"])
        self.assertEqual("general_manager", rows["api-main.final-approve"]["response"]["body"]["actor_role"])
        self.assertTrue(all(resource["closed"] for resource in resources))

    def test_driver_and_application_child_environments_exclude_credentials(self):
        canaries = {"GITHUB_TOKEN": "synthetic-canary", "AWS_SECRET_ACCESS_KEY": "synthetic-canary", "DATABASE_URL": "synthetic-canary"}
        with patch.dict(os.environ, canaries):
            self.assertFalse(set(canaries) & child_environment().keys())
            with browser_environment():
                self.assertFalse(set(canaries) & os.environ.keys())
            self.assertEqual("synthetic-canary", os.environ["GITHUB_TOKEN"])


if __name__ == "__main__":
    unittest.main()
