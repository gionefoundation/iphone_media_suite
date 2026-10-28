import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".bmp", ".tif", ".tiff", ".webp"}
BATCH_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
REPORT_LOCK = threading.Lock()
REPORT_FIELDS = ["source", "output", "input_bytes", "output_bytes", "saved_bytes", "status", "note"]

def human(n):
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

def media_files(source, output=None):
    source = source.resolve()
    output = output.resolve() if output else None
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        resolved = path.resolve()
        if output and (resolved == output or output in resolved.parents):
            continue
        yield path

def scan_images(source):
    files = sorted(media_files(source))
    total = sum(p.stat().st_size for p in files)
    print(f"Images found: {len(files)}")
    print(f"Total input size: {human(total)}")
    print("Video files are ignored. Original files are never deleted or modified.")

def make_batches(paths):
    batches, current, size = [], [], 0
    for path in paths:
        file_size = path.stat().st_size
        if current and size + file_size > BATCH_LIMIT_BYTES:
            batches.append(current)
            current, size = [], 0
        current.append(path)
        size += file_size
        if file_size > BATCH_LIMIT_BYTES:
            batches.append(current)
            current, size = [], 0
    if current:
        batches.append(current)
    return batches

def destination_for(src, source, output):
    rel = src.relative_to(source)
    dst = (output / rel).with_suffix(".jpg")
    if dst.resolve() == src.resolve():
        dst = dst.with_name(dst.stem + "__compressed.jpg")
    if dst.exists():
        dst = dst.with_name(f"{dst.stem}__from_{src.suffix.lower().lstrip('.')} .jpg".replace(" ", ""))
        counter = 2
        original = dst
        while dst.exists():
            dst = original.with_name(f"{original.stem}_{counter}{original.suffix}")
            counter += 1
    return dst

def write_jpeg(image, path, quality):
    # Explicitly omit EXIF, ICC, comments, and source metadata.
    image.save(path, format="JPEG", quality=quality, optimize=True,
               progressive=True, subsampling=2, exif=b"")

def prepare_image(src, max_mp):
    with Image.open(src) as opened:
        opened.load()
        image = ImageOps.exif_transpose(opened)
        image.load()
    if max_mp > 0:
        megapixels = (image.width * image.height) / 1_000_000
        if megapixels > max_mp:
            scale = (max_mp / megapixels) ** 0.5
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS
            )
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and image.info.get("transparency") is not None
    )
    if has_alpha:
        rgba = image.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, (255, 255, 255))
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        return rgb
    return image.convert("RGB")

def encode_to_target(image, tmp, target_bytes, max_bytes, starting_quality, source_is_jpeg):
    # Pass 1: reduce quality progressively, keeping resolution when possible.
    qualities = []
    q = min(95, max(40, starting_quality))
    while q >= 40:
        qualities.append(q)
        q -= 6
    if 40 not in qualities:
        qualities.append(40)

    attempts = []
    for quality in qualities:
        write_jpeg(image, tmp, quality)
        size = tmp.stat().st_size
        attempts.append((size, quality, image.size))
        if size <= target_bytes:
            return size, quality, image.size, "target_met"
        if size <= max_bytes:
            # Continue searching for target, but keep a safe valid encoding available.
            continue

    # Pass 2: target not reached with quality alone. Downscale progressively.
    # Never upscale. Shrink by about 15% per iteration until target or practical minimum.
    working = image
    while working.width > 320 or working.height > 320:
        new_size = (max(1, int(working.width * 0.85)), max(1, int(working.height * 0.85)))
        working = working.resize(new_size, Image.Resampling.LANCZOS)
        for quality in (76, 68, 60, 52, 44, 40):
            write_jpeg(working, tmp, quality)
            size = tmp.stat().st_size
            attempts.append((size, quality, working.size))
            if size <= target_bytes:
                return size, quality, working.size, "target_met_after_resize"

    # Hard max fallback: reduce dimensions more aggressively and encode low quality.
    # This is a hard cap for normal decodable images; if even tiny image exceeds it, fail safely.
    working = image
    for _ in range(12):
        working = working.resize(
            (max(1, int(working.width * 0.7)), max(1, int(working.height * 0.7))),
            Image.Resampling.LANCZOS
        )
        for quality in (40, 32, 25):
            write_jpeg(working, tmp, quality)
            size = tmp.stat().st_size
            attempts.append((size, quality, working.size))
            if size <= max_bytes:
                return size, quality, working.size, "max_limit_met_after_strong_resize"

    # Choose the smallest result encountered. Do not silently claim it meets the cap.
    smallest = min(attempts, key=lambda x: x[0])
    size, quality, dims = smallest
    # Recreate the smallest known candidate from original using dimensions recorded.
    fallback = image.resize(dims, Image.Resampling.LANCZOS) if image.size != dims else image
    write_jpeg(fallback, tmp, quality)
    final_size = tmp.stat().st_size
    if final_size > max_bytes:
        raise RuntimeError(f"Could not meet max file size {max_bytes} bytes; smallest result was {final_size} bytes")
    return final_size, quality, dims, "max_limit_met_fallback"

def write_report(output, row):
    report_dir = output / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "image_report.csv"
    with REPORT_LOCK:
        is_new = not report_path.exists() or report_path.stat().st_size == 0
        with report_path.open("a", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

def image_job(src, source, output, max_mp, quality, target_bytes, max_bytes):
    before = src.stat().st_size
    dst = destination_for(src, source, output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".partial.jpg")
    try:
        image = prepare_image(src, max_mp)
        size, used_quality, dims, note = encode_to_target(
            image, tmp, target_bytes, max_bytes, quality, src.suffix.lower() in {".jpg", ".jpeg"}
        )
        os.replace(tmp, dst)
        after = dst.stat().st_size
        note = f"{note}; quality={used_quality}; dimensions={dims[0]}x{dims[1]}"
        write_report(output, {"source": str(src), "output": str(dst), "input_bytes": before,
            "output_bytes": after, "saved_bytes": before-after, "status": "ok", "note": note})
        return before, after, "ok", after <= target_bytes, after <= max_bytes
    except Exception as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        note = f"{type(exc).__name__}: {exc}"
        write_report(output, {"source": str(src), "output": "", "input_bytes": before,
            "output_bytes": 0, "saved_bytes": 0, "status": "error", "note": note})
        return before, 0, "error", False, False

def run_images(source, output, workers, max_mp, quality, target_bytes, max_bytes):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must not be the same as, or inside, the source folder.")
    files = sorted(media_files(source, output))
    batches = make_batches(files)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "reports" / "image_report.csv"
    if report_path.exists():
        report_path.unlink()
    print(f"Images: {len(files)} | batches: {len(batches)} | workers: {workers}")
    print(f"Target: <= {target_bytes // 1024} KB where practical; HARD MAX: <= {max_bytes // 1024} KB")
    print("Note: meeting the 500 KB target may require reducing resolution; originals stay untouched.")
    total_in = total_out = errors = target_met = max_met = 0
    for index, batch in enumerate(batches, 1):
        batch_size = sum(p.stat().st_size for p in batch)
        print(f"\\nBatch {index}/{len(batches)}: {len(batch)} files, {human(batch_size)} input")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(image_job, p, source, output, max_mp, quality, target_bytes, max_bytes) for p in batch]
            with tqdm(total=len(futures), desc=f"Images {index}", unit="file", dynamic_ncols=True) as bar:
                for future in as_completed(futures):
                    before, after, status, target_ok, max_ok = future.result()
                    total_in += before
                    total_out += after
                    errors += int(status != "ok")
                    target_met += int(target_ok)
                    max_met += int(max_ok)
                    bar.set_postfix(saved=human(total_in-total_out), under_target=target_met, errors=errors)
                    bar.update(1)
    print(f"\\nSummary: input {human(total_in)} | output {human(total_out)} | net saved {human(total_in-total_out)}")
    print(f"Under target: {target_met}/{len(files)} | Under hard max: {max_met}/{len(files)} | errors: {errors}")
    print(f"Report: {report_path}")
