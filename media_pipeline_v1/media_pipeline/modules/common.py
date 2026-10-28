from pathlib import Path
from datetime import datetime
from config import IMAGE_EXTS,VIDEO_EXTS,SKIP_DIR_NAMES,BATCH_LIMIT_BYTES

def human(n):
    for unit in ("B","KB","MB","GB","TB"):
        if n<1024 or unit=="TB": return f"{n:.2f} {unit}"
        n/=1024

def make_batches(paths,max_bytes=BATCH_LIMIT_BYTES):
    batches=[]; batch=[]; size=0
    for p in sorted(paths,key=lambda x:str(x).lower()):
        try: n=p.stat().st_size
        except OSError: continue
        if batch and size+n>max_bytes: batches.append(batch); batch=[]; size=0
        batch.append(p); size+=n
        if n>max_bytes: batches.append(batch); batch=[]; size=0
    if batch: batches.append(batch)
    return batches

def scan_media(source,output):
    images=[]; videos=[]; skipped=[]; out=output.resolve()
    for p in source.rglob("*"):
        if not p.is_file(): continue
        try:
            r=p.resolve()
            if r==out or out in r.parents or any(x.lower() in SKIP_DIR_NAMES for x in p.parts): continue
            if p.suffix.lower() in IMAGE_EXTS: images.append(p)
            elif p.suffix.lower() in VIDEO_EXTS: videos.append(p)
        except OSError: skipped.append(str(p))
    return {"images":images,"videos":videos,"skipped":skipped}

def size_of(p):
    try:return p.stat().st_size
    except OSError:return 0

def print_scan(f):
    for k in ("images","videos"):
        print(f"{k.title()}: {len(f[k])} files, {human(sum(size_of(p) for p in f[k]))}")
    print(f"Unreadable paths: {len(f['skipped'])}")
    print(f"Image batches: {len(make_batches(f['images']))}; video batches: {len(make_batches(f['videos']))}")
    print("Original files are never deleted.")

def capture_datetime(p):
    try:return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
    except OSError:return "UNKNOWN-TIME"

def tag_for(p,place=None,date_text=None,prefix="IMG"):
    tag=f"ONE FOUNDATION | {prefix}:{date_text or capture_datetime(p)}"
    if place:
        letters="".join(c for c in str(place) if c.isalpha())
        if letters: tag+=f" | LOC:{letters[:3].upper()}"
    return tag

def safe_name(p,out,ext):
    import hashlib
    h=hashlib.sha1(str(p.resolve()).encode("utf-8","replace")).hexdigest()[:8]
    stem="".join(c if c.isalnum() or c in "-_ " else "_" for c in p.stem).strip()[:80] or "media"
    return out/f"{stem}_{h}.{ext}"
