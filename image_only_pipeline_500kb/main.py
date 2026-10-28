import argparse
from pathlib import Path
from modules.image_pipeline import scan_images, run_images

def main():
    parser = argparse.ArgumentParser(description="Image-only compression pipeline. Video files are ignored.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--source", required=True)
    images = sub.add_parser("images")
    images.add_argument("--source", required=True)
    images.add_argument("--output", required=True)
    images.add_argument("--workers", type=int, default=2)
    images.add_argument("--max-mp", type=float, default=16)
    images.add_argument("--quality", type=int, default=88)
    images.add_argument("--target-kb", type=int, default=500)
    images.add_argument("--max-kb", type=int, default=1024)
    args = parser.parse_args()
    if args.command == "scan":
        scan_images(Path(args.source))
    else:
        if not 1 <= args.workers <= 8:
            parser.error("--workers must be between 1 and 8")
        if not 1 <= args.quality <= 95:
            parser.error("--quality must be between 1 and 95")
        if args.max_mp < 0:
            parser.error("--max-mp must be >= 0 (0 disables initial resizing)")
        if args.target_kb < 50 or args.max_kb < args.target_kb:
            parser.error("--target-kb must be >= 50 and --max-kb must be >= --target-kb")
        run_images(Path(args.source), Path(args.output), args.workers, args.max_mp,
                   args.quality, args.target_kb * 1024, args.max_kb * 1024)

if __name__ == "__main__":
    main()
