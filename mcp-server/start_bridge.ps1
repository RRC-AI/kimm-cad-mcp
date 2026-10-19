# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python 환경이 없습니다. 먼저 install.ps1을 실행하세요.'
}
& $Python -c 'from kimm_cad_mcp.bridge_client import ensure_bridge; ensure_bridge(timeout=60)'
if ($LASTEXITCODE -ne 0) { throw 'KIMM-CAD V26 브리지 시작에 실패했습니다.' }
Write-Host 'KIMM-CAD V26 브리지가 연결되었습니다.'
