@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   도면3D변환기 - 라이브러리 설치 (최초 1회)
echo ============================================
echo.
python --version 1>nul 2>nul
if errorlevel 1 (
  echo [오류] 파이썬이 설치되어 있지 않습니다. python.org 에서 Python 3.11+ 설치 후 다시 실행하세요.
  pause & exit /b 1
)
echo 파이썬 확인됨. 라이브러리를 설치합니다...
echo.
python -m pip install --upgrade pip
python -m pip install ezdxf cadquery ifcopenshell pymupdf
echo.
echo ============================================
echo   설치 완료! 이제 변환.bat 로 도면을 변환하세요.
echo ============================================
pause
