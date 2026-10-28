# One Foundation Media Pipeline V1

A fresh, modular Python CLI for scanning iPhone media, converting images to JPG and videos to MP4, removing source metadata, adding a minimal One Foundation tag, verifying output, and reporting storage savings. Originals are never deleted.

## Reality check
- 9 GB of ordinary photos cannot generally be reduced to 900 MB losslessly. JPEG output is lossy; quality 92 is the visual-quality-first default.
- Video target size is not guaranteed. CRF controls quality, not exact output size. Try CRF 22 first; lower means larger/better quality.
- The tag uses capture date/time from EXIF when available, otherwise file modified time. A three-letter place token is included only if a textual place field exists. GPS is not reverse-geocoded.
- Transparent images are composited onto white because JPG does not support transparency.
- Images use bounded parallel workers; videos encode sequentially to protect 4 GB RAM systems.
- Batches cap total input size at 2 GiB. One file larger than 2 GiB is processed alone.
- Original resolution and frame rate are retained by default. All original files remain untouched.

## Setup (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```
FFmpeg and FFprobe must be installed and available on PATH.

## Commands
```powershell
py main.py scan --source "village-OS/iphone_media_suite/V2/test 1/input"
py main.py images --source "village-OS/iphone_media_suite/V2/test 1/input" --output ".\output" --workers 2 --quality 92
py main.py videos --source "D:\iPhone\gyan" --crf 22
py main.py all --source "village-OS/iphone_media_suite/V2/test 1/input".\output" --workers 2 --quality 92 --crf 22
```
Outputs: `output\Image\*.jpg`, `output\Video\*.mp4`, and timestamped CSV/JSONL reports in `output\reports`.
