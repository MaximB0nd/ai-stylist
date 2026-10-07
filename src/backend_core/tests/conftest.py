import os
from pathlib import Path
import sys

# Ensure backend_core directory is in sys.path
backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

from dotenv import load_dotenv

# Load test environment variables from .env.test before any module imports Settings.
# This ensures tests are isolated and reproducible without hardcoding credentials in Python code.
test_env_path = backend_core_dir / ".env.test"
if test_env_path.exists():
    load_dotenv(dotenv_path=test_env_path, override=False)

