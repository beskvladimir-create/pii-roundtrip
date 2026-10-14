"""Однократный прогон на отложенном наборе (data/holdout, хеши в HOLDOUT.md).

python -m eval.holdout [--set2] --tools pii_roundtrip,pii_guard,gliner_guard,presidio,privacy_filter,prompt_anonymizer,regex_baseline
Перед запуском сверяет SHA-256 файлов с HOLDOUT.md.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from eval import run


def check_hashes(folder: str) -> None:
    expected = dict(re.findall(r"\| (" + folder + r"/\w+\.jsonl) \| `([0-9a-f]{64})` \|", Path("HOLDOUT.md").read_text()))
    if not expected:
        sys.exit(f"В HOLDOUT.md нет хешей для {folder}")
    for path, h in expected.items():
        actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if actual != h:
            sys.exit(f"{path}: хеш не совпадает с HOLDOUT.md")
    print("Хеши отложенного набора совпадают с HOLDOUT.md")


if __name__ == "__main__":
    n = "2" if "--set2" in sys.argv else ""
    args = [a for a in sys.argv[1:] if a != "--set2"]
    folder = f"data/holdout{n}"
    check_hashes(folder)
    run.DATASETS.update({f"holdout{n}_ru": (f"{folder}/ru.jsonl", "ru"), f"holdout{n}_uk": (f"{folder}/uk.jsonl", "uk")})
    sys.argv = [sys.argv[0]] + args + ["--datasets", f"holdout{n}_ru,holdout{n}_uk"]
    run.main()
