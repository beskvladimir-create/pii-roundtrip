"""Copy the pinned model revisions from the local Hugging Face cache into build/models/hub.

The app ships this folder and points HF_HUB_CACHE at it, so it works offline from the
first launch. Symbolic links of the cache are resolved into plain files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

from pii_roundtrip.adapters import gliner, pii_guard

OUT = Path(__file__).resolve().parents[1] / "build" / "models" / "hub"
PINNED = [(pii_guard.NER_MODEL, pii_guard.NER_REVISION), (gliner.MODEL, gliner.REVISION)]


def main() -> None:
    for repo, rev in PINNED:
        src = Path(snapshot_download(repo, revision=rev, local_files_only=True))
        dst = OUT / f"models--{repo.replace('/', '--')}" / "snapshots" / rev
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("README.md"))
        print(f"{repo}@{rev[:7]}: {sum(f.stat().st_size for f in dst.rglob('*') if f.is_file()) / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
