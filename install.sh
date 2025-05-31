# install.sh
# ------------
# Convenience script to create a Python virtual environment and install runtime requirements.

#!/usr/bin/env bash
set -e

# 1. Create a virtual environment in ".venv"
python3 -m venv .venv

# 2. Activate the virtual environment
# Note: On Windows, use "source .venv/Scripts/activate"
source .venv/bin/activate

# 3. Upgrade pip to the latest version
pip install --upgrade pip

# 4. Install all packages listed in requirements.txt
pip install -r requirements.txt

echo "✅ Virtual environment created and dependencies installed."
