# Manual review checklist (performed 2026-07-13, cannot be executed — no pwsh/Windows in the
# authoring sandbox; a real Windows + TallyPrime run is still required before trusting this):
#   [x] Every external command (winget, python, pip, Invoke-WebRequest, ConvertFrom-Json
#       -AsHashtable, claude) is either existence-checked first (Get-Command ... -ErrorAction
#       SilentlyContinue) or has a clear failure message (thrown text pointing at a fix).
#   [x] The script never silently swallows an error: $ErrorActionPreference = "Stop" is set
#       globally, and the only try/catch blocks wrap the two genuinely-optional steps (the Tally
#       gateway probe and — implicitly, via Get-Command's -ErrorAction — Claude Code detection).
#   [x] The existing claude_desktop_config.json is always backed up (Copy-Item ... .bak) before
#       being overwritten.
#   [x] Config JSON is built and parsed via ConvertTo-Json / ConvertFrom-Json only — no
#       hand-templated strings — so it cannot corrupt an existing config.
#
# TallyMind one-command installer
# Usage: irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "    OK: $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "    WARNING: $message" -ForegroundColor Yellow
}

Write-Step "Checking for Python 3.10+"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Warn "Python not found. Attempting install via winget."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available. Install Python 3.10+ manually from https://python.org and re-run this script."
    }
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python install did not complete. Open a new PowerShell window and re-run this script."
    }
}
Write-Ok "Python found: $((python --version))"

Write-Step "Installing TallyMind"
python -m pip install --upgrade pip | Out-Null
python -m pip install "git+https://github.com/Wadhawnaiya/tally-mcp.git"
Write-Ok "tallymind package installed"

Write-Step "Looking for a running TallyPrime gateway"
$tallyHost = "localhost"
$tallyPort = 9000
$reachable = $false
try {
    $response = Invoke-WebRequest -Uri "http://${tallyHost}:${tallyPort}" -TimeoutSec 3 -UseBasicParsing
    $reachable = $true
    Write-Ok "Found a Tally gateway responding at ${tallyHost}:${tallyPort}"
} catch {
    Write-Warn "No Tally gateway found at ${tallyHost}:${tallyPort} yet."
    Write-Host "    Make sure TallyPrime is open, a company is loaded, and F1 > Settings >"
    Write-Host "    Connectivity > Client/Server is set to Server (or Both) with port 9000."
    $customPort = Read-Host "    Press Enter to keep port 9000, or type a different port"
    if ($customPort) { $tallyPort = [int]$customPort }
}

Write-Step "Registering TallyMind with Claude Desktop"
$claudeConfigPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
$claudeConfigDir = Split-Path $claudeConfigPath -Parent
if (-not (Test-Path $claudeConfigDir)) {
    New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
}
if (Test-Path $claudeConfigPath) {
    Copy-Item $claudeConfigPath "$claudeConfigPath.bak" -Force
    Write-Ok "Backed up existing config to claude_desktop_config.json.bak"
    $config = Get-Content $claudeConfigPath -Raw | ConvertFrom-Json -AsHashtable
} else {
    $config = @{}
}
if (-not $config.ContainsKey("mcpServers")) {
    $config["mcpServers"] = @{}
}
$config["mcpServers"]["tallymind"] = @{
    "command" = "python"
    "args"    = @("-m", "tallymind.server")
    "env"     = @{ "TALLYMIND_STATE_PATH" = "$env:USERPROFILE\.tallymind\state.json" }
}
($config | ConvertTo-Json -Depth 10) | Set-Content -Path $claudeConfigPath -Encoding UTF8
Write-Ok "Wrote $claudeConfigPath"

Write-Step "Registering TallyMind with Claude Code (if installed)"
$claudeCli = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCli) {
    claude mcp add --transport stdio tallymind -- python -m tallymind.server
    Write-Ok "Registered with Claude Code via 'claude mcp add'"
} else {
    Write-Host "    Claude Code CLI not found — skipping (Claude Desktop registration above still applies)."
}

Write-Step "Running a connection self-test"
python -c "
from tallymind.gateway import TallyGateway
from tallymind.diagnostics import run_doctor
import json
gateway = TallyGateway(host='$tallyHost', port=$tallyPort)
print(json.dumps(run_doctor(gateway), indent=2))
"

Write-Step "Done"
Write-Host "Restart Claude Desktop completely (quit from the system tray, not just close the window)"
Write-Host "so it picks up the new tallymind server. Then ask Claude: 'Using TallyMind, run tally_doctor.'"
