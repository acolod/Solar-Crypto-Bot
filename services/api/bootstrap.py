import os, sys, traceback, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

Path("../logs").mkdir(exist_ok=True)

def report(exc_type, exc_val, exc_tb):
    error_data = {
        "level": "critical",
        "message": str(exc_val),
        "error_type": exc_type.__name__,
        "traceback": "".join(
            traceback.format_exception(exc_type, exc_val, exc_tb)
        ),
        "request_id": "startup",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    with open("../logs/fast_api.log", "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Bootstrap error at {error_data['timestamp']}\n")
        f.write(f"{error_data['error_type']}: {error_data['message']}\n")
        f.write(error_data['traceback'])

try:
    from api.routes import app
except Exception:
    exc_type, exc_val, exc_tb = sys.exc_info()
    report(exc_type, exc_val, exc_tb)
    raise

__all__ = ["app"]