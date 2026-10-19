# KIMM-CAD MCP

자연어 요청으로 **KIMM-CAD V26**(FreeCAD 기반 CAD) 화면에 3D 형상을 만들고 검증하는 MCP 서버와, DXF·DWG·IFC·벡터 PDF 도면 파일을 STEP/STL 3D 모델로 바꾸는 **도면 → 3D 변환 skill**을 모은 저장소입니다.

> 한국기계연구원(KIMM) AI Agent 전략연구사업 결과물

## 시연 영상

MCP로 KIMM-CAD V26에 볼트 구멍 4개짜리 원형 플랜지를 만드는 과정입니다.

https://github.com/user-attachments/assets/06a637b9-3590-4a04-92d5-7be058c77afd

## 다운로드

[**Releases**](https://github.com/RRC-AI/kimm-cad-mcp/releases/latest)에서 설치 파일을 받을 수 있습니다.

| 파일 | 내용 |
|---|---|
| `KIMM-CAD-V26.1-Setup.zip` | KIMM-CAD V26.1 Windows 64-bit 설치 파일 |
| `kimm-cad-mcp_share_V26.1.zip` | MCP 서버 설치 패키지 (`mcp-server/`와 동일) |
| `drawing-to-3d_share_V26.1.zip` | 도면 → 3D 변환기 설치 패키지 (`drawing-to-3d/`와 동일) |

## 구성

```
kimm-cad-mcp/
├── mcp-server/        KIMM-CAD V26용 MCP 서버 (Python, MCP SDK)
│   ├── src/kimm_cad_mcp/   MCP 도구 정의 · 요청 파서 · 생성 전략 선택
│   ├── cad_bridge/         KIMM-CAD 내부에서 실행되는 명령 처리 브리지
│   ├── cad_addon/          KIMM-CAD 시작 시 브리지를 자동 실행하는 애드온
│   ├── generated_scripts/  검증된 CAD 계획(plan) 실행 스크립트
│   └── tests/
├── drawing-to-3d/     도면 파일 → 3D(STEP/STL) 변환기 + Agent skill
│   ├── .claude/skills/drawing-file-to-3d/   이식 가능한 skill (SKILL.md, convert.py)
│   ├── examples/           예제 도면 (DXF, 벡터 PDF)
│   ├── input/  output/     변환 입력·결과 폴더
│   └── 변환.bat · 설치.bat · 투명도조절.bat
├── docs/              예시 프롬프트
├── LICENSE            LGPL-2.1-or-later
└── NOTICE.md          저작권 · FreeCAD 관계 · 서드파티 라이선스
```

## 요구 사항

- Windows 10/11, KIMM-CAD V26 (기본 설치 위치 `%LOCALAPPDATA%\Programs\KIMM\KIMM-CAD V26`)
- Python 3.10 이상 (도면 변환기는 3.11 이상 권장)
- MCP 클라이언트 (Codex, Claude Code 등)
- DWG 입력 시 [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) 별도 설치

## 빠른 시작

### 1. MCP 서버

```powershell
cd mcp-server
.\INSTALL.cmd
```

`SETUP COMPLETE`가 표시되면 MCP 클라이언트와 KIMM-CAD V26을 다시 시작합니다. 클라이언트 등록 예시는 [`mcp-server/mcp.json.example`](mcp-server/mcp.json.example)에 있습니다. 자세한 내용은 [`mcp-server/README.md`](mcp-server/README.md)를 참고하세요.

제공 도구: `cad_status`, `cad_get_capabilities`, `cad_get_plan_schema`, `cad_execute_verified_plan`, `cad_analyze`, `cad_create`, `cad_create_verified_basic_shape`, `cad_import_verified_step`, `cad_validate_active_model`, `cad_clear`

### 2. 도면 → 3D 변환기

```powershell
cd drawing-to-3d
.\INSTALL.cmd
```

변환할 도면을 `input` 폴더에 넣고 에이전트에게 요청하거나 `변환.bat`에 끌어다 놓습니다. 결과는 `output` 폴더에 생성됩니다. 자세한 내용은 [`drawing-to-3d/README.md`](drawing-to-3d/README.md)를 참고하세요.

### 3. 테스트

```powershell
cd mcp-server
python -m pytest -q
```

## 동작 구조

MCP 서버가 `runtime/inbox`에 JSON 명령을 기록하면, KIMM-CAD 안에서 실행되는 브리지(`cad_bridge/bridge_bootstrap.py`)가 Qt GUI 스레드에서 명령을 처리합니다. 처리 결과는 `runtime/outbox`로 돌려줍니다. 생성된 형상은 FCStd·STEP으로 저장하고, 치수와 유효성(`Shape.isValid()`)을 검증한 뒤 등각 보기로 표시합니다.

## 라이선스

Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)

이 저장소는 KIMM-CAD의 기반인 FreeCAD와 같은 **[GNU LGPL v2.1 or later](./LICENSE)** 로 배포됩니다. FreeCAD·KIMM-CAD 본체는 포함되어 있지 않습니다. 외부 의존성(PyMuPDF는 AGPL-3.0, ODA File Converter는 독점 라이선스)에 관한 주의 사항은 [NOTICE.md](./NOTICE.md)를 확인하세요.
