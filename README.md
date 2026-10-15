# API access without hardcoded keys

Copying API keys into tool configuration creates more files to protect and update. This Python demo stores a **1Password secret reference** instead. `op run` resolves it when the process starts, and a read-only tool returns a synthetic ticket's ID, title, and status.

Run from any terminal or IDE. The same lookup optionally supports **MCP (Model Context Protocol)** over standard input/output. No model or specific IDE is required.

## Set up and rehearse

Use Python 3.12 (`python3.12` or Windows `py -3.12` if needed):

```text
python -m venv .venv-mcp
```

Activate with `. .venv-mcp/bin/activate` in Bash/Zsh or `.\.venv-mcp\Scripts\Activate.ps1` in Windows PowerShell. If activation is blocked, use `.venv-mcp/bin/python` or `.\.venv-mcp\Scripts\python.exe` instead of `python`; do not change execution policy.

```text
python -m pip install -r requirements-mcp.lock.txt
python smoke_mcp.py
python -m unittest discover -s tests -v
```

The rehearsal checks success, a missing ticket, and recovery over real MCP using fixture credentials and a temporary local API. It requires no vault or external service. Sandboxes may require localhost permission.

## Run with 1Password

Install and authenticate [1Password CLI](https://www.1password.dev/cli/get-started). Confirm `op --version` works. Use PowerShell on Windows and select the Python environment in both terminals.

1. Create a disposable 32-character alphanumeric password in a dedicated demo vault. Copy its `op://vault/item/field` reference.
2. In **Terminal A**, run `python demo_api.py`. Paste the disposable password at the hidden prompt, off screen. Clear the clipboard. This independently provisions the API's expected token; a real service would issue its own.
3. Copy [ticket.env.example](examples/ticket.env.example) to `.env.demo`. Replace the placeholder with the **reference, never the password**. Save as UTF-8.
4. In **Terminal B**, run:

```text
op run --env-file=.env.demo -- python ticket_mcp.py --ticket-id T-101
```

Approve expected CLI authorization. The result should be:

```json
{"ok": true, "ticket": {"id": "T-101", "title": "Webhook retries after timeout", "status": "open"}}
```

Try T-999, then T-101 to recover. Stop the API with Ctrl+C afterward. Never put credential values in files, command arguments, or prompts.

## Optional MCP client

Adapt [mcp.example.json](examples/mcp.example.json) to a client supporting local stdio servers. Replace the reference and three absolute-path placeholders. Keep tool approval enabled where supported.

Without `--ticket-id`, `ticket_mcp.py` serves MCP. Call `get_ticket` with `{"ticket_id":"T-101"}`. Terminal mode bypasses MCP but uses the same lookup. Windows JSON paths require escaped backslashes, for example `C:\\Tools\\op.exe`. Find your interpreter with `python -c "import sys; print(sys.executable)"`.

## Troubleshooting

| Error | Recovery |
| --- | --- |
| Command/file not found | Check CLI PATH, interpreter, working folder, and `.env.demo` filename. |
| CLI authorization / `credential_unavailable` | Check vault permissions and the reference privately. Use `op run`. |
| `api_unavailable` | Start the local API. |
| `api_auth_rejected` | Match the API and vault credentials privately, then relaunch. |
| `invalid_ticket_id` / `ticket_not_found` | Use T-101 or T-102. |
| `invalid_response` | Check the synthetic API response privately. |

Exit codes: 0 success, 1 tool failure, 2 setup/argument error. Never print environment variables to debug credentials.

## Code and boundaries

- `ticket_mcp.py`: validated lookup, terminal entry point, and MCP registration.
- `demo_api.py`: independent service that checks the token and serves synthetic data.
- `smoke_mcp.py` and `tests/`: rehearsal and boundary/integration tests.
- `package_mcp.py`: builds the source ZIP from an explicit allowlist.

The caller supplies only a ticket ID. The tool restricts requests to loopback, blocks redirects/proxies, bounds response size, and returns selected fields. These checks do not provide host isolation or per-user authorization.

The process still holds a plaintext credential. Relaunch after a vault edit and revoke compromised keys at their issuing service. This demo does not implement agent identity or general prompt-injection protection. Use OAuth or managed identity where appropriate.

Fixture tests run on macOS. Windows/Linux execution and the current live CLI flow remain unverified. Fixture tests do not prove vault access or model behavior.

AI assistance contributed to code and documentation. This demo contains only synthetic data and no employer code.
