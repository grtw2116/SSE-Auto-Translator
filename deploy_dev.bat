@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "BUILD_OUTPUT=%PROJECT_DIR%dist\SSE-AT"
set "DEV_DIR=G:\MyGames\Skyrim AE\SSE-AT-dev"
set "PROD_DATA_DIR=G:\MyGames\Skyrim AE\SSE-AT\data"
set "DEV_DATA_DIR=%DEV_DIR%\data"

pushd "%PROJECT_DIR%" || exit /b 1

echo Building SSE Auto Translator...
call build_fast.bat
if errorlevel 1 (
    echo Build failed.
    popd
    exit /b 1
)

if not exist "%BUILD_OUTPUT%\" (
    echo Build output folder not found: "%BUILD_OUTPUT%"
    popd
    exit /b 1
)

if not exist "%PROD_DATA_DIR%\" (
    echo Source data folder not found: "%PROD_DATA_DIR%"
    popd
    exit /b 1
)

echo Removing existing dev deployment...
if exist "%DEV_DIR%\" (
    if exist "%DEV_DATA_DIR%\" (
        echo Preserving existing dev data folder...
        move "%DEV_DATA_DIR%" "%PROJECT_DIR%data.deploy_backup" >nul
        if errorlevel 1 (
            echo Failed to preserve "%DEV_DATA_DIR%".
            popd
            exit /b 1
        )
    )

    rmdir /s /q "%DEV_DIR%"
    if errorlevel 1 (
        echo Failed to remove "%DEV_DIR%".
        if exist "%PROJECT_DIR%data.deploy_backup\" (
            mkdir "%DEV_DIR%"
            move "%PROJECT_DIR%data.deploy_backup" "%DEV_DATA_DIR%" >nul
        )
        popd
        exit /b 1
    )
)

echo Copying build output to "%DEV_DIR%"...
robocopy "%BUILD_OUTPUT%" "%DEV_DIR%" /E
if %ERRORLEVEL% GEQ 8 (
    echo Failed to copy build output.
    if exist "%PROJECT_DIR%data.deploy_backup\" (
        mkdir "%DEV_DIR%"
        move "%PROJECT_DIR%data.deploy_backup" "%DEV_DATA_DIR%" >nul
    )
    popd
    exit /b 1
)

if exist "%PROJECT_DIR%data.deploy_backup\" (
    echo Restoring existing dev data folder...
    if exist "%DEV_DATA_DIR%\" rmdir /s /q "%DEV_DATA_DIR%"
    move "%PROJECT_DIR%data.deploy_backup" "%DEV_DATA_DIR%" >nul
    if errorlevel 1 (
        echo Failed to restore existing dev data folder.
        popd
        exit /b 1
    )
) else (
    echo Copying data folder to "%DEV_DATA_DIR%"...
    robocopy "%PROD_DATA_DIR%" "%DEV_DATA_DIR%" /E
    if %ERRORLEVEL% GEQ 8 (
        echo Failed to copy data folder.
        popd
        exit /b 1
    )
)

popd
echo Dev deployment completed: "%DEV_DIR%"
exit /b 0
