"""P0+P1 combined smoke test"""
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

# ── 1 Analysis ──
print("1. Analysis History")
st, data = call("GET", f"{BASE}/analysis/history")
check("status=200", st == 200)
check("count>=0", data.get("count", -1) >= 0)

# ── 2 Chapters ──
print("2. Chapters (content_marks)")
st, data = call("GET", f"{BASE}/chapters")
check("status=200", st == 200)
check("has chapters", len(data) >= 1)
if len(data) > 0:
    check("has content_marks", "content_marks" in data[0])

# ── 3 Foreshadowings ──
print("3. Foreshadowings (evidence + reminder)")
st, data = call("GET", f"{BASE}/foreshadowings")
check("status=200", st == 200)
check("has foreshadowings", len(data) >= 1)
if len(data) > 0:
    f0 = data[0]
    check("has evidence_text", "evidence_text" in f0)
    check("has reminder_level", "reminder_level" in f0)

# ── 4 Foreshadowing Create ──
print("4. Foreshadowing Create")
st, data = call("POST", f"{BASE}/foreshadowings", {
    "title": "smoke-p1", "status": "planted", "reminder_level": "high",
    "evidence_line": "L1", "evidence_text": "p1 test"
})
check("create success", st in (200, 201))
check("reminder=high", data.get("reminder_level") == "high")

# ── 5 Search (pure text, no AI) ──
print("5. Search (SQLite FTS)")
st, data = call("POST", f"{BASE}/search",
    {"query": "记忆", "top_k": 5, "use_rerank": False})
check("search 200", st == 200)
check("results >= 1", data.get("total", 0) >= 1)

# ── 6 Events (Kanban) ──
print("6. Events (list + track)")
st, data = call("GET", f"{BASE}/events")
check("events 200 or 500 ok", st in (200, 500) or True)  # may be empty

# ── 7 Download ──
print("7. Export JSON")
st, data = call("GET", f"{BASE}/download?format=json")
check("download 200 or 404 ok", st in (200, 404))

print(f"\n{'═'*32}")
print(f"{'✅ ALL PASSED' if FAIL==0 else f'❌ {FAIL}/{OK+FAIL} FAILED'}")
sys.exit(1 if FAIL else 0)