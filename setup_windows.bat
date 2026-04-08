@echo off
SET ENV_NAME=venv

:: 1. Check if the virtual environment folder exists
if not exist %ENV_NAME% (
    echo Creating virtual environment: %ENV_NAME%...
    python -m venv %ENV_NAME%
) else (
    echo Virtual environment already exists.
)

:: 2. Activate the environment and install requirements
echo Activating environment and installing requirements...
call %ENV_NAME%\Scripts\activate.bat && (
    pip install --upgrade pip
    if exist requirements.txt (
        pip install -r requirements.txt
    ) else (
        echo requirements.txt not found. Skipping installation.
    )
    echo Setup complete!
    cmd /k
)