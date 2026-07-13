# TallyMind MCP

A Tally MCP server that fixes the six gaps every other one has: hardcoded
`localhost`, no connection diagnostics, no dry-run/undo safety on writes, no
GST-specific tools, session state lost on restart, and manual
`claude_desktop_config.json` editing.

## Install (Windows, same PC as TallyPrime + Claude Desktop)

```powershell
irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex
```

This installs Python if needed, installs TallyMind, detects your running
Tally gateway, registers the server with Claude Desktop (and Claude Code, if
present) without hand-editing any JSON, and runs a connectivity check.

## Requirements

- TallyPrime Silver/Gold (not Educational — it silently truncates date
  ranges), with the HTTP/XML gateway enabled: `F1 > Settings > Connectivity >
  Client/Server = Server (or Both)`, port `9000` by default.
- Windows, since TallyPrime itself is Windows-only.
- Claude Desktop and/or Claude Code.

## Development

```bash
pip install -e ".[dev]"
pytest
```

`install.ps1` is Windows-only and cannot be exercised in a Linux dev
environment; review it manually and test on a real Windows + TallyPrime
machine before relying on it.

## License

Proprietary — CA Shailesh S Wadhawaniya.
