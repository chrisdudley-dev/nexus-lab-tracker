import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

class TestCodeQLCommandLineRegression(unittest.TestCase):
    def _read(self, rel: str) -> str:
        p = REPO_ROOT / rel
        self.assertTrue(p.exists(), f"missing file: {rel}")
        return p.read_text(encoding="utf-8", errors="replace")

    def test_lims_api_snapshot_export_cmd_constant(self):
        s = self._read("scripts/lims_api.py")

        # Must keep argv constant for snapshot export (no --exports-dir on argv).
        self.assertIn(
            'cmd = ["./scripts/lims.sh", "snapshot", "export", "--json"]',
            s,
            "snapshot export cmd must remain constant and not include request-derived values",
        )

        # Defensive: do not allow reintroduction of exports_dir on argv.
        self.assertNotRegex(
            s,
            r'cmd\s*=\s*\[.*snapshot.*export.*--exports-dir',
            "snapshot export must not pass --exports-dir on argv",
        )

        # Ensure exports_dir is still passed via environment.
        self.assertRegex(
            s,
            r'env\["EXPORTS_DIR"\]\s*=\s*exports_dir',
            "EXPORTS_DIR must be set in env for snapshot export",
        )

    def test_lims_api_sample_report_not_appending_identifier_to_cmd(self):
        s = self._read("scripts/lims_api.py")

        # Must keep argv constant for sample report (identifier/limit via env).
        self.assertIn(
            'cmd = ["./scripts/lims.sh", "sample", "report", "--json"]',
            s,
            "sample report cmd must remain constant",
        )

        # Ensure the old taint pattern does not return: cmd += [identifier]
        self.assertNotRegex(
            s,
            r'cmd\s*\+=\s*\[\s*identifier\s*\]',
            "sample report must not append identifier to argv",
        )

        # Ensure env keys are used.
        self.assertRegex(
            s,
            r'env\["NEXUS_API_SAMPLE_IDENTIFIER"\]\s*=\s*identifier',
            "sample report must pass identifier via env",
        )
        # Limit should be passed via env when present.
        self.assertRegex(
            s,
            r'NEXUS_API_SAMPLE_REPORT_LIMIT',
            "sample report should support env-based limit",
        )

    def test_cli_requires_identifier_guard_present(self):
        s = self._read("lims/cli.py")

        # Guard message should remain present.
        self.assertIn(
            'ERROR: identifier is required',
            s,
            "CLI should fail fast if identifier is missing",
        )

        # Identifier argument should be optional (nargs='?') so env can supply it.
        self.assertRegex(
            s,
            r'add_argument\([\s\S]*"identifier"[\s\S]*nargs\s*=\s*["\']\?["\']',
            "CLI identifier should use nargs='?' to allow env fallback",
        )


if __name__ == "__main__":
    unittest.main()
