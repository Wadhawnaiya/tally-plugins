# Manual review checklist (performed 2026-07-13, cannot be executed — no pwsh/Windows in the
# authoring sandbox; a real Windows + TallyPrime run is still required before trusting this):
#   [x] Every external command (winget, python, pip, git, Invoke-WebRequest, ConvertFrom-Json,
#       claude) is either existence-checked first (Get-Command ... -ErrorAction
#       SilentlyContinue) or has a clear failure message (thrown text pointing at a fix).
#   [x] The script never silently swallows an error: $ErrorActionPreference = "Stop" is set
#       globally, and the only try/catch blocks wrap the two genuinely-optional steps (the Tally
#       gateway probe and — implicitly, via Get-Command's -ErrorAction — Claude Code detection).
#   [x] The existing claude_desktop_config.json is always backed up (Copy-Item ... .bak) before
#       being overwritten.
#   [x] Config JSON is built and parsed via ConvertTo-Json / ConvertFrom-Json (PSCustomObject +
#       Add-Member — no -AsHashtable, so it works on stock Windows PowerShell 5.1, not just
#       PowerShell 6.0+) only — no hand-templated strings — so it cannot corrupt an existing
#       config.
#   [x] Fixed in the 2026-07-13 review pass: config parsing no longer uses ConvertFrom-Json
#       -AsHashtable (PS 6.0+ only; threw a raw parameter-binding error on the default Windows
#       PowerShell 5.1); pip install, claude mcp add, and the connection self-test now check
#       $LASTEXITCODE instead of silently assuming success; Python's actual version is checked
#       (>= 3.10), not just that some python exists; git is existence-checked before the pip
#       install step that needs it; the custom Tally port prompt validates numeric input instead
#       of crashing on a raw [int] cast.
#
# TallyMind one-command installer
# Usage: irm https://raw.githubusercontent.com/Wadhawnaiya/tally-plugins/main/install.ps1 | iex

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

function Install-PythonViaWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available. Install Python 3.10+ manually from https://python.org and re-run this script."
    }
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $script:python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $script:python) {
        throw "Python install did not complete. Open a new PowerShell window and re-run this script."
    }
}

Write-Step "Checking for Python 3.10+"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Warn "Python not found. Attempting install via winget."
    Install-PythonViaWinget
}
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Found python, but it is older than the required 3.10. Attempting to install a newer version via winget."
    Install-PythonViaWinget
    python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Python is still older than 3.10 after attempting a winget install. TallyMind requires Python 3.10+ — install it manually from https://python.org, open a new PowerShell window, and re-run this script. Continuing anyway."
    }
}
Write-Ok "Python found: $((python --version))"

Write-Step "Installing TallyMind"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    throw "git is not available, but it is required to install tallymind from GitHub. Install Git for Windows from https://git-scm.com/download/win and re-run this script."
}
python -m pip install --upgrade pip | Out-Null
python -m pip install "git+https://github.com/Wadhawnaiya/tally-plugins.git"
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed (exit code $LASTEXITCODE). Check the error above, make sure git is installed, and re-run this script."
}
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
    if ($customPort) {
        $parsedPort = 0
        if ([int]::TryParse($customPort, [ref]$parsedPort)) {
            $tallyPort = $parsedPort
        } else {
            Write-Warn "'$customPort' is not a valid port number. Keeping the default port 9000."
        }
    }
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
    $config = Get-Content $claudeConfigPath -Raw | ConvertFrom-Json
} else {
    $config = [PSCustomObject]@{}
}
if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
    $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([PSCustomObject]@{}) -Force
}
$tallymindEntry = [PSCustomObject]@{
    command = "python"
    args    = @("-m", "tallymind.server")
    env     = [PSCustomObject]@{ TALLYMIND_STATE_PATH = "$env:USERPROFILE\.tallymind\state.json" }
}
$config.mcpServers | Add-Member -NotePropertyName "tallymind" -NotePropertyValue $tallymindEntry -Force
($config | ConvertTo-Json -Depth 10) | Set-Content -Path $claudeConfigPath -Encoding UTF8
Write-Ok "Wrote $claudeConfigPath"

Write-Step "Registering TallyMind with Claude Code (if installed)"
$claudeCli = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCli) {
    claude mcp add --transport stdio tallymind -- python -m tallymind.server
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Registered with Claude Code via 'claude mcp add'"
    } else {
        Write-Warn "claude mcp add exited with code $LASTEXITCODE (it may already be registered) — Claude Desktop registration above still applies."
    }
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
if ($LASTEXITCODE -ne 0) {
    Write-Warn "The connection self-test above did not run cleanly. TallyMind is installed and registered with Claude, but check the error above before assuming Tally connectivity is working."
}

Write-Step "Done"
Write-Host "Restart Claude Desktop completely (quit from the system tray, not just close the window)"
Write-Host "so it picks up the new tallymind server. Then ask Claude: 'Using TallyMind, run tally_doctor.'"
