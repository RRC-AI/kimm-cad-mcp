@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "SCRIPT=%~dp0.claude\skills\drawing-file-to-3d\scripts\convert.py"
echo ============================================
echo    도면 파일 -^> 3D 변환기  (DXF/DWG/IFC/PDF)
echo ============================================
echo.

set "INFILE=%~1"
if "%INFILE%"=="" set /p "INFILE=변환할 도면 파일 경로를 입력(또는 이 창에 드래그): "
if not exist "%INFILE%" (
  echo [오류] 파일을 찾을 수 없습니다: %INFILE%
  pause & exit /b 1
)

for %%F in ("%INFILE%") do set "NAME=%%~nF"
set "OUT=%~dp0output\%NAME%"

echo.
echo   [1] 압출  (평판/브래킷 - 두께 입력)
echo   [2] 회전  (풀리/축/부싱 - 반단면 프로파일)
echo   [3] IFC / 이미 3D  (그대로 변환)
echo.
set /p "OP=작업 선택 (1/2/3, 기본 1): "
if "%OP%"=="2" goto REVOLVE
if "%OP%"=="3" goto IFC

:EXTRUDE
set /p "TH=압출 두께 mm (기본 10): "
if "%TH%"=="" set "TH=10"
echo.
python "%SCRIPT%" "%INFILE%" --thickness %TH% --out "%OUT%"
goto DONE

:REVOLVE
set /p "AX=회전축 x / y / z (기본 x): "
if "%AX%"=="" set "AX=x"
echo.
python "%SCRIPT%" "%INFILE%" --revolve --axis %AX% --out "%OUT%"
goto DONE

:IFC
echo.
python "%SCRIPT%" "%INFILE%" --out "%OUT%"
goto DONE

:DONE
echo.
if exist "%OUT%.step" (
  echo [완료] output 폴더에 생성됨:  %NAME%.step  /  %NAME%.stl
  explorer "%~dp0output"
) else (
  echo [실패] 변환 결과가 없습니다. 위 메시지를 확인하세요.
)
echo.
pause
