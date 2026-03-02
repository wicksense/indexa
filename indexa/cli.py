import argparse
from .rename import scan_and_rename


def main():
    parser = argparse.ArgumentParser(prog="indexa")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan folder and rename PDFs")
    scan.add_argument("path", help="Folder to scan")
    scan.add_argument("--apply", action="store_true", help="Apply renames")
    scan.add_argument("--dry-run", action="store_true", help="Preview only")

    args = parser.parse_args()
    if args.cmd == "scan":
        dry_run = args.dry_run or not args.apply
        scan_and_rename(args.path, dry_run=dry_run)


if __name__ == "__main__":
    main()
