"""P0 smoke test"""
import json, sys, http.client
HOST, PORT = "127.0.0.1", 9000
PRJ = "9e2b3e79-684f-4ea4-8dd7-94dec3d4d76f"
BASE = f"/api/v1/projects/{PRJ}"
OK = FAIL = 0

def call(method, path, body=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    conn.request(method, path,
                 body=json.dumps(body) if body else None,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    data = json.loads(r.read())
    conn.close()
    return r.status, data

def check(label, condition):
    global OK, FAIL
    if condition:
        OK += 1; print(f"  ✅ {label}")
    else:
        FAIL += 1; print(f"  ❌ {label}")

# 1
print("1. Analysis History")
st, data = call("GET", f"{BASE}/analysis/history")
check("status=200", st == 200)
check("count>=0", data.get("count", -1) >= 0)

# 2
print("2. Chapters")
st, data = call("GET", f"{BASE}/chapters")
check("status=200", st == 200)
check("has chapters", len(data) >= 1)
if len(data) > 0:
    ch = data[0]
    check("has content_marks", "content_marks" in ch)
    check("content_marks is list", isinstance(ch.get("content_marks"), list))

# 3
print("3. Foreshadowings")
st, data = call("GET", f"{BASE}/foreshadowings")
check("status=200", st == 200)
check("has foreshadowings", len(data) >= 1)
if len(data) > 0:
    f0 = data[0]
    check("has title", bool(f0.get("title")))
    check("has status", bool(f0.get("status")))
    check("has reminder_level", "reminder_level" in f0)
    check("has evidence_text field", "evidence_text" in f0)
    check("has evidence_line field", "evidence_line" in f0)
    check("has resolved_at field", "resolved_at" in f0)

# 4
print("4. Project")
st, data = call("GET", BASE)
check("status=200", st == 200)
check("has name", bool(data.get("name")))

# 5 create
print("5. Foreshadowing Create")
st, data = call("POST", f"{BASE}/foreshadowings", {
    "title": "smoke", "description": "auto", "status": "planted",
    "reminder_level": "high", "evidence_line": "L1", "evidence_text": "test"
})
check("status=200 or 201", st in (200, 201))
check("has id", len(data.get("id", "")) > 10)
check("status=planted", data.get("status") == "planted")
check("reminder=high", data.get("reminder_level") == "high")

print(f"\n{'═'*32}")
print(f"{'✅ ALL PASSED' if FAIL==0 else f'❌ {FAIL}/{OK+FAIL} FAILED'}")
sys.exit(1 if FAIL else 0)