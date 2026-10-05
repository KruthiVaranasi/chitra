"""Command line: chitra index | search | serve | stats"""

import argparse
import sys
import time
import webbrowser
from pathlib import Path

from .config import DEFAULT_MODEL


def cmd_index(args):
    from .indexer import ModelMismatch, index

    start = time.time()
    try:
        s = index(Path(args.path), args.model, batch_size=args.batch_size, workers=args.workers, rebuild=args.rebuild)
    except ModelMismatch as exc:
        sys.exit(str(exc))
    took = time.time() - start
    rate = f" ({s.added / s.seconds:.1f} img/s)" if s.added and s.seconds else ""
    print(
        f"Scanned {s.scanned} images: {s.added} indexed, {s.unchanged} unchanged, "
        f"{s.removed} removed, {s.failed} unreadable. {took:.1f}s{rate}"
    )


def cmd_search(args):
    from .search import Searcher

    searcher = Searcher(Path(args.path))
    filters = {"year_from": args.year_from, "year_to": args.year_to}
    if args.image:
        from PIL import Image

        results = searcher.search_image(Image.open(args.image), args.k, **filters)
    elif args.query:
        results = searcher.search_text(" ".join(args.query), args.k, **filters)
    else:
        sys.exit("Give a text query or --image FILE")
    for r in results:
        date = (r["taken_at"] or "")[:10]
        print(f"{r['score']:.3f}  {date:10}  {searcher.store.abspath(r['path'])}")


def cmd_serve(args):
    import uvicorn

    from .search import Searcher
    from .server import create_app

    searcher = Searcher(Path(args.path))
    print(f"Loading model {searcher.model_name} ...")
    searcher.embedder  # load up front so the first search is fast
    url = f"http://127.0.0.1:{args.port}"
    print(f"Chitra is serving {len(searcher)} images from {searcher.store.root} at {url}")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(create_app(searcher), host="127.0.0.1", port=args.port, log_level="warning")


def cmd_stats(args):
    from .store import Store

    store = Store(Path(args.path), create=False)
    print(f"Root:       {store.root}")
    print(f"Model:      {store.get_meta('model')}")
    print(f"Indexed:    {store.count()}")
    print(f"Unreadable: {store.failure_count()}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="chitra", description="Search your photos by describing them. Offline, on any drive.")
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("index", help="index (or update the index of) a folder or drive")
    pi.add_argument("path")
    pi.add_argument("--model", help=f"Hugging Face model id (default: {DEFAULT_MODEL})")
    pi.add_argument("--batch-size", type=int, default=16)
    pi.add_argument("--workers", type=int, default=4, help="image decoding threads")
    pi.add_argument("--rebuild", action="store_true", help="discard the existing index first")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="search from the terminal")
    ps.add_argument("path")
    ps.add_argument("query", nargs="*")
    ps.add_argument("--image", help="find photos similar to this image file")
    ps.add_argument("-k", type=int, default=10)
    ps.add_argument("--year-from", type=int)
    ps.add_argument("--year-to", type=int)
    ps.set_defaults(func=cmd_search)

    pv = sub.add_parser("serve", help="open the search UI in your browser")
    pv.add_argument("path")
    pv.add_argument("--port", type=int, default=8765)
    pv.add_argument("--no-browser", action="store_true")
    pv.set_defaults(func=cmd_serve)

    pt = sub.add_parser("stats", help="show index info")
    pt.add_argument("path")
    pt.set_defaults(func=cmd_stats)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except FileNotFoundError as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        sys.exit("\nStopped. Progress so far is saved; run the same command to resume.")


if __name__ == "__main__":
    main()
