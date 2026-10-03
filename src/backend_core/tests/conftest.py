import os
from pathlib import Path
import sys

# Ensure backend_core directory is in sys.path
backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

# Ensure required environment variables exist during test suite collection
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-execution")
os.environ.setdefault("AI_CORE_SERVICE_TOKEN", "test-ai-core-service-token")
os.environ.setdefault("AI_CORE_WEBHOOK_SECRET", "test-ai-core-webhook-secret")
