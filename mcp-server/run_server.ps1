# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw "가상환경이 없습니다. 먼저 setup.ps1을 실행하세요."
}
& $Python -m kimm_cad_mcp.server
