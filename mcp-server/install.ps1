# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
param(
    [switch]$SkipCodexRegistration
)

$ErrorActionPreference = "Stop"

$setupScript = Join-Path $PSScriptRoot "setup.ps1"
if (-not (Test-Path -LiteralPath $setupScript -PathType Leaf)) {
    throw "setup.ps1 파일을 찾을 수 없습니다: $setupScript"
}

$setupArguments = @{}
if ($SkipCodexRegistration) {
    $setupArguments.SkipCodexRegistration = $true
}

& $setupScript @setupArguments

