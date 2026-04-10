@echo off

:: Usage:
::   rundocker.bat                        -> pull latest image from DockerHub, then run
::   rundocker.bat --local                -> build image locally from Dockerfile, then run
::   rundocker.bat --local --no-cache     -> build locally without Docker layer cache, then run

set BUILD_LOCAL=0
set NO_CACHE=
for %%A in (%*) do (
    if /i "%%A"=="--local"    set BUILD_LOCAL=1
    if /i "%%A"=="--no-cache" set NO_CACHE=--no-cache
)

:: Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is not running. Attempting to start Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to start...
    :waitloop
    timeout /t 3 /nobreak >nul
    docker info >nul 2>&1
    if errorlevel 1 goto waitloop
    echo Docker is ready.
)

if %BUILD_LOCAL%==1 (
    if defined NO_CACHE (
        echo Building image locally ^(no cache^)...
    ) else (
        echo Building image locally...
    )
    docker build %NO_CACHE% -t coopstorage:local .
    if errorlevel 1 (
        echo Build failed. Exiting.
        pause
        exit /b 1
    )
    set IMAGE=coopstorage:local
) else (
    echo Pulling latest image from DockerHub...
    docker pull tylertjburns/coopstorage:latest
    set IMAGE=tylertjburns/coopstorage:latest
)

:: Stop and remove any existing container with the same name
docker inspect coopstorage >nul 2>&1
if not errorlevel 1 (
    echo Existing coopstorage container found. Stopping and removing...
    docker stop coopstorage >nul 2>&1
    docker rm coopstorage >nul 2>&1
    echo Done.
)

docker run -d -p 1219:1219 --name coopstorage %IMAGE%
echo coopstorage running at http://localhost:1219
pause
