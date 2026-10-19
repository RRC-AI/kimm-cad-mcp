@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"

set "FCSTD_FILE=%~1"
if "%FCSTD_FILE%"=="" set /p "FCSTD_FILE=투명도를 조절할 FCStd 파일 경로(또는 이 창에 드래그): "
set "FCSTD_FILE=%FCSTD_FILE:"=%"
if not exist "%FCSTD_FILE%" (
  echo [오류] 파일을 찾을 수 없습니다: %FCSTD_FILE%
  pause
  exit /b 1
)

set /p "TRANSPARENCY=투명도 0~100 (추천/기본 60): "
if "%TRANSPARENCY%"=="" set "TRANSPARENCY=60"

echo.
echo   [1] 외피·커버만 자동 선택 (조립품 추천)
echo   [2] 모든 객체 (단일 솔리드 추천)
echo   [3] 객체명 직접 지정
set /p "MODE=적용 대상 (1/2/3, 기본 1): "
if "%MODE%"=="" set "MODE=1"

if "%MODE%"=="2" goto APPLY_ALL
if "%MODE%"=="3" goto APPLY_OBJECTS

:APPLY_EXTERIOR
python "%~dp0투명도조절.py" "%FCSTD_FILE%" --transparency %TRANSPARENCY% --exterior
goto RESULT

:APPLY_ALL
python "%~dp0투명도조절.py" "%FCSTD_FILE%" --transparency %TRANSPARENCY% --all
goto RESULT

:APPLY_OBJECTS
set /p "OBJECT_NAMES=객체명(쉼표로 구분, * 사용 가능): "
python "%~dp0투명도조절.py" "%FCSTD_FILE%" --transparency %TRANSPARENCY% --objects "%OBJECT_NAMES%"

:RESULT

if errorlevel 1 (
  echo.
  echo [실패] 위 메시지를 확인해 주세요.
) else (
  echo.
  echo [안내] 원본은 유지되며, 같은 폴더에 *_내부보기.FCStd가 생성됩니다.
)
echo.
pause
