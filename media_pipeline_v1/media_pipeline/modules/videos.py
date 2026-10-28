from pathlib import Path
from datetime import datetime
import subprocess,shutil,json
from tqdm import tqdm
from config import BATCH_LIMIT_BYTES
from media_pipeline.modules.common import make_batches,size_of,safe_name,tag_for

def probe(p):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,width,height,r_frame_rate,codec_name","-of","json",str(p)],capture_output=True,text=True,check=True)
    return json.loads(r.stdout)

def has_x265():
    r=subprocess.run(["ffmpeg","-hide_banner","-encoders"],capture_output=True,text=True,timeout=20)
    return "libx265" in r.stdout+r.stderr

def one(p,out,crf,x265):
    started=datetime.now().isoformat(timespec="seconds"); ib=size_of(p); dst=safe_name(p,out,"mp4"); tmp=dst.with_name(dst.stem+".partial.mp4")
    try:
        meta=probe(p); duration=float(meta.get("format",{}).get("duration") or 0); enc="libx265" if x265 else "libx264"; c=crf if x265 else max(18,min(25,crf)); tag=tag_for(p,prefix="VID")
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(p),"-map","0:v:0","-map","0:a?","-sn","-dn","-map_metadata","-1","-c:v",enc,"-preset","medium","-crf",str(c),"-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-movflags","+faststart","-metadata",f"comment={tag}","-progress","pipe:1",str(tmp)]
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1); pct=0
        with tqdm(total=100,desc=p.name[:22],unit="%",leave=False,dynamic_ncols=True) as bar:
            for line in proc.stdout:
                if line.startswith("out_time_ms=") and duration:
                    try:
                        n=min(99,int(int(line.split("=",1)[1])/(duration*1_000_000)*100))
                        if n>pct:bar.update(n-pct);pct=n
                    except Exception:pass
                elif line.strip()=="progress=end":
                    if pct<100:bar.update(100-pct)
                    break
        err=proc.stderr.read() if proc.stderr else ""; rc=proc.wait()
        if rc: raise RuntimeError(err[-1200:] or f"ffmpeg exit {rc}")
        if not tmp.exists() or not tmp.stat().st_size: raise RuntimeError("Empty output")
        verify=subprocess.run(["ffmpeg","-v","error","-i",str(tmp),"-f","null","-"],capture_output=True,text=True)
        if verify.returncode: raise RuntimeError("Output decode verification failed: "+verify.stderr[-800:])
        om=probe(tmp); od=float(om.get("format",{}).get("duration") or 0)
        if duration and abs(duration-od)>max(1,duration*.01): raise RuntimeError(f"Duration mismatch: {duration:.2f}s vs {od:.2f}s")
        tmp.replace(dst); ob=size_of(dst); saved=ib-ob
        return dict(timestamp=started,kind="video",source=str(p),output=str(dst),status="ok",input_bytes=ib,output_bytes=ob,saved_bytes=saved,saved_percent=round(saved/ib*100,2) if ib else 0,details=f"{enc} CRF={c}; duration={od:.2f}s; metadata stripped; tag={tag}; decode verified")
    except Exception as e:
        try:tmp.unlink(missing_ok=True)
        except OSError:pass
        return dict(timestamp=started,kind="video",source=str(p),output=str(dst),status="error",input_bytes=ib,output_bytes=0,saved_bytes=0,saved_percent=0,details=f"{type(e).__name__}: {e}")

def process_videos(paths,output,crf=22):
    if not paths:return []
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):raise SystemExit("Install FFmpeg and FFprobe and ensure both work in PowerShell.")
    out=Path(output)/"Video"; out.mkdir(parents=True,exist_ok=True); batches=make_batches(paths); x=has_x265(); records=[]
    print(f"VIDEO: {len(paths)} files, {len(batches)} batches, one encoder at a time, {'libx265' if x else 'libx264'}, CRF={crf}")
    for bi,batch in enumerate(batches,1):
        print(f"Video batch {bi}/{len(batches)}: {len(batch)} files, {sum(size_of(p) for p in batch)/1024**2:.1f} MiB input")
        with tqdm(total=len(batch),desc=f"Video batch {bi}",unit="file",dynamic_ncols=True) as bar:
            for p in batch:
                r=one(p,out,crf,x); records.append(r); bar.update(1); bar.set_postfix(status=r["status"],saved=f"{r['saved_percent']}%")
    return records
