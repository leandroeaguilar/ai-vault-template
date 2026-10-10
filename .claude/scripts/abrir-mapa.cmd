@echo off
rem Abre el Mapa de mis agentes (Mission Control) con doble clic.
rem Si el servidor ya está corriendo en 8765, solo abre el navegador;
rem si no, lo levanta minimizado (se cierra cerrando esa ventana).
cd /d "%~dp0..\.."
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { if ($c.ConnectAsync('127.0.0.1', 8765).Wait(500)) { exit 0 } } catch {}; exit 1"
if %errorlevel%==0 (
  start "" http://127.0.0.1:8765/
) else (
  start "Mission Control" /min python .claude\scripts\mapa-agentes.py --serve
)
