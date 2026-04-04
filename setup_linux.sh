#!/bin/bash

ENV_NAME="venv"

# 1. Check if the virtual environment folder exists
if [ ! -d "$ENV_NAME" ]; then
    echo "Creating virtual environment: $ENV_NAME..."
    python3 -m venv "$ENV_NAME"
else
    echo "Virtual environment already exists."
fi

# 2. Activate the environment and install requirements
echo "Activating environment and installing requirements..."
source "$ENV_NAME/bin/activate"

pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Skipping installation."
fi

echo "Setup complete!"

# Keep the shell active with the venv activated
exec "$SHELL"
