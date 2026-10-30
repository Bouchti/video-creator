"""Small HTTP client for standard ComfyUI prompt execution."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import requests


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    # How long status polls may keep failing before a running job is given up.
    CONNECTION_GRACE_SECONDS = 120

    def __init__(self, base_url: str, timeout: int = 3600, poll_seconds: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_seconds = poll_seconds
        self.client_id = uuid.uuid4().hex


    def free_memory(self) -> bool:
        """Best-effort release of cached models between expensive local video jobs."""
        try:
            response = requests.post(
                f"{self.base_url}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=30,
            )
            return response.ok
        except requests.RequestException:
            return False

    def has_node(self, class_type: str) -> bool:
        try:
            response = requests.get(f"{self.base_url}/object_info/{class_type}", timeout=5)
            return response.ok and class_type in response.json()
        except (requests.RequestException, ValueError):
            return False

    def upload_image(self, source: str | Path) -> str:
        path = Path(source)
        with path.open("rb") as stream:
            response = requests.post(
                f"{self.base_url}/upload/image",
                files={"image": (path.name, stream, "application/octet-stream")},
                data={"overwrite": "false"},
                timeout=120,
            )
        if not response.ok:
            raise ComfyError(f"ComfyUI image upload failed: HTTP {response.status_code} {response.text[:300]}")
        value = response.json()
        name = value.get("name") or path.name
        subfolder = value.get("subfolder") or ""
        return f"{subfolder}/{name}".strip("/")

    def submit(self, workflow: dict[str, Any]) -> str:
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": self.client_id},
            timeout=30,
        )
        if not response.ok:
            details = response.text[:1000]
            try:
                details = json.dumps(response.json(), ensure_ascii=False)[:2000]
            except ValueError:
                pass
            raise ComfyError(f"ComfyUI rejected workflow: HTTP {response.status_code}: {details}")
        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise ComfyError("ComfyUI did not return a prompt_id")
        return str(prompt_id)

    def wait(
        self,
        prompt_id: str,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        last_contact = time.monotonic()
        while time.monotonic() < deadline:
            try:
                response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
            except requests.RequestException as exc:
                # A busy GPU host can drop a status poll; only a sustained outage ends the job.
                if time.monotonic() - last_contact > self.CONNECTION_GRACE_SECONDS:
                    raise ComfyError(
                        f"ComfyUI connection lost for over {self.CONNECTION_GRACE_SECONDS}s: {exc}"
                    ) from exc
                time.sleep(self.poll_seconds)
                continue
            last_contact = time.monotonic()
            if not response.ok:
                raise ComfyError(f"ComfyUI history failed: HTTP {response.status_code}")
            value = response.json().get(prompt_id)
            if value:
                status = value.get("status") or {}
                if status.get("status_str") == "error" or status.get("completed") is False:
                    messages = status.get("messages") or []
                    exception = None
                    for message in messages:
                        if (isinstance(message, list) and len(message) > 1
                                and isinstance(message[1], dict) and message[1].get("exception_message")):
                            exception = str(message[1]["exception_message"])
                            break
                    details = exception or json.dumps(messages, ensure_ascii=False)
                    raise ComfyError(f"ComfyUI generation failed: {details[:4000]}")
                if value.get("outputs") is not None and status.get("completed", True):
                    return value
            if on_progress:
                try:
                    queue = requests.get(f"{self.base_url}/queue", timeout=10).json()
                except (requests.RequestException, ValueError):
                    queue = {}
                on_progress(queue)
            time.sleep(self.poll_seconds)
        self.cancel(prompt_id)
        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {self.timeout} seconds and was cancelled")

    def cancel(self, prompt_id: str, wait_seconds: float = 30.0) -> bool:
        """Remove our queued prompt or interrupt it if it is the active ComfyUI job."""
        try:
            queue = requests.get(f"{self.base_url}/queue", timeout=10).json()
            running = queue.get("queue_running") or []
            pending = queue.get("queue_pending") or []
            is_running = any(len(item) > 1 and str(item[1]) == prompt_id for item in running)
            is_pending = any(len(item) > 1 and str(item[1]) == prompt_id for item in pending)
            if is_pending:
                response = requests.post(
                    f"{self.base_url}/queue", json={"delete": [prompt_id]}, timeout=10,
                )
                response.raise_for_status()
            if is_running:
                response = requests.post(f"{self.base_url}/interrupt", json={}, timeout=10)
                response.raise_for_status()
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                queue = requests.get(f"{self.base_url}/queue", timeout=10).json()
                ids = {
                    str(item[1]) for key in ("queue_running", "queue_pending")
                    for item in (queue.get(key) or []) if len(item) > 1
                }
                if prompt_id not in ids:
                    self.free_memory()
                    return True
                time.sleep(min(self.poll_seconds, 1.0))
            return False
        except (requests.RequestException, ValueError, TypeError):
            return False

    @staticmethod
    def output_item(history: dict[str, Any]) -> dict[str, Any]:
        extensions = (".mp4", ".webm", ".mkv", ".mov")
        for node in (history.get("outputs") or {}).values():
            for key in ("videos", "gifs", "images", "files"):
                for item in node.get(key, []) if isinstance(node, dict) else []:
                    if str(item.get("filename", "")).lower().endswith(extensions):
                        return item
        raise ComfyError("ComfyUI completed but returned no video file")

    def download(self, item: dict[str, Any], target: str | Path) -> Path:
        response = requests.get(
            f"{self.base_url}/view",
            params={
                "filename": item.get("filename"),
                "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output"),
            },
            timeout=300,
            stream=True,
        )
        if not response.ok:
            raise ComfyError(f"ComfyUI output download failed: HTTP {response.status_code}")
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        with temporary.open("wb") as stream:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    stream.write(chunk)
        temporary.replace(path)
        return path

    def generate(
        self,
        workflow: dict[str, Any],
        target: str | Path,
        on_submitted: Callable[[str], None] | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[Path, str, dict[str, Any]]:
        prompt_id = self.submit(workflow)
        if on_submitted:
            on_submitted(prompt_id)
        history = self.wait(prompt_id, on_progress=on_progress)
        item = self.output_item(history)
        return self.download(item, target), prompt_id, history
