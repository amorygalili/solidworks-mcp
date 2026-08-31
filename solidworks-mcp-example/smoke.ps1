<#
.SYNOPSIS
    Preflight for the solidworks-mcp server, before you wire a client to it.

.DESCRIPTION
    Runs three checks, cheapest first:

      1. The exact command line from .mcp.json actually launches (uv resolves the
         project, the venv exists, the console script is installed).
      2. A real MCP handshake over stdio returns tool schemas. Needs no SOLIDWORKS.
      3. --doctor reports install and session health. This is the only step that
         looks at the machine; it does not launch or attach to SOLIDWORKS.

    Use -SkipDoctor to stop after step 2.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\smoke.ps1
#>
[CmdletBinding()]
param(
    [string] $ServerDir = "C:/projects/cad-mcp-comparisons/solidworks-mcp",
    [switch] $SkipDoctor
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $ServerDir "pyproject.toml"))) {
    Write-Host "No pyproject.toml under $ServerDir." -ForegroundColor Red
    Write-Host "Pass -ServerDir with the path to your solidworks-mcp checkout."
    exit 1
}

# Mirror .mcp.json so this script fails for the same reasons a client would.
$config = Get-Content (Join-Path $PSScriptRoot ".mcp.json") -Raw | ConvertFrom-Json
foreach ($name in $config.mcpServers.solidworks.env.PSObject.Properties.Name) {
    Set-Item -Path "env:$name" -Value $config.mcpServers.solidworks.env.$name
}
Write-Host "SWMCP_ALLOWED_ROOTS = $env:SWMCP_ALLOWED_ROOTS" -ForegroundColor DarkGray
Write-Host "SWMCP_TOOL_TIER     = $env:SWMCP_TOOL_TIER" -ForegroundColor DarkGray

Write-Host "`n[1/3] Launching the server binary..." -ForegroundColor Cyan
$manifest = & uv run --directory $ServerDir solidworks-mcp --print-manifest
if ($LASTEXITCODE -ne 0) {
    Write-Host "The server did not start. Install it first:" -ForegroundColor Red
    Write-Host "  cd $ServerDir; uv venv; uv pip install -e ."
    exit 1
}
$tools = ($manifest | ConvertFrom-Json).tools
Write-Host "      ok - $($tools.Count) operations in the manifest" -ForegroundColor Green

Write-Host "`n[2/3] MCP handshake over stdio..." -ForegroundColor Cyan
& uv run --directory $ServerDir python scripts/mcp_handshake.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "      handshake failed" -ForegroundColor Red
    exit 1
}
Write-Host "      ok - a client can list tools and read their schemas" -ForegroundColor Green

if ($SkipDoctor) {
    Write-Host "`nSkipping --doctor. The config in .mcp.json is usable." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[3/3] Install and session health (--doctor)..." -ForegroundColor Cyan
$health = & uv run --directory $ServerDir solidworks-mcp --doctor
Write-Host $health
$parsed = $health | ConvertFrom-Json
if ($parsed.result.healthy) {
    Write-Host "      healthy" -ForegroundColor Green
} else {
    Write-Host "      not healthy yet:" -ForegroundColor Yellow
    foreach ($issue in $parsed.result.issues) { Write-Host "        - $issue" -ForegroundColor Yellow }
}
Write-Host "`nPoint your MCP client at $PSScriptRoot and it will pick up .mcp.json." -ForegroundColor Green
