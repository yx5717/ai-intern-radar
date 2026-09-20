import tempfile
import sys
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import UserStore


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    store = UserStore(root / "test.db", root / ".key")
    user = store.register_user("tester", "strong-password")
    assert store.authenticate("tester", "wrong-password") is None
    assert store.authenticate("tester", "strong-password")["id"] == user["id"]

    state = {"profile_school": "首都经济贸易大学", "api_key": "sk-secret-value"}
    store.save_state(user["id"], state)
    assert store.load_state(user["id"]) == state
    assert b"sk-secret-value" not in (root / "test.db").read_bytes()
    Fernet((root / ".key").read_bytes())

    job = {
        "record_id": "USR-TEST",
        "jd_raw": "AI 产品实习生岗位说明",
        "saved_at": "2026-09-20 12:00",
        "snapshot": {"company": "示例公司"},
    }
    store.upsert_job(user["id"], job)
    assert store.list_jobs(user["id"])[0]["record_id"] == "USR-TEST"
    store.delete_job(user["id"], "USR-TEST")
    assert store.list_jobs(user["id"]) == []

print({"auth": "passed", "api_key_storage": "encrypted", "jobs": "persistent"})
