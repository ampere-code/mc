@echo off
rem Lanzador de Marce Commander. Acepta hasta dos rutas: izquierda y derecha.
setlocal
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PY%" set "PY=pythonw.exe"
start "" "%PY%" -m mc %*
endlocal
