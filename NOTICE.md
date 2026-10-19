# NOTICE

KIMM-CAD MCP & Drawing-to-3D
Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)

이 저장소의 소스 코드는 **GNU Lesser General Public License v2.1 or later (LGPL-2.1-or-later)** 로 배포됩니다. 전문은 [LICENSE](./LICENSE)에 있습니다.

## 1. KIMM-CAD / FreeCAD 와의 관계

- **KIMM-CAD V26**은 [FreeCAD](https://www.freecad.org/)를 기반으로 KIMM이 개발한 CAD 배포판입니다. FreeCAD는 LGPL-2.1-or-later로 배포됩니다.
- 이 저장소의 코드는 KIMM-CAD에 설치된 FreeCAD 런타임의 Python API(`FreeCAD`, `FreeCADGui`, `Part`, `Import`)를 **실행 시점에 import 하여 호출**합니다.
- 이 저장소는 FreeCAD 또는 KIMM-CAD의 소스 코드나 바이너리를 **포함하거나 재배포하지 않습니다.** KIMM-CAD는 사용자가 별도로 설치해야 합니다.
- FreeCAD와 같은 LGPL-2.1-or-later를 채택하여 FreeCAD 애드온 생태계와의 호환성을 유지합니다.
- "FreeCAD"는 FreeCAD 프로젝트의 명칭이며, 이 저장소는 FreeCAD 프로젝트가 보증하거나 후원하는 것이 아닙니다.

## 2. 외부 의존성 (이 저장소에 포함되지 않음)

설치 스크립트가 각 패키지 저장소에서 내려받으며, 각 구성요소는 해당 라이선스를 따릅니다.

| 구성요소 | 사용 위치 | 라이선스 | 비고 |
|---|---|---|---|
| FreeCAD (KIMM-CAD V26 런타임) | `mcp-server/cad_bridge`, `cad_addon`, `generated_scripts` | LGPL-2.1-or-later | KIMM-CAD 설치본 사용, 미포함 |
| PySide6 (FreeCAD 런타임 포함) | `mcp-server/cad_bridge` | LGPL-3.0 | KIMM-CAD 설치본 사용, 미포함 |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp`) | `mcp-server` | MIT | 필수 |
| pytest | `mcp-server/tests` | MIT | 개발용 |
| hatchling | `mcp-server` 빌드 | MIT | 빌드용 |
| [ezdxf](https://github.com/mozman/ezdxf) | `drawing-to-3d` | MIT | 필수 |
| [CadQuery](https://github.com/CadQuery/cadquery) | `drawing-to-3d` | Apache-2.0 | 필수 |
| [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) | `drawing-to-3d` (IFC 입력) | LGPL-3.0-or-later | IFC 변환 시에만 import |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) (`fitz`) | `drawing-to-3d` (PDF 입력) | **AGPL-3.0** 또는 Artifex 상용 라이선스 | PDF 변환 시에만 import |
| [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) | `drawing-to-3d` (DWG 입력) | ODA 독점 라이선스 | 외부 프로그램 호출, 미포함 |

### 주의 사항

- **PyMuPDF (AGPL-3.0)**: `convert.py`는 PDF 입력을 처리할 때만 PyMuPDF를 import 합니다. PyMuPDF와 결합한 프로그램을 배포하거나 네트워크 서비스로 제공하려면 AGPL-3.0 조건을 따르거나 Artifex의 상용 라이선스를 받아야 합니다. PDF 변환이 필요 없다면 `drawing-to-3d/requirements.txt`에서 `pymupdf`를 빼고 설치해도 됩니다.
- **ODA File Converter**: DWG→DXF 변환에 쓰이는 외부 프로그램입니다. 이 저장소는 재배포하지 않으며, 사용자가 ODA 공식 사이트에서 직접 설치해야 합니다. ODA는 비회원에게 **비상업적 용도의 사용만** 허용한다고 안내하고 있으니, 상업적으로 사용하려면 ODA 이용 조건을 확인해야 합니다.

## 3. 저장소에 포함하지 않은 자료

다음 자료는 고객사 자료이거나, 용량이 크거나, 재배포 조건이 있어서 저장소에 넣지 않았습니다.

- KIMM-CAD 설치 파일(`KIMM-CAD-V26.1-Setup.exe`)
- 실제 프로젝트 도면(DWG)과 그 도면으로 생성한 STEP·FCStd·분석 결과물
- 실행 로그, 런타임 큐(`runtime/`), 가상환경(`.venv/`)
