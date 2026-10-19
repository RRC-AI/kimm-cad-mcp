# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
param(
    [string]$PythonCommand = 'python',
    [switch]$SkipDependencies,
    [switch]$Relink
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$skillName = 'drawing-file-to-3d'
$projectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$skillRoot = Join-Path $projectRoot '.claude\skills\drawing-file-to-3d'
$skillManifest = Join-Path $skillRoot 'SKILL.md'
$converterScript = Join-Path $skillRoot 'scripts\convert.py'
$requirementsPath = Join-Path $projectRoot 'requirements.txt'
$userProfile = [Environment]::GetFolderPath('UserProfile')
$skillsDirectory = Join-Path $userProfile '.agents\skills'
$linkPath = Join-Path $skillsDirectory $skillName

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        return (Resolve-Path -LiteralPath $Path).Path.TrimEnd('\')
    }
    catch {
        return [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    }
}

function Test-JunctionTarget {
    param(
        [Parameter(Mandatory = $true)]$Item,
        [Parameter(Mandatory = $true)][string]$ExpectedTarget
    )

    if ($Item.LinkType -ne 'Junction') {
        return $false
    }

    $expected = Get-NormalizedPath -Path $ExpectedTarget
    foreach ($target in @($Item.Target)) {
        if ((Get-NormalizedPath -Path ([string]$target)) -ieq $expected) {
            return $true
        }
    }
    return $false
}

if (-not (Test-Path -LiteralPath $skillManifest -PathType Leaf)) {
    throw "Skill manifest not found: $skillManifest"
}
if (-not (Test-Path -LiteralPath $converterScript -PathType Leaf)) {
    throw "Converter script not found: $converterScript"
}
if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "Requirements file not found: $requirementsPath"
}

Write-Host ''
Write-Host '============================================'
Write-Host ' Drawing file to 3D - Codex skill installer'
Write-Host '============================================'
Write-Host "Project : $projectRoot"
Write-Host "Skill   : $skillRoot"
Write-Host ''

if (-not $SkipDependencies) {
    Write-Host "[1/3] Checking Python command: $PythonCommand"
    & $PythonCommand --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python was not found. Install Python 3.11 or newer and run this installer again."
    }

    Write-Host "[2/3] Installing Python dependencies: $requirementsPath"
    & $PythonCommand -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed with exit code $LASTEXITCODE."
    }

    & $PythonCommand -c "import cadquery, ezdxf, fitz, ifcopenshell; print('Python dependencies verified')"
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency verification failed with exit code $LASTEXITCODE."
    }
}
else {
    Write-Host '[1/3] Python dependency installation skipped.'
    Write-Host '[2/3] Python dependency verification skipped.'
}

Write-Host '[3/3] Connecting the project skill to Codex.'
New-Item -ItemType Directory -Path $skillsDirectory -Force | Out-Null

if (Test-Path -LiteralPath $linkPath) {
    $existing = Get-Item -LiteralPath $linkPath -Force
    if (Test-JunctionTarget -Item $existing -ExpectedTarget $skillRoot) {
        Write-Host "Skill is already connected: $linkPath -> $skillRoot"
    }
    else {
        if (-not $Relink) {
            throw "A different item already exists at '$linkPath'. If it is an old project junction, run '.\install.ps1 -Relink'."
        }
        if ($existing.LinkType -ne 'Junction') {
            throw "Refusing to replace '$linkPath' because it is not a Junction. Check and move it manually first."
        }

        Remove-Item -LiteralPath $linkPath -Force
        New-Item -ItemType Junction -Path $linkPath -Target $skillRoot | Out-Null
        Write-Host "Skill junction updated: $linkPath -> $skillRoot"
    }
}
else {
    New-Item -ItemType Junction -Path $linkPath -Target $skillRoot | Out-Null
    Write-Host "Skill connected: $linkPath -> $skillRoot"
}

$installedManifest = Join-Path $linkPath 'SKILL.md'
if (-not (Test-Path -LiteralPath $installedManifest -PathType Leaf)) {
    throw "Skill connection verification failed: $installedManifest"
}

$odaCandidates = @(
    'C:\Program Files\ODA\ODAFileConverter 26.8.0\ODAFileConverter.exe',
    'C:\Program Files\ODAFileConverter 26.8.0\ODAFileConverter.exe',
    'C:\Program Files\ODAFileConverter\ODAFileConverter.exe'
)
$odaAvailable = $false
foreach ($candidate in $odaCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $odaAvailable = $true
        break
    }
}

Write-Host ''
Write-Host '[Completed] drawing-file-to-3d skill is installed.'
Write-Host "Installed link: $linkPath"
Write-Host 'Restart Codex once so the skill list is refreshed.'
Write-Host "Converted files will be written to: $(Join-Path $projectRoot 'output')"
if (-not $odaAvailable) {
    Write-Warning 'ODA File Converter was not detected. DXF/PDF/IFC work normally, but DWG conversion needs ODA File Converter.'
}
