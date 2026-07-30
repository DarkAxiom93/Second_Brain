[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$handoff = Join-Path $repoRoot "docs\CHAT_HANDOFF.md"
$content = Get-Content -LiteralPath $handoff -Raw
if ([string]::IsNullOrWhiteSpace($content)) { throw "Chat handoff is missing or blank." }
$content | Set-Clipboard
Write-Host "Chat handoff copied to the Windows clipboard."
