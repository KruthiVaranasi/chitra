"""Text-to-image retrieval benchmark on COCO (Karpathy test split).

Downloads N test images with their 5 human-written captions, indexes them with
Chitra, then uses every caption as a search query and checks where the correct
image ranks.

    python benchmarks/coco_benchmark.py --n 1000
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chitra.indexer import index  # noqa: E402
from chitra.search import Searcher  # noqa: E402

ROWS_API = "https://datasets-server.huggingface.co/rows?dataset=yerevann/coco-karpathy&config=default&split=test"


def fetch_rows(n: int) -> list:
    rows = []
    while len(rows) < n:
        url = f"{ROWS_API}&offset={len(rows)}&length={min(100, n - len(rows))}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            page = json.load(resp)["rows"]
        if not page:
            break
        rows += [r["row"] for r in page]
    return rows


def download(row: dict, dest: Path) -> bool:
    path = dest / row["filename"]
    if path.exists() and path.stat().st_size > 0:
        return True
    try:
        urllib.request.urlretrieve(row["url"], path)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000, help="number of test images")
    ap.add_argument("--data", default=str(Path(__file__).parent / "data" / "coco"))
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    captions_file = data / "captions.json"
    if captions_file.exists() and len(json.loads(captions_file.read_text())) >= args.n:
        rows = json.loads(captions_file.read_text())[: args.n]
    else:
        print(f"Fetching {args.n} captioned images from the COCO Karpathy test split ...")
        rows = fetch_rows(args.n)
        captions_file.write_text(json.dumps(rows))
    with ThreadPoolExecutor(16) as pool:
        ok = list(pool.map(lambda r: download(r, data), rows))
    rows = [r for r, good in zip(rows, ok) if good]
    print(f"{len(rows)} images ready in {data}")

    stats = index(data, args.model, rebuild=bool(args.model))

    searcher = Searcher(data)
    path_to_row = {searcher.store.get(int(i))["path"]: n for n, i in enumerate(searcher.ids)}
    queries, targets = [], []
    for r in rows:
        if r["filename"] in path_to_row:
            for caption in r["sentences"]:
                queries.append(caption.strip())
                targets.append(path_to_row[r["filename"]])

    # Encode all captions in batches, then rank every image for every caption.
    t0 = time.time()
    text_vecs = np.vstack([searcher.embedder.encode_text(queries[i : i + 64]) for i in range(0, len(queries), 64)])
    scores = text_vecs @ searcher.matrix.T
    target_scores = scores[np.arange(len(targets)), targets]
    ranks = (scores > target_scores[:, None]).sum(axis=1) + 1
    encode_secs = time.time() - t0

    latencies = []
    for q in queries[:50]:
        t = time.perf_counter()
        searcher.search_text(q, k=10)
        latencies.append((time.perf_counter() - t) * 1000)

    n_img = len(searcher)
    result = {
        "model": searcher.model_name,
        "images": n_img,
        "queries": len(queries),
        "recall@1": float((ranks <= 1).mean()),
        "recall@5": float((ranks <= 5).mean()),
        "recall@10": float((ranks <= 10).mean()),
        "median_rank": float(np.median(ranks)),
        "index_img_per_sec": round(stats.added / stats.seconds, 1) if stats.added else None,
        "search_ms_median": round(statistics.median(latencies), 1),
        "query_encode_ms_avg": round(encode_secs / len(queries) * 1000, 1),
    }
    (Path(__file__).parent / "results.json").write_text(json.dumps(result, indent=2))

    print()
    print(f"Model: {result['model']}  |  {n_img} images  |  {len(queries)} caption queries")
    print("| Metric | Value |\n|---|---|")
    print(f"| Recall@1 | {result['recall@1']:.1%} |")
    print(f"| Recall@5 | {result['recall@5']:.1%} |")
    print(f"| Recall@10 | {result['recall@10']:.1%} |")
    print(f"| Median rank of correct image | {result['median_rank']:.0f} of {n_img} |")
    if result["index_img_per_sec"]:
        print(f"| Indexing speed | {result['index_img_per_sec']} images/sec |")
    print(f"| Search latency (median, end to end) | {result['search_ms_median']} ms |")


if __name__ == "__main__":
    main()
