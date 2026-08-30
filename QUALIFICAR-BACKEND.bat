@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo  ECONOMY LAB v2.11 - QUALIFICAR BACKEND
echo ==============================================
echo.
echo Este teste valida Mesa, HARK, Dynare/Octave e Minsky.
echo Os relatorios serao salvos em validation-reports.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\validate-external-engines.ps1" -StrictQualification
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (
  echo QUALIFICACAO CONCLUIDA COM SUCESSO.
) else (
  echo QUALIFICACAO NAO COMPLETA. Codigo: %CODE%
  echo Abra o relatorio em validation-reports para ver o motivo.
)
echo.
pause
exit /b %CODE%
