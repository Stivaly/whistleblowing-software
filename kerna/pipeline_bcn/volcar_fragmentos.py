"""Vuelca a JSON los payloads vigentes de una colección de Qdrant (sin el punto meta)."""
import json
import sys
import embed_sync as e

col, salida = sys.argv[1], sys.argv[2]
out, off = [], None
while True:
    b = {"limit": 128, "with_payload": True, "with_vector": False,
         "filter": {"must": [{"key": "vigente", "match": {"value": True}}], "must_not": [{"has_id": [e.PUNTO_META_ID]}]}}
    if off:
        b["offset"] = off
    r = e.qdrant(f"/collections/{col}/points/scroll", b, "POST")["result"]
    out += [p["payload"] for p in r["points"]]
    off = r.get("next_page_offset")
    if not off:
        break
json.dump(out, open(salida, "w"), ensure_ascii=False)
print(len(out), "fragmentos ->", salida)
