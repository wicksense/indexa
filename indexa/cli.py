import argparse
from .rename import scan_and_rename, undo_renames, watch_and_rename


def _add_common_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", help="Folder to scan/watch")
    p.add_argument("--apply", action="store_true", help="Apply renames")
    p.add_argument("--dry-run", action="store_true", help="Preview only")
    p.add_argument("--title-words", type=int, default=8, help="Max words kept from title (default: 8)")
    p.add_argument(
        "--template",
        default="{first_author_last}-{short_title}-{year}",
        help="Filename template (tokens: {first_author_last}, {short_title}, {year})",
    )
    p.add_argument(
        "--undo-log",
        default=".indexa-renames.jsonl",
        help="Path to JSONL rename log (default: .indexa-renames.jsonl in target folder)",
    )


def main():
    parser = argparse.ArgumentParser(prog="indexa")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan folder and rename PDFs")
    _add_common_options(scan)

    watch = sub.add_parser("watch", help="Watch folder and rename new PDFs")
    _add_common_options(watch)
    watch.add_argument("--interval", type=float, default=3.0, help="Polling interval seconds (default: 3)")

    undo = sub.add_parser("undo", help="Undo renames from the log")
    undo.add_argument("path", help="Folder containing PDFs / undo log")
    undo.add_argument(
        "--undo-log",
        default=".indexa-renames.jsonl",
        help="Path to JSONL rename log (default: .indexa-renames.jsonl in target folder)",
    )
    undo.add_argument("--steps", type=int, default=0, help="Undo last N renames (default: all)")
    undo.add_argument("--apply", action="store_true", help="Apply undo operations")
    undo.add_argument("--dry-run", action="store_true", help="Preview only")

    args = parser.parse_args()
    dry_run = args.dry_run or not args.apply

    if args.cmd == "scan":
        scan_and_rename(
            args.path,
            dry_run=dry_run,
            title_words=args.title_words,
            undo_log_path=args.undo_log,
            template=args.template,
        )
    elif args.cmd == "watch":
        watch_and_rename(
            args.path,
            dry_run=dry_run,
            title_words=args.title_words,
            undo_log_path=args.undo_log,
            interval=args.interval,
            template=args.template,
        )
    elif args.cmd == "undo":
        undo_dry_run = args.dry_run or not args.apply
        undo_renames(
            args.path,
            undo_log_path=args.undo_log,
            steps=args.steps,
            dry_run=undo_dry_run,
        )


if __name__ == "__main__":
    main()
