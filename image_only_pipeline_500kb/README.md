# Image-only compression pipeline

Images only. Video files are ignored. Original files are never deleted or modified.

Default target is 500 KB per image. The hard maximum is 1 MB (1024 KB). To meet the 500 KB target, quality is reduced first and resolution is reduced if necessary. This can visibly soften some images; inspect sample outputs before processing your full library.

## Install (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Scan
```powershell
.\.venv\Scripts\python.exe main.py scan --source "C:\Users\gione\OneDrive\Desktop\01_BUSINESS\diwali\jpg"
```

## Process
```powershell
.\.venv\Scripts\python.exe main.py images --source "C:\Users\gione\OneDrive\Pictures\whatsapp\iphone" --output ".\image_output" --workers 2 --max-mp 16 --quality 88 --target-kb 500 --max-kb 1024
```

Outputs are JPGs and `reports\image_report.csv`. PNG transparency is composited onto white because JPG does not support transparency. Metadata is stripped. A strict 500 KB target may require downscaling. Originals remain untouched.
