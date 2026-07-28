"""P0+P1+P2 combined smoke test"""
import json, sys, http.client
HOST, PORT = "127.0.0.1", 9000
PRJ = "9e2b3e79-684f-4ea4-8dd7-94dec3d4d76f"
BASE = f"/api/v1/projects/{PRJ}"
OK = FAIL = 0

def call(method, path, body=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    conn.request(method, path,
                 body=json.dumps(body) if body else None,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data

def call_json(method, path, body=None):
    st, raw = call(method, path, body)
    return st, json.loads(raw)

def check(label, condition):
    global OK, FAIL
    if condition:
        OK += 1; print(f"  ✅ {label}")
    else:
        FAIL += 1; print(f"  ❌ {label}")

# ── 0 Health ──
st, raw = call("GET", "/health")
check("health 200", st == 200)

# ── 1 Analysis ──
print("1. Analysis History")
st, data = call_json("GET", f"{BASE}/analysis/history")
check("status=200", st == 200)
check("count>=0", data.get("count", -1) >= 0)

# ── 2 Chapters + group/tags ──
print("2. Chapters (group/tags fields)")
st, data = call_json("GET", f"{BASE}/chapters")
check("status=200", st == 200)
check("has chapters", len(data) >= 1)
if len(data) > 0:
    check("has group field", "group" in data[0])
    check("has tags field", "tags" in data[0])

# ── 3 Foreshadowing ──
print("3. Foreshadowing")
st, data = call_json("GET", f"{BASE}/foreshadowings")
check("status=200", st == 200)
check("has items", len(data) >= 1)

# ── 4 Search ──
print("4. Search (SQLite)")
st, data = call_json("POST", f"{BASE}/search",
    {"query": "记忆", "top_k": 3, "use_rerank": False})
check("status=200", st == 200)
check("results>=1", data.get("total", 0) >= 1)

# ── 5 Events ──
print("5. Events")
st, data = call_json("GET", f"{BASE}/events")
check("status=200", st == 200)
check("has events", data.get("total", -1) >= 1)

# ── 6 Backup ──
print("6. Backup (JSON download)")
st, raw = call("GET", f"/api/v1/projects/backup/{PRJ}")
check("status=200", st == 200)
try:
    data = json.loads(raw)
    check("backup has project", "project" in data)
    check("backup has chapters", "chapters" in data)
    check("backup has characters", "characters" in data)
    check("backup has chapters count", len(data.get("chapters", [])) >= 1)
except Exception as e:
    check(f"backup json parse error: {e}", False)

# ── 7 Restore ──
print("7. Restore")
st, data = call_json("POST", f"/api/v1/projects/backup/{PRJ}", data)
check("status=200", st == 200)
check("restored_count>=0", data.get("restored_count", -1) >= 0)

print(f"\n{'═'*32}")
print(f"{'✅ ALL PASSED' if FAIL==0 else f'❌ {FAIL}/{OK+FAIL} FAILED'}")
sys.exit(1 if FAIL else 0)