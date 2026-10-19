# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
param(
    [switch]$SkipCodexRegistration
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$RunServer = Join-Path $ProjectRoot 'run_server.ps1'
$AddonSource = Join-Path $ProjectRoot 'cad_addon\KimmCadMcp'
$KimmCadCandidates = if ($env:KIMM_CAD_EXE) {
    @($env:KIMM_CAD_EXE)
} else {
    @(
        (Join-Path $env:LOCALAPPDATA 'Programs\KIMM\KIMM-CAD V26\KIMM-CAD V26.exe'),
        (Join-Path $env:ProgramFiles 'KIMM\KIMM-CAD V26\KIMM-CAD V26.exe')
    )
}
$KimmCadExe = $KimmCadCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $KimmCadExe) {
    throw 'KIMM-CAD V26 실행 파일을 찾지 못했습니다. KIMM_CAD_EXE에 KIMM-CAD V26.exe 경로를 지정하세요.'
}
$KimmCadRoot = Split-Path -Parent $KimmCadExe
$ManifestPath = Join-Path $KimmCadRoot 'build-manifest.json'
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf) -or
    (Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json).product -ne 'KIMM-CAD V26') {
    throw "KIMM-CAD V26 설치 폴더가 아닙니다: $KimmCadRoot"
}
$ProfileRoot = if ($env:KIMM_CAD_PROFILE_ROOT) { [IO.Path]::GetFullPath($env:KIMM_CAD_PROFILE_ROOT) } else { $KimmCadRoot }
$KimmCadModRoot = Join-Path $ProfileRoot 'profile\data\Mod'
$AddonLink = Join-Path $KimmCadModRoot 'KimmCadMcp'
$AddonMarker = Join-Path $AddonLink 'project_path.txt'
$LegacyAddons = @(
    (Join-Path $env:APPDATA 'FreeCAD\Mod\KimmCadMcp'),
    (Join-Path $env:APPDATA 'KIMM-CAD\Mod\KimmCadMcp')
)
Set-Location $ProjectRoot

function Test-PythonEnvironment {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) { return $false }
    & $VenvPython -c "import sys, mcp, kimm_cad_mcp; from pathlib import Path; sys.exit(0 if Path(kimm_cad_mcp.__file__).resolve().parents[2].samefile(sys.argv[1]) else 2)" $ProjectRoot 2>$null
    return $LASTEXITCODE -eq 0
}

function Find-CodexExecutable {
    $codexBin = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
    $candidates = @()
    if (Test-Path -LiteralPath $codexBin -PathType Container) {
        $candidates += Get-ChildItem -LiteralPath $codexBin -Filter 'codex.exe' -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -ExpandProperty FullName
    }
    $command = Get-Command codex.exe -ErrorAction SilentlyContinue
    if ($command -and $candidates -notcontains $command.Source) {
        $candidates += $command.Source
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

Write-Host '[1/3] Python environment'
if (Test-PythonEnvironment) {
    Write-Host '  OK - already installed; skipped.'
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    uv sync --reinstall-package kimm-cad-mcp
    if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
    Write-Host '  INSTALLED - project-local .venv'
} else {
    python -m venv --clear .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
    & $VenvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Python package installation failed.' }
    Write-Host '  INSTALLED - project-local .venv'
}
if (-not (Test-PythonEnvironment)) { throw 'Project-local Python environment verification failed.' }

Write-Host '[2/3] Codex MCP registration'
if ($SkipCodexRegistration) {
    Write-Host '  SKIPPED - Qwen/Open WebUI setup does not require Codex registration.'
} else {
    $Codex = Find-CodexExecutable
    if (-not $Codex) { throw 'codex.exe was not found.' }
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $mcpDetails = (& $Codex mcp get kimm-cad 2>&1 | Out-String)
    $mcpExists = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $savedErrorPreference
    $normalizedDetails = $mcpDetails.Replace('/', '\').ToLowerInvariant()
    $normalizedRunServer = $RunServer.Replace('/', '\').ToLowerInvariant()
    if ($mcpExists -and $normalizedDetails.Contains($normalizedRunServer)) {
        Write-Host '  OK - already registered; skipped.'
    } else {
        if ($mcpExists) {
            & $Codex mcp remove kimm-cad | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'Existing kimm-cad MCP removal failed.' }
        }
        & $Codex mcp add kimm-cad -- powershell.exe -NoProfile -ExecutionPolicy Bypass -File $RunServer | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
        Write-Host '  INSTALLED - kimm-cad STDIO MCP'
    }
}

Write-Host '[3/3] KIMM-CAD GUI add-on'
foreach ($LegacyAddon in $LegacyAddons) {
    if (-not (Test-Path -LiteralPath $LegacyAddon)) { continue }
    $legacyItem = Get-Item -LiteralPath $LegacyAddon -Force
    $legacyMarker = Join-Path $LegacyAddon 'project_path.txt'
    $legacyOwned = $false
    if ($legacyItem.LinkType -eq 'Junction') {
        $legacyOwned = @($legacyItem.Target) -contains $AddonSource
    } elseif (Test-Path -LiteralPath $legacyMarker -PathType Leaf) {
        $legacyOwned = (Get-Content -Raw -Encoding UTF8 -LiteralPath $legacyMarker).Trim() -eq $ProjectRoot
    }
    if ($legacyOwned) {
        if ($legacyItem.LinkType -eq 'Junction') {
            [System.IO.Directory]::Delete($LegacyAddon)
        } else {
            Remove-Item -LiteralPath $LegacyAddon -Recurse -Force
        }
        Write-Host '  CLEANED - obsolete FreeCAD-path loader'
    }
}
New-Item -ItemType Directory -Force $KimmCadModRoot | Out-Null
$addonInstalled = $false
$existing = Get-Item -LiteralPath $AddonLink -Force -ErrorAction SilentlyContinue
if ($existing -and -not $existing.LinkType -and (Test-Path -LiteralPath $AddonMarker -PathType Leaf)) {
    $markedProject = (Get-Content -Raw -Encoding UTF8 -LiteralPath $AddonMarker).Trim()
    $sameProject = [IO.Path]::GetFullPath($markedProject).TrimEnd('\') -eq [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
    $sameFiles = $true
    foreach ($fileName in @('Init.py', 'InitGui.py', 'KimmCadMcpLocator.py')) {
        $sourceFile = Join-Path $AddonSource $fileName
        $installedFile = Join-Path $AddonLink $fileName
        if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf) -or
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($sourceFile)) -ne
                [Convert]::ToBase64String([IO.File]::ReadAllBytes($installedFile))) {
            $sameFiles = $false
        }
    }
    $addonInstalled = $sameProject -and $sameFiles
}
if ($addonInstalled) {
    Write-Host '  OK - already installed; skipped.'
} else {
    if ($existing) {
        $ownedJunction = $existing.LinkType -eq 'Junction' -and @($existing.Target) -contains $AddonSource
        $ownedDirectory = -not $existing.LinkType -and
            (Test-Path -LiteralPath $AddonMarker -PathType Leaf) -and
            ([IO.Path]::GetFullPath((Get-Content -Raw -Encoding UTF8 -LiteralPath $AddonMarker).Trim()).TrimEnd('\') -eq
                [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\'))
        if (-not ($ownedJunction -or $ownedDirectory)) {
            throw "Add-on path exists but is not owned by this project: $AddonLink"
        }
        $resolvedModRoot = [IO.Path]::GetFullPath($KimmCadModRoot).TrimEnd('\')
        $resolvedAddon = [IO.Path]::GetFullPath($AddonLink).TrimEnd('\')
        if (-not $resolvedAddon.StartsWith($resolvedModRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace add-on outside the KIMM-CAD Mod directory: $resolvedAddon"
        }
        if ($ownedJunction) {
            [System.IO.Directory]::Delete($AddonLink)
        } else {
            Remove-Item -LiteralPath $AddonLink -Recurse -Force
        }
    }
    New-Item -ItemType Directory -Force $AddonLink | Out-Null
    Copy-Item -LiteralPath (Join-Path $AddonSource 'Init.py') -Destination $AddonLink
    Copy-Item -LiteralPath (Join-Path $AddonSource 'InitGui.py') -Destination $AddonLink
    Copy-Item -LiteralPath (Join-Path $AddonSource 'KimmCadMcpLocator.py') -Destination $AddonLink
    [IO.File]::WriteAllText($AddonMarker, $ProjectRoot, (New-Object Text.UTF8Encoding($false)))
    Write-Host '  INSTALLED - KIMM-CAD autostart loader'
}

Write-Host 'SETUP COMPLETE'
Write-Host "Project: $ProjectRoot"
if (-not $SkipCodexRegistration) {
    Write-Host 'Restart Codex to load the new MCP registration.'
}
Write-Host 'Restart KIMM-CAD to verify automatic RPC startup.'
