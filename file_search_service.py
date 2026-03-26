"""Thin wrapper: File Search store + upload_to_file_search_store + generate_content."""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from config import Config

logger = logging.getLogger(__name__)


def _to_jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:
            return str(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(i) for i in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


class FileSearchRAG:

    def __init__(self) -> None:
        self._client = None
        self._store_name: Optional[str] = None

    def _load_state(self) -> Optional[str]:
        path = Path(Config.STORE_STATE_FILE)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("name")
            if isinstance(name, str) and name.startswith("fileSearchStores/"):
                return name
        except Exception as e:
            logger.warning("Could not read store state file: %s", e)
        return None

    def _save_state(self, store_name: str) -> None:
        try:
            Path(Config.STORE_STATE_FILE).write_text(
                json.dumps({"name": store_name}, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Could not persist store name: %s", e)

    def invalidate_store(self) -> None:
        """Drop cached store and local state (e.g. after API 404 or stale id)."""
        self._store_name = None
        try:
            Path(Config.STORE_STATE_FILE).unlink(missing_ok=True)
        except OSError:
            pass

    def client(self):
        if self._client is None:
            if not Config.GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY is not set")
            from google import genai

            self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
            if not hasattr(self._client, "file_search_stores"):
                raise RuntimeError(
                    "google-genai is too old (need >=1.49.0 for File Search). "
                    "If you use a venv, upgrade with that interpreter: "
                    ".venv/bin/python -m pip install -U -r requirements.txt"
                )
        return self._client

    def _store_exists(self, c, name: str) -> bool:
        from google.genai import errors

        try:
            c.file_search_stores.get(name=name)
            return True
        except errors.APIError as e:
            if e.code == 404:
                return False
            raise

    def ensure_store(self) -> str:
        """Return fileSearchStores/... resource name, creating or reusing as needed."""
        c = self.client()

        if self._store_name:
            if self._store_exists(c, self._store_name):
                return self._store_name
            logger.warning(
                "Cached File Search store %s is gone (404); re-resolving.",
                self._store_name,
            )
            self.invalidate_store()

        if Config.FILE_SEARCH_STORE_NAME:
            n = Config.FILE_SEARCH_STORE_NAME
            if not self._store_exists(c, n):
                raise RuntimeError(
                    f"FILE_SEARCH_STORE_NAME={n!r} was not found (404). "
                    "Remove it or fix the id."
                )
            self._store_name = n
            return n

        from_disk = self._load_state()
        if from_disk:
            if self._store_exists(c, from_disk):
                self._store_name = from_disk
                logger.info("Using File Search store from state file: %s", from_disk)
                return from_disk
            logger.warning(
                "Saved store %s no longer exists (404); delete stale state and create new.",
                from_disk,
            )
            self.invalidate_store()

        target = Config.FILE_SEARCH_STORE_DISPLAY_NAME
        for store in c.file_search_stores.list():
            if getattr(store, "display_name", None) == target:
                if self._store_exists(c, store.name):
                    self._store_name = store.name
                    logger.info("Reusing existing File Search store: %s", self._store_name)
                    self._save_state(self._store_name)
                    return self._store_name

        created = c.file_search_stores.create(config={"display_name": target})
        self._store_name = created.name
        logger.info("Created File Search store: %s", self._store_name)
        self._save_state(self._store_name)
        return self._store_name

    def _wait_operation(self, operation) -> None:
        c = self.client()
        op = operation
        while op.done is not True:
            time.sleep(2)
            op = c.operations.get(op)
        if op.error:
            raise RuntimeError(f"Operation failed: {op.error}")

    def _wait_file_active(self, c, file_name: str, timeout_s: float = 120) -> None:
        """import_file expects the Files API object to be ready."""
        from google.genai import types as genai_types

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            f = c.files.get(name=file_name)
            st = getattr(f, "state", None)
            if st == genai_types.FileState.ACTIVE:
                return
            if st is not None and str(st).upper().rstrip("]").endswith("ACTIVE"):
                return
            if st == genai_types.FileState.FAILED:
                raise RuntimeError(f"File processing failed for {file_name}")
            time.sleep(1)
        raise TimeoutError(f"File {file_name} did not become ACTIVE within {timeout_s}s")

    def count_documents(self, store_name: str) -> int:
        c = self.client()
        n = 0
        try:
            for _ in c.file_search_stores.documents.list(parent=store_name):
                n += 1
        except Exception as e:
            logger.warning("Could not list documents: %s", e)
        return n

    def upload_file_bytes(self, data: bytes, filename: str) -> dict[str, Any]:
        ext = Path(filename).suffix or ".bin"
        mime, _ = mimetypes.guess_type(filename)
        upload_cfg: dict[str, Any] = {"display_name": filename}
        if mime:
            upload_cfg["mime_type"] = mime

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        from google.genai import errors

        last_err: Optional[BaseException] = None
        try:
            for attempt in range(2):
                store = self.ensure_store()
                try:
                    c = self.client()
                    logger.info(
                        "Uploading directly to File Search store %s …", store
                    )

                    operation = c.file_search_stores.upload_to_file_search_store(
                        file_search_store_name=store,
                        file=tmp_path,
                        config=upload_cfg,
                    )
                    self._wait_operation(operation)

                    doc_count = self.count_documents(store)
                    return {
                        "file_search_store": store,
                        "filename": filename,
                        "documents_in_store": doc_count,
                        "message": (
                            "File uploaded and imported into File Search "
                            "store (managed chunking & embeddings)"
                        ),
                    }
                except errors.APIError as e:
                    last_err = e
                    if e.code == 404 and attempt == 0:
                        # importFile often 404s even when fileSearchStores.get is 200
                        # (broken/partial store). Clearing only .file_search_store.json
                        # is not enough: ensure_store() re-lists by displayName and
                        # picks the same store again — so delete it in the API first.
                        logger.warning(
                            "importFile returned 404 for %s; deleting store (force) "
                            "and local state, then creating a new store once.",
                            store,
                        )
                        try:
                            self.client().file_search_stores.delete(
                                name=store,
                                config={"force": True},
                            )
                        except errors.APIError as de:
                            logger.warning(
                                "Store delete failed (may already be gone): %s", de
                            )
                        self.invalidate_store()
                        continue
                    raise
            if last_err:
                raise last_err
            raise RuntimeError("upload_file_bytes: unexpected exit without result")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def query(self, question: str) -> dict[str, Any]:
        from google.genai import types

        store = self.ensure_store()
        c = self.client()
        response = c.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=question,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store],
                        )
                    )
                ]
            ),
        )

        answer = (response.text or "").strip()
        citations: list[Any] = []
        grounding: Optional[dict[str, Any]] = None

        try:
            cands = getattr(response, "candidates", None) or []
            if cands:
                cand = cands[0]
                cm = getattr(cand, "citation_metadata", None)
                if cm is not None:
                    raw_cites = getattr(cm, "citations", None) or []
                    parsed = _to_jsonable(raw_cites)
                    citations = parsed if isinstance(parsed, list) else []
                gm = getattr(cand, "grounding_metadata", None)
                if gm is not None:
                    grounding = _to_jsonable(gm)
        except Exception as e:
            logger.debug("Citation parse skipped: %s", e)

        return {
            "answer": answer,
            "citations": citations,
            "grounding_metadata": grounding,
            "file_search_store": store,
            "model": Config.GEMINI_MODEL,
        }
