[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$scriptsRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $scriptsRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
. (Join-Path $scriptsRoot "Invoke-IsolatedProcess.ps1")

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

$first = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
    "-c", "import sys; print('stdout-one'); print('stderr-one', file=sys.stderr)"
) -WorkingDirectory $repoRoot
Assert-True ($first.ExitCode -eq 0) "Successful command exit code was not preserved."
Assert-True ($first.StandardOutput -match "stdout-one") "stdout was not preserved."
Assert-True ($first.StandardError -match "stderr-one") "stderr was not preserved."

$highOutput = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
    "-c", "import sys; [print(f'out-{i}') for i in range(4000)]; [print(f'err-{i}', file=sys.stderr) for i in range(4000)]"
) -WorkingDirectory $repoRoot
Assert-True ($highOutput.ExitCode -eq 0) "High-output command failed."
Assert-True ($highOutput.StandardOutput -match "out-3999") "High-volume stdout was incomplete."
Assert-True ($highOutput.StandardError -match "err-3999") "High-volume stderr was incomplete."

$later = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
    "-c", "import sys; print('stdout-later'); print('stderr-later', file=sys.stderr)"
) -WorkingDirectory $repoRoot
Assert-True ($later.ExitCode -eq 0) "Command after high output failed."
Assert-True ($later.StandardOutput -match "stdout-later") "Later stdout was unusable."
Assert-True ($later.StandardError -match "stderr-later") "Later stderr was unusable."

$failure = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
    "-c", "import sys; print('expected failure', file=sys.stderr); raise SystemExit(23)"
) -WorkingDirectory $repoRoot
Assert-True ($failure.ExitCode -eq 23) "Nonzero exit code was not preserved."
Assert-True ($failure.StandardError -match "expected failure") "Failing stderr was swallowed."

$ranLater = $false
try {
    $result = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
        "-c", "raise SystemExit(19)"
    ) -WorkingDirectory $repoRoot
    if ($result.ExitCode -ne 0) { throw "stage failed" }
    $ranLater = $true
    $null = Invoke-IsolatedProcess -FilePath $python -ArgumentList @(
        "-c", "print('must-not-run')"
    ) -WorkingDirectory $repoRoot
    throw "The deliberate failure unexpectedly returned success."
} catch {
    Assert-True (-not $ranLater) "A failed command did not stop sequential execution."
}

Write-Host "Focused isolated-process verification passed."
