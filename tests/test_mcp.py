"""Real MCP stdio subprocess tests; fixtures only, no IDE or vault access."""
import json
import secrets
import sys
import unittest
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from demo_api import running_api
from ticket_mcp import TOOL_SCHEMA

ROOT = Path(__file__).resolve().parents[1]


def parameters(url, token=""):
    return StdioServerParameters(command=sys.executable,
        args=[str(ROOT / "ticket_mcp.py")], cwd=ROOT,
        env={"TICKET_API_URL": url, "TICKET_API_TOKEN": token})


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_and_contract(self):
        token = secrets.token_hex(24)
        with running_api(token) as api:
            async with Client(parameters(api.url, token)) as client:
                listed = await client.list_tools()
                self.assertEqual([t.name for t in listed.tools], ["get_ticket"])
                self.assertFalse(listed.tools[0].input_schema["additionalProperties"])
                self.assertEqual(listed.tools[0].description, TOOL_SCHEMA["description"])
                self.assertEqual(listed.tools[0].input_schema, TOOL_SCHEMA["parameters"])
                self.assertTrue(listed.tools[0].input_schema["properties"]["ticket_id"]["description"])
                for ticket_id in ("T-101", "T-102"):
                    result = await client.call_tool("get_ticket", {"ticket_id": ticket_id})
                    self.assertFalse(result.is_error)
                    self.assertEqual(set(result.structured_content["ticket"]), {"id", "title", "status"})
                    self.assertNotIn(token, json.dumps(result.structured_content))
                    self.assertNotIn(token, str(result.content))
                count = api.authenticated_requests
                for name, args in (
                    ("get_ticket", {"ticket_id": "T-101", "url": "https://attacker.invalid"}),
                    ("get_ticket", {"ticket_id": "../../secret"}),
                    ("get_ticket", {"ticket_id": 101}),
                    ("get_ticket", {}),
                    ("read_secret", {"reference": "op://demo/item/password"}),
                ):
                    result = await client.call_tool(name, args)
                    self.assertTrue(result.is_error)
                    self.assertEqual(api.authenticated_requests, count)
                result = await client.call_tool("get_ticket", {"ticket_id": "T-999"})
                self.assertTrue(result.is_error)
                self.assertEqual(result.structured_content["error"]["code"], "ticket_not_found")

    async def test_missing_unresolved_and_wrong_credentials(self):
        with running_api(secrets.token_hex(24)) as api:
            for token, code in (("", "credential_unavailable"),
                                ("op://demo/item/password", "credential_unavailable"),
                                (secrets.token_hex(24), "api_auth_rejected")):
                async with Client(parameters(api.url, token)) as client:
                    result = await client.call_tool("get_ticket", {"ticket_id": "T-101"})
                    self.assertTrue(result.is_error)
                    self.assertEqual(result.structured_content["error"]["code"], code)
            self.assertEqual(api.authenticated_requests, 0)

    async def test_failure_then_recovery_on_same_connection(self):
        token = secrets.token_hex(24)
        with running_api(token) as api:
            async with Client(parameters(api.url, token)) as client:
                missing = await client.call_tool("get_ticket", {"ticket_id": "T-999"})
                recovered = await client.call_tool("get_ticket", {"ticket_id": "T-101"})
                self.assertEqual(missing.structured_content["error"]["code"], "ticket_not_found")
                self.assertFalse(recovered.is_error)
                self.assertEqual(recovered.structured_content["ticket"]["id"], "T-101")

    async def test_secret_echo_is_withheld_across_mcp(self):
        token = secrets.token_hex(24)
        tickets = {"T-101": {"id": "T-101", "title": token, "status": "open"}}
        with running_api(token, tickets=tickets) as api:
            async with Client(parameters(api.url, token)) as client:
                result = await client.call_tool("get_ticket", {"ticket_id": "T-101"})
                self.assertTrue(result.is_error)
                self.assertEqual(result.structured_content["error"]["code"], "secret_echo_blocked")
                self.assertNotIn(token, str(result.content))
                self.assertNotIn(token, json.dumps(result.structured_content))


if __name__ == "__main__":
    unittest.main()
