"""Run the actual terminal entry point with disposable credentials, never a vault."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from demo_api import running_api

SERVER = Path(__file__).resolve().parents[1] / "ticket_mcp.py"


class TerminalTests(unittest.TestCase):
    def run_cli(self, ticket_id, url, token):
        # An unrelated working directory ensures no project-folder/IDE dependency.
        with TemporaryDirectory(prefix="ticket cli ") as directory:
            return subprocess.run(
                [sys.executable, str(SERVER), "--ticket-id", ticket_id],
                cwd=directory, env={**os.environ, "TICKET_API_URL": url, "TICKET_API_TOKEN": token},
                capture_output=True, text=True, timeout=10,
            )

    def test_success_and_missing_ticket(self):
        token = secrets.token_hex(24)
        with running_api(token) as api:
            success = self.run_cli("T-101", api.url, token)
            missing = self.run_cli("T-999", api.url, token)
        self.assertEqual(success.returncode, 0)
        self.assertEqual(json.loads(success.stdout)["ticket"]["id"], "T-101")
        self.assertEqual(success.stderr, "")
        self.assertNotIn(token, success.stdout)
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)["error"]["code"], "ticket_not_found")

    def test_bad_credentials_and_arguments_do_not_authenticate(self):
        with running_api(secrets.token_hex(24)) as api:
            for ticket_id, token, code in (
                ("T-101", "", "credential_unavailable"),
                ("T-101", "op://demo/item/password", "credential_unavailable"),
                ("T-101", secrets.token_hex(24), "api_auth_rejected"),
                ("../../secret", secrets.token_hex(24), "invalid_ticket_id"),
            ):
                with self.subTest(code=code):
                    result = self.run_cli(ticket_id, api.url, token)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(json.loads(result.stdout)["error"]["code"], code)
                    if token:
                        self.assertNotIn(token, result.stdout + result.stderr)
            self.assertEqual(api.authenticated_requests, 0)

    def test_nonlocal_endpoint_is_rejected(self):
        result = self.run_cli("T-101", "https://example.invalid", "")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("127.0.0.1", result.stderr)


if __name__ == "__main__":
    unittest.main()
