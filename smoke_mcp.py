"""Deterministic MCP rehearsal with fixture credentials; no vault or model calls."""
import asyncio
import json
import secrets
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from demo_api import running_api


async def main():
    print("FIXTURE REHEARSAL: real MCP subprocess, synthetic API; no vault, IDE, or model required.")
    token = secrets.token_hex(24)
    with running_api(token) as api:
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name("ticket_mcp.py"))],
            env={"TICKET_API_TOKEN": token, "TICKET_API_URL": api.url})
        async with Client(params) as client:
            names = [t.name for t in (await client.list_tools()).tools]
            if names != ["get_ticket"]:
                raise RuntimeError("Unexpected tool contract.")
            print("Discovered:", names[0])
            for ticket_id in ("T-101", "T-999", "T-101"):
                result = await client.call_tool("get_ticket", {"ticket_id": ticket_id})
                data = result.structured_content
                if ticket_id == "T-999":
                    valid = result.is_error and data.get("error", {}).get("code") == "ticket_not_found"
                else:
                    valid = not result.is_error and data.get("ticket", {}).get("id") == ticket_id
                if not valid or token in json.dumps(data):
                    raise RuntimeError("Rehearsal failed; response withheld.")
                print(json.dumps(data))


if __name__ == "__main__":
    asyncio.run(main())
