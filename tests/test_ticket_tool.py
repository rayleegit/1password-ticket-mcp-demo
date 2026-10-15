import asyncio
import io
import json
import os
import secrets
from http.client import BadStatusLine, IncompleteRead
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ticket_mcp import NoRedirects, TicketTool, validate_endpoint
from demo_api import running_api


GOOD_CALL = {"name": "get_ticket", "arguments": {"ticket_id": "T-101"}}


class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.token = secrets.token_urlsafe(32)
        environment = patch.dict(os.environ, {"TICKET_API_TOKEN": self.token})
        environment.start()
        self.addCleanup(environment.stop)
        self.tool = TicketTool("http://127.0.0.1:8765")

    @patch("ticket_mcp.os.environ.get")
    async def test_validation_before_environment_read(self, read_environment):
        for call in [None, [], {}, {**GOOD_CALL, "secret": "value"},
                     {"name": "read_secret", "arguments": {}},
                     {"name": "get_ticket", "arguments": {"ticket_id": "T-101", "url": "https://attacker.invalid"}},
                     {"name": "get_ticket", "arguments": {"ticket_id": "../../secret"}},
                     {"name": "get_ticket", "arguments": {"ticket_id": "T-101\n"}},
                     {"name": "get_ticket", "arguments": {"ticket_id": 101}},
                     {"name": "get_ticket", "arguments": []}]:
            with self.subTest(call=call):
                result = await self.tool.execute(call)
                self.assertFalse(result["ok"])
        read_environment.assert_not_called()

    async def test_missing_or_unresolved_secret_prevents_http(self):
        for value in ("", "op://private-demo/item/password"):
            with patch.dict(os.environ, {"TICKET_API_TOKEN": value}), patch.object(self.tool, "_request") as request:
                result = await self.tool.execute(GOOD_CALL)
            self.assertEqual(result["error"]["code"], "credential_unavailable")
            self.assertNotIn("private-demo", json.dumps(result))
            request.assert_not_called()

    async def test_invalid_header_credential_prevents_http(self):
        for bad_token in ["too-short", "A" * 25 + "\r\nX-Injected: yes"]:
            os.environ["TICKET_API_TOKEN"] = bad_token
            with patch.object(self.tool, "_request") as request:
                result = await self.tool.execute(GOOD_CALL)
            self.assertEqual(result["error"]["code"], "invalid_demo_credential")
            request.assert_not_called()

    async def test_redirect_is_not_followed(self):
        with patch.object(self.tool.opener, "open", side_effect=HTTPError("", 302, "", {}, None)):
            result = await self.tool.execute(GOOD_CALL)
        self.assertEqual(result["error"]["code"], "redirect_blocked")
        handlers = self.tool.opener.handlers
        self.assertTrue(any(isinstance(h, NoRedirects) for h in handlers))
        self.assertIsNone(NoRedirects().redirect_request(None, None, 302, "", {}, "https://attacker.invalid"))

    async def test_error_response_body_is_never_exposed(self):
        with patch.object(self.tool.opener, "open", side_effect=HTTPError("", 500, self.token, {}, io.BytesIO(self.token.encode()))):
            result = await self.tool.execute(GOOD_CALL)
        self.assertEqual(result["error"]["code"], "api_error")
        self.assertNotIn(self.token, json.dumps(result))

    async def test_malformed_http_is_sanitized(self):
        for stage in ("open", "read"):
            for error in (BadStatusLine(self.token), IncompleteRead(self.token.encode(), 50)):
                response = io.BytesIO(b"")
                target = self.tool.opener if stage == "open" else response
                method = "open" if stage == "open" else "read"
                with self.subTest(stage=stage, error=type(error).__name__), patch.object(
                    self.tool.opener, "open", return_value=response
                ), patch.object(target, method, side_effect=error):
                    result = await self.tool.execute(GOOD_CALL)
                self.assertEqual(result["error"]["code"], "invalid_response")
                self.assertNotIn(self.token, json.dumps(result))

    async def test_network_error_is_actionable(self):
        with patch.object(self.tool.opener, "open", side_effect=TimeoutError(self.token)):
            result = await self.tool.execute(GOOD_CALL)
        self.assertEqual(result["error"]["code"], "api_unavailable")
        self.assertNotIn(self.token, json.dumps(result))

    async def test_oversized_response_rejected(self):
        with patch.object(self.tool.opener, "open", return_value=io.BytesIO(b" " * 8193)):
            result = await self.tool.execute(GOOD_CALL)
        self.assertEqual(result["error"]["code"], "invalid_response")

    async def test_response_schema_validation(self):
        bad_bodies = [b"not json", b"[]", b"null", b'{}',
                      json.dumps({"id": "T-102", "status": "open", "title": "wrong ticket"}).encode(),
                      json.dumps({"id": "T-101", "status": "open", "title": "bad\u001b[31m"}).encode(),
                      json.dumps({"id": "T-101", "status": "made-up", "title": "bad status"}).encode()]
        for raw in bad_bodies:
            with self.subTest(raw=raw), patch.object(self.tool.opener, "open", return_value=io.BytesIO(raw)):
                result = await self.tool.execute(GOOD_CALL)
                self.assertEqual(result["error"]["code"], "invalid_response")

    def test_endpoint_is_operator_controlled_and_local(self):
        for url in ["https://example.com", "http://localhost:8765", "http://127.0.0.1:8765@attacker.invalid",
                    "http://127.0.0.1:8765/path", "http://127.0.0.1:8765?q=x", "http://127.0.0.1:8765#x",
                    "http://user:pass@127.0.0.1:8765", "http://127.0.0.1:bad",
                    "http://127.0.0.1:0", "http://127.0.0.1:65536"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_endpoint(url)
        self.assertEqual(validate_endpoint("http://127.0.0.1:8765/"), "http://127.0.0.1:8765")


class HTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.token = secrets.token_urlsafe(32)
        environment = patch.dict(os.environ, {"TICKET_API_TOKEN": self.token})
        environment.start()
        self.addCleanup(environment.stop)

    def test_authenticated_success_without_token_in_response(self):
        with running_api(self.token) as api:
            result = asyncio.run(TicketTool(api.url).execute(GOOD_CALL))
            self.assertEqual(api.authenticated_requests, 1)
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["ticket"]), {"id", "title", "status"})
        self.assertNotIn(self.token, json.dumps(result))

    def test_wrong_credential_is_rejected(self):
        os.environ["TICKET_API_TOKEN"] = secrets.token_urlsafe(32)
        with running_api(self.token) as api:
            result = asyncio.run(TicketTool(api.url).execute(GOOD_CALL))
            self.assertEqual(api.authenticated_requests, 0)
        self.assertEqual(result["error"]["code"], "api_auth_rejected")

    def test_unknown_ticket(self):
        with running_api(self.token) as api:
            result = asyncio.run(TicketTool(api.url).execute(
                {"name": "get_ticket", "arguments": {"ticket_id": "T-999"}}))
        self.assertEqual(result["error"]["code"], "ticket_not_found")

    def test_unneeded_fields_never_reach_caller(self):
        with running_api(self.token) as api:
            result = asyncio.run(TicketTool(api.url).execute(
                {"name": "get_ticket", "arguments": {"ticket_id": "T-102"}}))
        self.assertTrue(result["ok"])
        self.assertEqual(set(result["ticket"]), {"id", "title", "status"})
        self.assertNotIn("synthetic customer report", json.dumps(result))

    def test_literal_secret_echo_rejected(self):
        tickets = {"T-101": {"id": "T-101", "status": "open", "title": self.token}}
        with running_api(self.token, tickets=tickets) as api:
            result = asyncio.run(TicketTool(api.url).execute(GOOD_CALL))
        self.assertEqual(result["error"]["code"], "secret_echo_blocked")
        self.assertNotIn(self.token, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
