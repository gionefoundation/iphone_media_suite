import argparse
from pathlib import Path
from media_pipeline.modules.common import scan_media, print_scan
from media_pipeline.modules.images import process_images
from media_pipeline.modules.videos import process_videos
from media_pipeline.modules.report import write_reports

def main():
    p=argparse.ArgumentParser(description="One Foundation Media Pipeline V1")
    sub=p.add_subparsers(dest="command",required=True)
    for c in ("scan","images","videos","all"):
        s=sub.add_parser(c)
        s.add_argument("--source",required=True)
        s.add_argument("--output",default="./output")
        s.add_argument("--workers",type=int,default=2)
        s.add_argument("--quality",type=int,default=92)
        s.add_argument("--crf",type=int,default=22)
        s.add_argument("--background",default="#ffffff")
    a=p.parse_args(); source=Path(a.source).expanduser().resolve(); output=Path(a.output).expanduser().resolve()
    if not source.is_dir(): raise SystemExit(f"Source folder not found: {source}")
    if a.workers<1 or not 1<=a.quality<=95 or not 0<=a.crf<=40: raise SystemExit("Invalid workers, quality, or CRF value")
    found=scan_media(source,output); print_scan(found)
    if a.command=="scan": return
    records=[]
    if a.command in ("images","all"): records += process_images(found["images"],output,a.workers,a.quality,a.background)
    if a.command in ("videos","all"): records += process_videos(found["videos"],output,a.crf)
    write_reports(output,records)
    ok=[r for r in records if r.get("status")=="ok"]
    i=sum(r["input_bytes"] for r in ok); o=sum(r["output_bytes"] for r in ok)
    print(f"Successful files: {len(ok)}/{len(records)} | input {i/1024**3:.2f} GiB | output {o/1024**3:.2f} GiB | saved {(i-o)/1024**2:.1f} MiB")
if __name__=="__main__": main()
