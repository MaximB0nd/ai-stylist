import os
from pathlib import Path
import sys

# Ensure backend_core directory is in sys.path
backend_core_dir = Path(__file__).resolve().parent.parent
if str(backend_core_dir) not in sys.path:
    sys.path.insert(0, str(backend_core_dir))

# Ensure required environment variables exist during test suite collection.
# Secrets must pass field_validator rules: >=32 chars, not in forbidden list.
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-for-test-execution-only-32ch")
os.environ.setdefault("AI_CORE_SERVICE_TOKEN", "pytest-ai-core-service-token-for-tests")
os.environ.setdefault("AI_CORE_WEBHOOK_SECRET", "pytest-ai-core-webhook-secret-for-tests")
