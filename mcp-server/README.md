# kimm-cad-mcp

자연어 요청으로 KIMM-CAD V26 화면에 CAD 형상을 생성하는 로컬 MCP 서버입니다. 배포 폴더를 다른 위치로 옮긴 뒤에도 `INSTALL.cmd`로 다시 연결할 수 있습니다.

## 현재 지원 형상

- 직육면체/정육면체 (`Part::Box`)
- 원기둥 (`Part::Cylinder`)
- 구체 (`Part::Sphere`)
- 원형 플랜지 (`Part::Feature`, 외경/내경/두께)

치수 단위는 mm입니다. 예: `가로 40mm, 세로 30mm, 높이 20mm 직육면체를 만들어줘`

## 설치

ZIP을 완전히 푼 뒤 폴더의 `INSTALL.cmd`를 더블클릭합니다. 명령줄에서도 실행할 수 있습니다.

```powershell
cd <옮긴 폴더>\kimm-cad-mcp_share
.\INSTALL.cmd
```

간단한 설치·실행 방법은 [설치_실행_가이드.md](./설치_실행_가이드.md) 또는 [설치_실행_가이드.html](./설치_실행_가이드.html)에서 확인할 수 있습니다.

KIMM-CAD V26 기본 설치 위치는 `%LOCALAPPDATA%\Programs\KIMM\KIMM-CAD V26\KIMM-CAD V26.exe`입니다. 다른 위치라면 `KIMM_CAD_EXE` 환경 변수에 V26 실행기 전체 경로를 지정합니다.

`INSTALL.cmd`는 실행 정책을 지정해 내부 `install.ps1`과 `setup.ps1`을 호출합니다. 배포 폴더를 옮겨 `.venv`가 이전 위치를 가리키면 Python 환경을 다시 연결합니다. V26 GUI 자동 시작 애드온은 기본적으로 V26 설치 폴더의 `profile\data\Mod\KimmCadMcp`에 설치됩니다. `KIMM_CAD_PROFILE_ROOT`를 설정한 경우에는 그 폴더의 `profile\data\Mod`를 사용합니다. 기존 V25 프로필은 건드리지 않습니다.

배포 ZIP에는 PC별 경로가 기록되는 `.venv`를 넣지 않습니다. 처음 설치할 때 Python 패키지를 내려받으므로 인터넷 연결이 필요합니다.

## MCP 클라이언트 등록

`mcp.json.example`의 `C:/path/to/project`를 실제로 옮긴 경로로 바꾸어 사용합니다. 실행 진입점은 `run_server.ps1`입니다.

도구는 세 개입니다.

- `cad_get_capabilities()`: 실행 가능한 기본 형상과 등록 복합 워크플로 조회
- `cad_create_verified_basic_shape(request, name)`: 기본 형상 생성, FCStd/STEP 저장, 치수·형상 검증, 상태 확인을 한 번에 실행
- `cad_create(request, name)`: 기존 클라이언트 호환 이름이며 동일한 생성·검증 완료 계약을 강제
- `cad_import_verified_step(step_path, object_name, ...)`: 생성된 STEP 원본을 KIMM-CAD에 그대로 불러오고 같은 폴더에 FCStd·FCBak 저장, 유효성·solid·부피 검증, 가시성 설정, 등각 보기 및 화면 맞춤을 수행
- `cad_status()`: 연결 및 문서 상태 확인
- `cad_clear()`: 현재 문서의 객체 모두 제거

KIMM-CAD V26 GUI를 실행하면 애드온이 RPC 브리지를 자동으로 시작합니다. 브리지가 없는 상태에서 MCP 명령을 먼저 실행해도 V26 실행기를 자동으로 시작합니다. `cad_status()`는 제품 버전과 FreeCAD 런타임 버전을 별도로 표시합니다.

## 동작 구조

MCP 서버가 `runtime/inbox`에 JSON 명령을 원자적으로 기록합니다. KIMM-CAD 내부에서 실행되는 `cad_bridge/bridge_bootstrap.py`가 Qt GUI 스레드에서 명령을 처리하고 화면을 등각 보기로 맞춘 뒤 `runtime/outbox`에 결과를 돌려줍니다. 현재 문서는 `models/current_model.FCStd`에도 저장됩니다.

## 검증

```powershell
python -m pytest -q
.\start_bridge.ps1
```

`start_bridge.ps1`이 연결되면 Codex에서 `cad_status()`로 `kimm_cad_version`이 `V26.1`인지 확인할 수 있습니다.
