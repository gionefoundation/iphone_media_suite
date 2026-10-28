# Image-only compression pipeline

This project processes images only. Video files are ignored. Originals are never modified or deleted.

## Install (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Scan
```powershell
.\.venv\Scripts\python.exe main.py scan --source "C:\Users\gione\OneDrive\Desktop\One\village-OS\iphone_media_suite\V2\test 1\input\Image"
```

## Process images
```powershell
.\.venv\Scripts\python.exe main.py images --source "C:\Users\gione\OneDrive\Desktop\One\village-OS\iphone_media_suite\V2\test 1\input\Image" --output "C:\path\to\image_output" --workers 2 --max-mp 16 --quality 88
```
ST. PAULS INTER COLLEGE
Outputs are JPGs and `reports\image_report.csv`. PNG transparency is composited onto white because JPG does not support transparency. Metadata is stripped. Existing JPEGs are retried at lower quality if recompression makes them larger. Test a small folder first.
