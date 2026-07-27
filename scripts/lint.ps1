<#
.SYNOPSIS
    Local lint automation script using Ruff.

.DESCRIPTION
    Runs Ruff linter and formatter against the project source.
    By default it runs in CHECK mode (no files modified).
    Pass -Fix to auto-fix all safely fixable issues.
    Pass -Format to also apply Ruff's formatter (Black-compatible).

.PARAMETER Fix
    Auto-fix lint issues that Ruff can correct safely.

.PARAMETER Format
    Auto-format code using ruff format (implies -Fix).

.PARAMETER Path
    Target path(s) to lint. Defaults to the full project (.).

.EXAMPLE
    # Check only (CI mode)
    .\scripts\lint.ps1

.EXAMPLE
    # Fix lint issues
    .\scripts\lint.ps1 -Fix

.EXAMPLE
    # Fix lint issues AND reformat code
    .\scripts\lint.ps1 -Format

.EXAMPLE
    # Lint a specific directory only
    .\scripts\lint.ps1 -Fix -Path app
#>

param(
    [switch]$Fix,
    [switch]$Format,
    [string]$Path = "."
)

# --- Helpers -----------------------------------------------------------------
function Write-Header  { param($msg) Write-Host "`n$msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host $msg    -ForegroundColor Green }
function Write-Failure { param($msg) Write-Host $msg    -ForegroundColor Red }
function Write-Info    { param($msg) Write-Host $msg    -ForegroundColor Yellow }

# --- Ensure ruff is available ------------------------------------------------
if (-not (Get-Command ruff -ErrorAction SilentlyContinue)) {
    Write-Failure "ERROR: 'ruff' not found. Install it with:  pip install ruff"
    exit 1
}

$ruffVersion = ruff --version
Write-Info "Using $ruffVersion"

# --- Resolve mode flags ------------------------------------------------------
$exitCode   = 0
$checkArgs  = @($Path, "--output-format", "concise")
$formatArgs = @($Path)

if ($Fix -or $Format) {
    $checkArgs += "--fix"
    Write-Info "Mode: AUTO-FIX enabled"
} else {
    Write-Info "Mode: CHECK only (pass -Fix to auto-fix, -Format to also reformat)"
}

# --- Step 1: Lint ------------------------------------------------------------
Write-Header "==> Ruff Lint Check"
ruff check @checkArgs
$lintExit = $LASTEXITCODE

if ($lintExit -eq 0) {
    Write-Success "  Lint: OK"
} else {
    Write-Failure "  Lint: Issues found (exit $lintExit)"
    $exitCode = $lintExit
}

# --- Step 2: Format ----------------------------------------------------------
Write-Header "==> Ruff Format Check"

if ($Format) {
    ruff format @formatArgs
    $fmtExit = $LASTEXITCODE
    if ($fmtExit -eq 0) {
        Write-Success "  Format: Applied successfully"
    } else {
        Write-Failure "  Format: Failed (exit $fmtExit)"
        $exitCode = $fmtExit
    }
} else {
    # Check mode: report which files WOULD change without modifying them
    ruff format --check @formatArgs
    $fmtExit = $LASTEXITCODE
    if ($fmtExit -eq 0) {
        Write-Success "  Format: OK (no changes needed)"
    } else {
        Write-Failure "  Format: Files need reformatting - run with -Format to apply"
        if ($exitCode -eq 0) { $exitCode = $fmtExit }
    }
}

# --- Summary -----------------------------------------------------------------
Write-Header "==> Summary"
if ($exitCode -eq 0) {
    Write-Success "All checks passed!"
} else {
    Write-Failure "One or more checks failed. Exit code: $exitCode"
}

exit $exitCode
