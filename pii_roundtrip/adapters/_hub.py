"""Local model resolution without touching process environment variables."""

from __future__ import annotations

from pii_roundtrip.errors import ModelsNotAvailableError


def local_snapshot(repo_id: str, revision: str, offline: bool) -> str:
    """Path to a pinned model revision in the Hugging Face cache.

    With ``offline=True`` only the local cache is used, so no network request is made;
    a missing model raises :class:`ModelsNotAvailableError`.
    """
    from huggingface_hub import snapshot_download

    try:
        return snapshot_download(repo_id, revision=revision, local_files_only=offline)
    except Exception as e:  # LocalEntryNotFoundError and network errors
        raise ModelsNotAvailableError(
            f"Model {repo_id}@{revision[:7]} is not available locally. Run `pii-roundtrip download-models` once."
        ) from e
