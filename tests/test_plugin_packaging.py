import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "cowork-plugin"


def test_plugin_json_is_valid_and_points_at_mcp_config() -> None:
    data = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "tallymind-mcp-plugin"
    assert data["mcpServers"] == "./mcp_config.json"
    assert data["skills"] == "./skills/"


def test_mcp_config_and_mcp_json_agree_on_command() -> None:
    # "python" (not "python3"): Windows typically has no python3 alias on PATH,
    # only python, and install.ps1's Claude Desktop registration already uses
    # "python" — this project's target platform is Windows CAs running TallyPrime.
    mcp_config = json.loads((PLUGIN_DIR / "mcp_config.json").read_text(encoding="utf-8"))
    mcp_json = json.loads((PLUGIN_DIR / ".mcp.json").read_text(encoding="utf-8"))
    for data in (mcp_config, mcp_json):
        entry = data["mcpServers"]["tallymind"]
        assert entry["command"] == "python"
        assert entry["args"] == ["-m", "tallymind.server"]


def test_skill_md_exists_and_names_the_plugin() -> None:
    content = (PLUGIN_DIR / "skills" / "tally-mind" / "SKILL.md").read_text(encoding="utf-8")
    assert "tally-mind" in content
    assert "tally_doctor" in content
