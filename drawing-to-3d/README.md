# 도면 파일 → 3D 변환기 (이식 가능한 skill 포함)

2D/3D **도면 파일**(DXF · DWG · IFC · 벡터 PDF)을 읽어 **3D 모델(STEP + STL)** 로 변환합니다.
도면 이미지를 눈으로 해석하는 게 아니라, **파일 안의 정확한 벡터 치수를 그대로** 사용하므로
치수를 잘못 읽을 일이 없습니다.

이 폴더는 **skill을 자체 포함**합니다 — 폴더째 복사하면 다른 위치/PC에서도 똑같이 작동합니다.

---

## 폴더 구조
```
도면3D변환기/
├── .claude/
│   └── skills/
│       └── drawing-file-to-3d/     ← ★ 이식 가능한 skill (이게 핵심)
│           ├── SKILL.md            
│           ├── scripts/convert.py  ← 실제 변환 엔진
│           └── references/
├── INSTALL.cmd     ← Codex skill 및 필요한 파이썬 라이브러리 설치
├── 설치.bat        ← 수동 변환용 파이썬 라이브러리 설치
├── 변환.bat        ← 도면 파일 드래그&드롭 → 3D 변환
├── 투명도조절.bat  ← FCStd 결과의 외피/전체 투명도 조절
├── input/          ← 변환할 도면 두는 곳
├── output/         ← 결과 STEP/STL 나오는 곳
├── examples/       ← 예제 도면 3개
├── requirements.txt
└── README.md
```

---

## 📦 다른 곳/다른 PC에서 쓰기 (이식성)
- 이 **`도면3D변환기` 폴더를 통째로 복사**하면 됩니다. 안에 `.claude/skills/`가 들어있어
  **skill이 폴더를 따라다닙니다.**
- **Claude Code로 쓸 때**: 이 폴더를 작업 폴더(프로젝트)로 열면 `.claude/skills/`의 skill이
  자동으로 인식됩니다 → "이 도면 3D로 만들어줘" 하면 제가 이 skill로 처리.
- **수동으로 쓸 때**: 어디에 두든 `설치.bat`(최초 1회) → `변환.bat` 실행이면 됩니다.
- (참고) 새 PC라면 파이썬 3.11+ 설치 + `설치.bat` 한 번만 해주면 라이브러리가 준비됩니다.

---

## 사용법

간단한 설치·실행 순서는 `설치_실행_가이드.md` 또는 `설치_실행_가이드.html`을 참고하세요.

### Codex skill 설치 (최초 1회)
압축을 푼 폴더에서 `INSTALL.cmd`를 더블클릭합니다. 이 설치파일은 필요한 Python 라이브러리를 설치하고, 이 프로젝트의
`.claude\skills\drawing-file-to-3d`를 `%USERPROFILE%\.agents\skills\drawing-file-to-3d`에
Junction으로 연결합니다. 따라서 프로젝트 안의 skill을 수정하면 재설치 없이
반영되고, 기본 변환 결과는 이 폴더의 `output\`에 저장됩니다.

설치 후에는 **Codex를 한 번 재시작**하세요. 기존 스킬 연결이 이전 배포 폴더의 Junction이면 설치파일이 새 위치로 연결합니다. 일반 폴더는 덮어쓰지 않습니다.

### 최초 1회 — 라이브러리 설치
`설치.bat` 더블클릭 (ezdxf · cadquery · ifcopenshell · pymupdf 자동 설치).

### 변환 (쉬운 방법)
1. `변환.bat` 에 도면 파일을 **드래그&드롭** (또는 더블클릭 후 경로 입력).
2. 작업 선택: **[1] 압출**(평판, 두께 입력) / **[2] 회전**(풀리·축, 축 선택) / **[3] IFC·이미3D**.
3. `output/` 폴더에 `이름.step`, `이름.stl` 생성 → 폴더 자동으로 열림.

### 최종 확인 모델의 내부 보기 (FCStd 투명도)
1. KIMM-CAD에서 결과를 `.FCStd`로 저장합니다. (`.STEP`/`.STL`은 표시 투명도를 저장하지 않습니다.)
2. FCStd 파일을 `투명도조절.bat`에 드래그합니다.
3. 투명도를 입력합니다. `0=불투명`, `100=완전 투명`이며, 내부가 은은하게 보이는 값은 `50~65`입니다.
4. 조립품은 **외피·커버만**, 단일 솔리드는 **모든 객체**를 선택합니다.

원본은 변경하지 않고, 같은 폴더에 `이름_내부보기.FCStd` 사본을 생성합니다. 조절되는 것은 KIMM-CAD 표시 속성뿐이며 STEP/STL 형상 정밀도에는 영향이 없습니다.

### 변환 (명령줄 — 세밀한 제어)
```
set S=.claude\skills\drawing-file-to-3d\scripts\convert.py
python %S% input\part.dxf   --thickness 12
python %S% input\pulley.dxf --revolve --axis x
python %S% input\part.dwg   --thickness 8         (DWG는 자동 DXF 변환)
python %S% input\model.ifc                        (IFC → STL)
python %S% input\draw.pdf   --thickness 5 --pdf-scale 1.0
```
옵션 전체: `python %S% --help`

---

## 지원 포맷 & 신뢰도
| 포맷 | 처리 | 신뢰도 |
|---|---|---|
| **DXF** | 벡터 그대로 → 압출/회전 | 높음 |
| **DWG** | ODA File Converter로 DXF 변환 후 처리 | 높음 |
| **IFC** | 이미 3D → STL 변환 | 높음 |
| **PDF** | 벡터 PDF만: 선/곡선 추출 → DXF → 3D (`--pdf-scale` 보정) | 중간 |

## 꼭 알아둘 한계
1. 2D 한 장엔 깊이가 없어 **압출 두께/회전축은 지정** 필요 (임의로 안 지어냄).
2. **여러 뷰가 섞인 도면 시트 통째로**는 자동변환 불가 → 깨끗한 단일 프로파일 필요.
3. **PDF**: 벡터만(스캔 불가), 실척 보정 필요, 원은 다각형 근사.
4. **이미 3D인 DWG(3DSOLID)**는 대상 아님 (2D→3D가 아니라 3D 추출 → 별도 기능 필요).

## 예제로 테스트
```
set S=.claude\skills\drawing-file-to-3d\scripts\convert.py
python %S% examples\test.dxf --thickness 12 --out output\test
python %S% examples\bushing_halfsection.dxf --revolve --axis x --out output\bushing
python %S% examples\example_vector.pdf --thickness 6 --out output\frompdf
```
