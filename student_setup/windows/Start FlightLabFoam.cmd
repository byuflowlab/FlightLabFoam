@echo off
setlocal
title FlightLabFoam

rem Double-click launcher for FlightLabFoam.
rem FlightLabFoam is pinned so every student uses the same build.
rem
rem The first launch downloads uv, Python 3.12, and the promoted build into a
rem FlightLabFoam-only folder under %LOCALAPPDATA%\FlightLabFoam. Later launches
rem start that installed copy directly, so nothing is downloaded or re-resolved
rem again until the instructor promotes a new build. The machine settings live
rem in the same folder, outside the environment, so updates keep them.

set "FLIGHTLABFOAM_DEFAULT_COMMIT=cc14eb49dc85fbac4482cbb93a0be939c11e7a87"
set "FLIGHTLABFOAM_RELEASE_URL=https://raw.githubusercontent.com/byuflowlab/FlightLabFoam/master/student_setup/release.txt"
set "FLIGHTLABFOAM_DATA_ROOT=%LOCALAPPDATA%\FlightLabFoam"
set "FLIGHTLABFOAM_UV_DIR=%FLIGHTLABFOAM_DATA_ROOT%\uv"
set "FLIGHTLABFOAM_UV=%FLIGHTLABFOAM_UV_DIR%\uv.exe"
set "FLIGHTLABFOAM_RELEASE_FILE=%FLIGHTLABFOAM_DATA_ROOT%\release.txt"
set "FLIGHTLABFOAM_RELEASE_TEMP=%FLIGHTLABFOAM_DATA_ROOT%\release-download.txt"
set "FLIGHTLABFOAM_ENV_DIR=%FLIGHTLABFOAM_DATA_ROOT%\env"
set "FLIGHTLABFOAM_ENV_TEMP=%FLIGHTLABFOAM_DATA_ROOT%\env-install"
set "FLIGHTLABFOAM_INSTALLED_FILE=%FLIGHTLABFOAM_DATA_ROOT%\installed.txt"
set "FLIGHTLABFOAM_SETTINGS_FILE=%FLIGHTLABFOAM_DATA_ROOT%\settings.yaml"
set "FLIGHTLABFOAM_PYTHON=%FLIGHTLABFOAM_ENV_DIR%\Scripts\python.exe"
set "FLIGHTLABFOAM_INSTALLED="

echo FlightLabFoam
echo ==============================================
echo.

if not exist "%FLIGHTLABFOAM_DATA_ROOT%" mkdir "%FLIGHTLABFOAM_DATA_ROOT%"

if not exist "%FLIGHTLABFOAM_UV%" (
    echo First-time setup: downloading the FlightLabFoam launcher...
    echo This does not need administrator access.
    echo.
    if not exist "%FLIGHTLABFOAM_UV_DIR%" mkdir "%FLIGHTLABFOAM_UV_DIR%"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_UNMANAGED_INSTALL='%FLIGHTLABFOAM_UV_DIR%'; irm 'https://astral.sh/uv/install.ps1' | iex"
    if errorlevel 1 goto setup_error
    if not exist "%FLIGHTLABFOAM_UV%" goto setup_error
)

echo Checking for an update...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$v=(Invoke-RestMethod -TimeoutSec 15 '%FLIGHTLABFOAM_RELEASE_URL%').Trim(); if ($v -notmatch '^[0-9a-f]{40}$') { exit 1 }; Set-Content -NoNewline -Path '%FLIGHTLABFOAM_RELEASE_TEMP%' -Value $v"
if errorlevel 1 goto update_unavailable
move /Y "%FLIGHTLABFOAM_RELEASE_TEMP%" "%FLIGHTLABFOAM_RELEASE_FILE%" >nul
goto update_ready

:update_unavailable
if exist "%FLIGHTLABFOAM_RELEASE_FILE%" (
    echo The update check was unavailable; using the most recent downloaded version.
    goto update_ready
)
echo The update check was unavailable; using the version included with this launcher.
>"%FLIGHTLABFOAM_RELEASE_FILE%" echo %FLIGHTLABFOAM_DEFAULT_COMMIT%

:update_ready
set /p FLIGHTLABFOAM_COMMIT=<"%FLIGHTLABFOAM_RELEASE_FILE%"
if exist "%FLIGHTLABFOAM_INSTALLED_FILE%" set /p FLIGHTLABFOAM_INSTALLED=<"%FLIGHTLABFOAM_INSTALLED_FILE%"
if not exist "%FLIGHTLABFOAM_PYTHON%" goto install
if not "%FLIGHTLABFOAM_INSTALLED%"=="%FLIGHTLABFOAM_COMMIT%" goto install
goto run

:install
set "FLIGHTLABFOAM_REQUIREMENT=flightlabfoam[pinned] @ https://github.com/byuflowlab/FlightLabFoam/archive/%FLIGHTLABFOAM_COMMIT%.zip"
echo Installing build %FLIGHTLABFOAM_COMMIT:~0,8%...
echo The first install downloads Python and FlightLabFoam's libraries (about 60 MB)
echo and can take a few minutes. Later updates reuse what is already downloaded.
echo.
if exist "%FLIGHTLABFOAM_ENV_TEMP%" rmdir /s /q "%FLIGHTLABFOAM_ENV_TEMP%"
"%FLIGHTLABFOAM_UV%" python install 3.12
if errorlevel 1 goto install_failed
"%FLIGHTLABFOAM_UV%" venv --quiet --python 3.12 "%FLIGHTLABFOAM_ENV_TEMP%"
if errorlevel 1 goto install_failed
"%FLIGHTLABFOAM_UV%" pip install --python "%FLIGHTLABFOAM_ENV_TEMP%\Scripts\python.exe" "%FLIGHTLABFOAM_REQUIREMENT%"
if errorlevel 1 goto install_failed
if exist "%FLIGHTLABFOAM_ENV_DIR%" rmdir /s /q "%FLIGHTLABFOAM_ENV_DIR%"
move "%FLIGHTLABFOAM_ENV_TEMP%" "%FLIGHTLABFOAM_ENV_DIR%" >nul
if errorlevel 1 goto install_failed
>"%FLIGHTLABFOAM_INSTALLED_FILE%" echo %FLIGHTLABFOAM_COMMIT%
echo.
goto run

:install_failed
if exist "%FLIGHTLABFOAM_ENV_TEMP%" rmdir /s /q "%FLIGHTLABFOAM_ENV_TEMP%"
echo.
if not exist "%FLIGHTLABFOAM_PYTHON%" goto install_error
if "%FLIGHTLABFOAM_INSTALLED%"=="" goto install_error
echo The update could not be installed; starting the previously installed build instead.
set "FLIGHTLABFOAM_COMMIT=%FLIGHTLABFOAM_INSTALLED%"
goto run

:run
echo Build: %FLIGHTLABFOAM_COMMIT:~0,8%
echo Starting FlightLabFoam. Your web browser will open when it is ready.
echo.
echo Keep this window open while using FlightLabFoam.
echo Click Exit in the app, close this window, or press Control-C when you are finished.
echo.

rem The server runs until stopped, so the smoke test only imports the app.
if "%FLIGHTLABFOAM_TEST_ONLY%"=="1" (
    "%FLIGHTLABFOAM_PYTHON%" -c "import flightlabfoam.app; print('FlightLabFoam imports OK')"
) else (
    "%FLIGHTLABFOAM_PYTHON%" -m flightlabfoam --settings "%FLIGHTLABFOAM_SETTINGS_FILE%"
)
if errorlevel 1 goto run_error
exit /b 0

:setup_error
echo.
echo Setup could not be downloaded. Check the internet connection and try again.
echo If the problem continues, take a screenshot of this window and send it to your TA.
if "%FLIGHTLABFOAM_TEST_ONLY%"=="1" exit /b 1
pause
exit /b 1

:install_error
echo FlightLabFoam could not be installed. Check the internet connection and try again.
echo If the problem continues, take a screenshot of this window and send it to your TA.
if "%FLIGHTLABFOAM_TEST_ONLY%"=="1" exit /b 1
pause
exit /b 1

:run_error
echo.
echo FlightLabFoam stopped because of an error.
echo Take a screenshot of this window and send it to your TA.
if "%FLIGHTLABFOAM_TEST_ONLY%"=="1" exit /b 1
pause
exit /b 1
