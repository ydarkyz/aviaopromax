"""Gera aviaopromax/static/airports.json a partir da base OurAirports (domínio público).

Uso: python tools/build_airports.py <pasta com basic_info.json, region.json, references.json>
Os arquivos vêm do pacote npm `ourairports-data-js` (dist/data/).
Mantém só aeroportos com código IATA e voos comerciais regulares.
"""
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
load = lambda name: {r["id"]: r for r in json.loads((src / name).read_text())}
basic, region, refs = load("basic_info.json"), load("region.json"), load("references.json")

out = []
for id_, b in basic.items():
    iata = (b.get("iata_code") or "").strip().upper()
    if len(iata) != 3 or refs.get(id_, {}).get("scheduled_service") != "yes":
        continue
    if b.get("type") not in ("large_airport", "medium_airport", "small_airport"):
        continue
    r = region.get(id_, {})
    rank = {"large_airport": 0, "medium_airport": 1}.get(b["type"], 2)
    out.append([iata, b["name"], r.get("municipality") or "", r.get("iso_country") or "", rank])

out.sort(key=lambda a: (a[4], a[0]))
dest = Path(__file__).resolve().parent.parent / "aviaopromax" / "static" / "airports.json"
dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(f"{len(out)} aeroportos -> {dest}")
