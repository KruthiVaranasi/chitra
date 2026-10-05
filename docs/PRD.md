# PRD: Chitra (चित्र)

**Offline, natural-language search for personal photo archives**

| | |
|---|---|
| **Author** | Kruthi Varanasi |
| **Status** | v0.1 shipped (MVP). v0.2 in discovery |
| **Last updated** | October 2026 |
| **Links** | [Repo](https://github.com/KruthiVaranasi/chitra) · [Benchmark](../benchmarks/coco_benchmark.py) · [Results](../benchmarks/results.json) |

---

## 1. TL;DR

People keep years of photos on laptops, external hard disks and old backup drives, and the only way to find one is to remember *when* it was taken and scroll through folders. Chitra lets you **describe the photo** ("kids on a beach at sunset") or **show an example** and returns the matches in under a second, **fully offline**. The index lives on the drive itself, so an external disk is searchable on any computer.

The v0.1 MVP is built and benchmarked: **95.1% recall@10** on 5,000 COCO caption queries, ~220 ms per search on a laptop CPU.

---

## 2. Problem

### Origin
I needed reprints of a passport photo taken a year earlier. The studio could only find files by date (year → month → day folders). I didn't remember the date, so I had to accept a lower-quality scan of an old print. The photo existed in their archive, but there was no way to *find* it.

### The general problem
- Photo archives grow every year, and a large share of them live on **local and external storage**, not in the cloud: professionals' client archives, family backups, old phone dumps.
- On local storage, the only search keys are **folder names, file names and dates**. None of them describe what's *in* the photo.
- Cloud apps (Google Photos, Apple Photos) solve content search, but **only for photos uploaded to them**. Many users won't or can't upload: client confidentiality, cost of storage, privacy, or terabytes of old archives.

### What we know vs. what we're assuming

| | Status |
|---|---|
| Content search on local archives isn't available in the default OS tools (Explorer, Finder) | Known |
| Open vision-language models are good enough to search everyday photos by description | **Validated**: 95.1% recall@10 on COCO (Section 8) |
| Photographers search their archives weekly and lose meaningful time doing it | **Assumption**: to validate in user interviews (Section 11) |
| Users value "works offline, on the drive" enough to install a local tool | **Assumption**: to validate |

---

## 3. Why AI, and why not AI at first

My first idea was **face-embedding search for photo studios**: photograph the customer, match the face against the archive, return their past photos.

When I pressure-tested it, **a phone-number lookup solves most of that problem**. It's cheaper, more reliable, and avoids storing biometric data (which is regulated under India's DPDP Act). Face search only won in edge cases. Building it would have been AI for AI's sake.

So I looked for a problem where **AI is the only viable solution**: archives with **no useful metadata**, where what you remember is the *content* ("the one with the red car at night") and nothing else. No rules engine, tag system or database query can answer that. A vision-language model can.

> **Principle:** use AI where the input is unstructured and human (a fuzzy description, a memory) and there's no structured key to search by.

---

## 4. Target users

| Persona | Context | Pain | Priority |
|---|---|---|---|
| **Freelance / wedding photographer** (primary) | Thousands of shots per event, archived to multiple drives, clients asking for "that photo from last year's wedding" | Search time is unbilled time; drives are huge and poorly labelled | **P0**: most acute, most frequent, will pay |
| **Family archivist** | Decade of family photos across 3–6 backup drives | "Which drive has Grandma's 80th birthday?" Emotional value, low tech comfort | P1 |
| **Content creator / editor** | B-roll and stills across SSDs | Finding a specific shot mid-edit | P1 |
| **Small photo studio** | Customer archive sorted by date | The origin story; but a phone-number field solves most cases | P2 |

---

## 5. User stories

1. As a photographer, I want to **type a description** and see matching photos from my archive, so I can deliver a client request in minutes, not an hour.
2. As a user with a **scanned or phone-photographed print**, I want to **search by that image**, so I can find the original high-quality file.
3. As a user looking at a result, I want to **find similar photos**, so I can see the whole burst or the event it came from.
4. As a user with **external drives**, I want the index to **live on the drive**, so I can plug it into any computer and search immediately.
5. As a privacy-conscious user, I want **nothing to leave my machine**.
6. As a user with a large archive, I want indexing to be **incremental and resumable**, so adding 200 new photos doesn't mean re-indexing 50,000.

---

## 6. Goals and non-goals

**Goals (v0.1)**
- Find a described photo in a 10k+ archive in **under 30 seconds of user time**
- **Zero data leaves the device**; zero running cost
- Runs on an ordinary laptop **without a GPU**
- Works on folders **and** removable drives with a portable index

**Non-goals (for now)**
- Photo editing, organising or album management. Chitra is a *search* layer, not a replacement for Lightroom or Photos.
- Cloud sync or multi-device accounts
- Face recognition. Deferred deliberately for privacy reasons (Section 3); may return as opt-in.
- Mobile apps

---

## 7. Solution and scope

### How it works
Each photo is converted once into an embedding by **SigLIP**, an open vision-language model that maps images and text into the same space. A search query is embedded the same way and compared against every photo. The index (SQLite, with relative paths) is stored in a hidden `.chitra/` folder **on the drive being indexed**.

### Requirements

| # | Requirement | Priority | v0.1 status |
|---|---|---|---|
| R1 | Natural-language text search with ranked results | P0 | ✅ Shipped |
| R2 | Search by example image (upload or drag-and-drop) | P0 | ✅ Shipped |
| R3 | Index stored on the drive with relative paths | P0 | ✅ Shipped |
| R4 | Incremental, resumable indexing | P0 | ✅ Shipped |
| R5 | Local web UI: grid, viewer, "show in folder" | P0 | ✅ Shipped |
| R6 | "Find similar" from any result | P1 | ✅ Shipped |
| R7 | Filter by year (EXIF date) | P1 | ✅ Shipped |
| R8 | HEIC (iPhone) support | P1 | ✅ Shipped |
| R9 | **Search across all drives, including ones not plugged in** | P1 | 🔜 v0.2 |
| R10 | Relevance threshold ("no good match found") | P1 | 🔜 v0.2 |
| R11 | One-click installer (no Python required) | P1 | 🔜 v0.2 |
| R12 | Multilingual queries (Hindi and other Indian languages) | P2 | Later |
| R13 | Video search (sampled frames), OCR for screenshots | P2 | Later |

---

## 8. Success metrics

Model quality is necessary but not sufficient. **Recall is a proxy; time-to-find is the outcome.**

| Layer | Metric | Target | Current |
|---|---|---|---|
| **North star** | Median time to find a target photo vs. folder browsing | ≥ 5× faster | To measure (Section 11) |
| Model quality | Recall@10, COCO 1k (5,001 caption queries) | ≥ 90% | **95.1%** ✅ |
| Model quality | Recall@1 | ≥ 60% | **67.8%** ✅ |
| Experience | Search latency, end to end, laptop CPU | < 500 ms | **~220 ms** ✅ |
| Experience | Time to first search on a 10k-photo drive (indexing) | < 1 hour on CPU | ~46 min (at ~3.6 photos/s) ⚠️ |
| Adoption *(post-launch)* | % of searches where a result is opened | ≥ 60% | — |
| Adoption *(post-launch)* | Weekly searches per active user | Track | — |
| **Guardrail** | Data sent off-device | 0 bytes (model download only) | ✅ 0 |
| **Guardrail** | Incorrect results shown with high confidence | Minimise; see R10 | Not yet handled |

---

## 9. Competitive landscape

| | Google / Apple Photos | Immich / PhotoPrism | OS file search | **Chitra** |
|---|---|---|---|---|
| Content-based search | ✅ | ✅ | ❌ | ✅ |
| Works on local and external drives | ❌ cloud / own library | ⚠️ needs a server or Docker | ✅ | ✅ |
| Index travels with the drive | ❌ | ❌ | ❌ | ✅ |
| No upload / fully private | ❌ | ✅ | ✅ | ✅ |
| Setup effort | Low | High | None | Low–medium (improves with R11) |

**Positioning:** *For photographers and anyone with photos spread across drives, Chitra is offline photo search that lives on the drive itself. Unlike cloud photo apps, nothing is uploaded. Unlike self-hosted servers, there's nothing to run.*

**Differentiator to protect:** the drive-native index, and the v0.2 "search drives that aren't plugged in". No competitor above does this.

---

## 10. Key decisions and trade-offs

| Decision | Chosen | Alternatives | Why |
|---|---|---|---|
| Model | **SigLIP base** (Apache-2.0) | CLIP ViT-B/32; jina-clip-v2 | Better accuracy than CLIP at the same size; **commercially usable license** (jina-clip-v2 is non-commercial); runs on CPU |
| Inference location | **On-device** | Cloud API | Privacy is the core value proposition; zero marginal cost. Trade-off: slower first-time indexing on CPU |
| Vector search | **Exact brute force (NumPy)** | FAISS, vector database | At personal scale (≤200k photos) exact search takes milliseconds; no extra infrastructure or sync bugs. Revisit above ~1M photos |
| Index location | **On the drive, relative paths** | Central index on the computer | Makes external drives portable across machines and drive letters. This is the differentiator |
| Change detection | **File size + modified time** | Content hashing | Re-scans 100k files in seconds instead of re-reading terabytes |
| Interface | **Local web UI + CLI** | Native desktop app | Fastest path to a usable MVP; a native installer is v0.2 (R11) |

---

## 11. Risks and mitigations

| Risk | Type | Mitigation |
|---|---|---|
| **Always returns *something*, even when nothing matches** (e.g. "pizza" returns a sandwich) | AI / UX | R10: calibrated relevance threshold plus a "no strong matches" state; show the match score |
| **Known model weak spots:** text-heavy images, very specific counts ("exactly 3 people"), niche or regional concepts | AI quality | Failure-mode analysis on real archives; OCR (R13) for screenshots; evaluate larger SigLIP variants |
| **Bias:** model trained on web data may perform unevenly across cultures and skin tones, and may handle Indian contexts poorly (festivals, attire, food) | AI ethics | Build an Indian-context evaluation set; evaluate multilingual models (R12) |
| Indexing is slow on low-end CPUs (~3.6 photos/s) | Performance | Resumable indexing (shipped); GPU auto-detection (shipped); quantised ONNX model; index overnight |
| 800 MB model download is a barrier on slow connections | Adoption | One-time download; offer a smaller CLIP model option |
| Python install is too technical for the family-archivist persona | Adoption | R11 one-click installer |
| Users assume a photo doesn't exist if it isn't in the top results | Trust | Show 60 results, "find similar" to explore, clear scores |

---

## 12. Validation plan (next 4 weeks)

1. **User interviews (n = 5–8):** photographers and people with backup drives. Learn how often they search, how they search today, how long it takes, and what they'd pay. *Kill criterion:* fewer than half search their archives at least monthly → the wedge is wrong; re-evaluate the persona.
2. **Time-to-find study (n = 8–10):** 10 target photos in a 20k-photo archive. Compare folder browsing with Chitra, recording median time and completion rate. This measures the north-star metric.
3. **Failure analysis:** run 100 real queries on a real personal archive and categorise the misses (text, counts, cultural concepts, low light). The results feed the risk table and the roadmap.

---

## 13. Roadmap

| Now (v0.2) | Next | Later |
|---|---|---|
| Multi-drive search, including offline drives (R9) | Multilingual queries (R12) | Video search, OCR (R13) |
| Relevance threshold / "no match" state (R10) | Auto-index when a drive is connected | Opt-in face grouping |
| One-click Windows installer (R11) | Indian-context evaluation set | Studio edition (archive + customer lookup) |

**Prioritisation rationale:** R9 deepens the one advantage no competitor has. R10 fixes the biggest trust risk. R11 unlocks the non-technical personas. Features where Chitra would only reach parity (albums, editing) are deliberately out.

---

## 14. Open questions

- Is the photographer persona's pain frequent enough to pay for, or is this a free tool with a pro tier (multi-drive, studio features)?
- What relevance-score threshold gives the best balance between "no results" and wrong results? This needs calibration on real archives, not COCO.
- Would users accept a smaller, faster model in exchange for slightly lower accuracy? Test both in the time-to-find study.
- How should Chitra handle shared or networked drives (NAS) with multiple users?

---

## Appendix: benchmark details

**Dataset:** COCO Karpathy test split; 1,000 images, 5 human captions each (5,001 queries).
**Method:** every caption is a query; we record the rank of its source image among all 1,000.
**Hardware:** consumer laptop, CPU only.

| Recall@1 | Recall@5 | Recall@10 | Median rank | Search latency | Indexing |
|---|---|---|---|---|---|
| 67.8% | 89.9% | 95.1% | #1 | ~220 ms | ~3.6 photos/s |

Reproduce: `python benchmarks/coco_benchmark.py --n 1000`
