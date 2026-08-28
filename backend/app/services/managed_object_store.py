"""Private content-addressed local object store for constrained single-node deployment."""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path


class ManagedObjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise ValueError("object key escapes managed store")
        return path

    def put(self, payload: bytes, suffix: str = ".zip") -> tuple[str, str, Path]:
        digest = hashlib.sha256(payload).hexdigest()
        key = f"sha256/{digest[:2]}/{digest}{suffix}"
        destination = self.path_for(key)
        if destination.exists(): return digest, key, destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary, "xb") as handle:
                handle.write(payload); handle.flush(); os.fsync(handle.fileno())
            try: os.replace(temporary, destination)
            except FileExistsError: pass
        finally:
            temporary.unlink(missing_ok=True)
        return digest, key, destination
