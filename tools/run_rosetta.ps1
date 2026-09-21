$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Write-Host "FTFL Rosetta Toolbox v0.2" -ForegroundColor Cyan
Write-Host "Repository: $repo"

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python was not found in PATH." }

& $py.Source "$PSScriptRoot\extract_dialogue.py" --repo "$repo"
if ($LASTEXITCODE -ne 0) { throw "Extraction failed." }

& $py.Source "$PSScriptRoot\build_alignment.py" --repo "$repo"
if ($LASTEXITCODE -ne 0) { throw "Alignment build failed." }

& $py.Source "$PSScriptRoot\validate_alignment.py" --repo "$repo"
if ($LASTEXITCODE -ne 0) { throw "Alignment validation failed." }

Write-Host "`nRosetta dataset ready." -ForegroundColor Green
Write-Host "reference\aligned\localization_alignment.csv"
Write-Host "reference\aligned\direct_reference_pairs.csv"
