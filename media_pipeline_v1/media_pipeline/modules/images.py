from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from PIL import Image,ImageOps
from tqdm import tqdm
from config import BATCH_LIMIT_BYTES
from media_pipeline.modules.common import make_batches,size_of,safe_name,tag_for
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception: pass

def date_place(im):
    date=None; place=None
    try:
        ex=im.getexif(); nested=ex.get_ifd(0x8769) if ex else {}
        raw=nested.get(36867) or ex.get(306)
        if raw:
            try: date=datetime.strptime(str(raw),"%Y:%m:%d %H:%M:%S").strftime("%Y%m%d-%H%M%S")
            except Exception: pass
        for key in (0x9C9C,0xA434,315,33432):
            if ex.get(key): place=str(ex.get(key)); break
    except Exception: pass
    return date,place

def one(p,out,quality,bg):
    started=datetime.now().isoformat(timespec="seconds"); ib=size_of(p); dst=safe_name(p,out,"jpg"); tmp=dst.with_name(dst.stem+".partial.jpg")
    try:
        with Image.open(p) as source:
            date,place=date_place(source); source.seek(0); im=ImageOps.exif_transpose(source)
            if im.mode in ("RGBA","LA") or (im.mode=="P" and "transparency" in im.info):
                rgba=im.convert("RGBA"); canvas=Image.new("RGBA",rgba.size,bg); canvas.alpha_composite(rgba); im=canvas.convert("RGB")
            else: im=im.convert("RGB")
            tag=tag_for(p,place,date,"IMG")
            # Fresh JPEG re-encode removes inherited EXIF/IPTC/XMP; only comment tag is supplied.
            im.save(tmp,format="JPEG",quality=quality,optimize=True,progressive=True,subsampling=0,comment=tag.encode())
        with Image.open(tmp) as chk: chk.verify()
        tmp.replace(dst); ob=size_of(dst); saved=ib-ob
        return dict(timestamp=started,kind="image",source=str(p),output=str(dst),status="ok",input_bytes=ib,output_bytes=ob,saved_bytes=saved,saved_percent=round(saved/ib*100,2) if ib else 0,details=f"JPEG quality={quality}; metadata stripped; tag={tag}; verified")
    except Exception as e:
        try: tmp.unlink(missing_ok=True)
        except OSError: pass
        return dict(timestamp=started,kind="image",source=str(p),output=str(dst),status="error",input_bytes=ib,output_bytes=0,saved_bytes=0,saved_percent=0,details=f"{type(e).__name__}: {e}")

def process_images(paths,output,workers=2,quality=92,background="#ffffff"):
    out=Path(output)/"Image"; out.mkdir(parents=True,exist_ok=True); batches=make_batches(paths); records=[]
    print(f"IMAGE: {len(paths)} files, {len(batches)} batches, {workers} workers, JPEG quality {quality}")
    for bi,batch in enumerate(batches,1):
        print(f"Image batch {bi}/{len(batches)}: {len(batch)} files, {sum(size_of(p) for p in batch)/1024**2:.1f} MiB input")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(one,p,out,quality,background) for p in batch]
            with tqdm(total=len(futures),desc=f"Batch {bi}",unit="file",dynamic_ncols=True) as bar:
                for f in as_completed(futures):
                    records.append(f.result()); bar.update(1)
                    bar.set_postfix(errors=sum(r["status"]!="ok" for r in records if r["kind"]=="image"))
    return records
