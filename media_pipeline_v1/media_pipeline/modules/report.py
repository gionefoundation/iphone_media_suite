import csv,json
from pathlib import Path
from datetime import datetime
FIELDS=["timestamp","kind","source","output","status","input_bytes","output_bytes","saved_bytes","saved_percent","details"]
def write_reports(output,records):
    d=Path(output)/"reports"; d.mkdir(parents=True,exist_ok=True); stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    with (d/f"summary_{stamp}.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for r in records:w.writerow({k:r.get(k,"") for k in FIELDS})
    with (d/f"run_{stamp}.jsonl").open("w",encoding="utf-8") as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+"\n")
    print(f"Reports saved to: {d}")
