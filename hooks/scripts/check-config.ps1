# tvfetch SessionStart hook (Windows PowerShell variant)
# Non-blocking: only prints warnings, never fails the session.

$SkillDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# 1. Python check
try {
    $pyVersion = python --version 2>&1
    $minor = python -c "import sys; print(sys.version_info.minor)" 2>$null
    if ($minor -lt 11) {
        Write-Host "TVFETCH WARNING: Python 3.11+ required, found $pyVersion"
    }
} catch {
    Write-Host "TVFETCH WARNING: Python not found. Install Python 3.11+"
}

# 2. tvfetch check
python -c "import tvfetch" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "TVFETCH WARNING: tvfetch not installed. Run: pip install -e $SkillDir"
}

# 3. Auth status
python "$SkillDir\scripts\lib\config.py" --check-auth-quiet 2>$null

exit 0
