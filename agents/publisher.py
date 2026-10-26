"""Safe official-API publishing adapters; dry-run/private by default."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


class PublishError(RuntimeError):
    pass


def _metadata(video: Path, metadata: dict[str, Any] | None) -> dict[str, Any]:
    value = dict(metadata or {})
    value.setdefault("title", video.stem.replace("_", " ")[:100])
    value.setdefault("description", "")
    value.setdefault("hashtags", [])
    value.setdefault("ai_generated", True)
    return value


def prepare_publish(video_path: str | Path, platform: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    video = Path(video_path).expanduser().resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video does not exist: {video}")
    if platform not in {"youtube", "instagram", "tiktok"}:
        raise ValueError("platform must be youtube, instagram, or tiktok")
    package = {
        "platform": platform,
        "video": str(video),
        "metadata": _metadata(video, metadata),
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    target = video.with_name(f"{video.stem}.{platform}.publish.json")
    target.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    package["package_path"] = str(target)
    return package


def _auth(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise PublishError(f"{name} is not configured")
    return value


def _youtube(video: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    token = _auth("YOUTUBE_ACCESS_TOKEN")
    privacy = os.getenv("YOUTUBE_PRIVACY", "private")
    if privacy not in {"private", "unlisted", "public"}:
        raise PublishError("YOUTUBE_PRIVACY must be private, unlisted, or public")
    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": (metadata.get("description") or "") + "\n\n" + " ".join(metadata.get("hashtags") or []),
            "categoryId": os.getenv("YOUTUBE_CATEGORY_ID", "27"),
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": bool(metadata.get("ai_generated", True))},
    }
    size = video.stat().st_size
    initiation = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        json=body, timeout=60,
    )
    upload_url = initiation.headers.get("Location")
    if not initiation.ok or not upload_url:
        raise PublishError(
            f"YouTube upload initialization failed: HTTP {initiation.status_code} {initiation.text[:500]}"
        )
    with video.open("rb") as stream:
        response = requests.put(
            upload_url, data=stream,
            headers={"Content-Type": "video/mp4", "Content-Length": str(size)}, timeout=1800,
        )
    if not response.ok:
        raise PublishError(f"YouTube upload failed: HTTP {response.status_code} {response.text[:500]}")
    return {"status": "uploaded", "platform_id": response.json().get("id"), "privacy": privacy}


def _instagram(video: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    token = _auth("INSTAGRAM_ACCESS_TOKEN")
    user_id = _auth("INSTAGRAM_USER_ID")
    public_url = metadata.get("video_url") or os.getenv("PUBLISH_VIDEO_URL")
    if not public_url:
        raise PublishError("Instagram requires metadata.video_url or PUBLISH_VIDEO_URL")
    version = os.getenv("META_GRAPH_VERSION", "v25.0")
    caption = (metadata.get("description") or "") + "\n\n" + " ".join(metadata.get("hashtags") or [])
    response = requests.post(
        f"https://graph.facebook.com/{version}/{user_id}/media",
        data={"media_type": "REELS", "video_url": public_url, "caption": caption, "access_token": token},
        timeout=60,
    )
    value = response.json() if response.content else {}
    if not response.ok or not value.get("id"):
        raise PublishError(f"Instagram container failed: HTTP {response.status_code} {response.text[:500]}")
    container_id = value["id"]
    deadline = time.monotonic() + int(os.getenv("INSTAGRAM_PROCESSING_TIMEOUT", "900"))
    while time.monotonic() < deadline:
        status_response = requests.get(
            f"https://graph.facebook.com/{version}/{container_id}",
            params={"fields": "status_code,status", "access_token": token}, timeout=60,
        )
        status = status_response.json() if status_response.content else {}
        if not status_response.ok:
            raise PublishError(
                f"Instagram status check failed: HTTP {status_response.status_code} "
                f"{status_response.text[:500]}"
            )
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagram processing failed: {status}")
        time.sleep(max(2, int(os.getenv("INSTAGRAM_POLL_SECONDS", "10"))))
    else:
        raise PublishError(f"Instagram processing timed out for container {container_id}")

    publish = requests.post(
        f"https://graph.facebook.com/{version}/{user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token}, timeout=60,
    )
    published = publish.json() if publish.content else {}
    if not publish.ok or not published.get("id"):
        raise PublishError(f"Instagram publish failed: HTTP {publish.status_code} {publish.text[:500]}")
    return {"status": "published", "container_id": container_id, "platform_id": published["id"]}


def _tiktok(video: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    token = _auth("TIKTOK_ACCESS_TOKEN")
    privacy = os.getenv("TIKTOK_PRIVACY", "SELF_ONLY")
    caption = " ".join(filter(None, [metadata.get("description", ""), *(metadata.get("hashtags") or [])]))
    size = video.stat().st_size
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    creator_response = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
        headers=headers, timeout=60,
    )
    creator_value = creator_response.json() if creator_response.content else {}
    if (not creator_response.ok or (creator_value.get("error") or {}).get("code") != "ok"):
        raise PublishError(
            f"TikTok creator check failed: HTTP {creator_response.status_code} {creator_response.text[:500]}"
        )
    privacy_options = (creator_value.get("data") or {}).get("privacy_level_options") or []
    if privacy not in privacy_options:
        raise PublishError(f"TikTok privacy {privacy!r} is not allowed; choose one of {privacy_options}")
    response = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {"title": caption[:2200], "privacy_level": privacy, "disable_comment": False,
                          "disable_duet": False, "disable_stitch": False,
                          "brand_content_toggle": False, "brand_organic_toggle": False,
                          "is_aigc": bool(metadata.get("ai_generated", True))},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": size, "total_chunk_count": 1},
        }, timeout=60,
    )
    value = response.json() if response.content else {}
    data = value.get("data") or {}
    if not response.ok or (value.get("error") or {}).get("code") != "ok" or not data.get("upload_url"):
        raise PublishError(f"TikTok initialization failed: HTTP {response.status_code} {response.text[:500]}")
    with video.open("rb") as stream:
        upload = requests.put(
            data["upload_url"], data=stream,
            headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                     "Content-Range": f"bytes 0-{size - 1}/{size}"}, timeout=1800,
        )
    if not upload.ok:
        raise PublishError(f"TikTok upload failed: HTTP {upload.status_code} {upload.text[:500]}")
    publish_id = data.get("publish_id")
    deadline = time.monotonic() + int(os.getenv("TIKTOK_PROCESSING_TIMEOUT", "900"))
    last_status = "PROCESSING_UPLOAD"
    while time.monotonic() < deadline:
        status_response = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers=headers, json={"publish_id": publish_id}, timeout=60,
        )
        status_value = status_response.json() if status_response.content else {}
        if not status_response.ok or (status_value.get("error") or {}).get("code") != "ok":
            raise PublishError(
                f"TikTok status check failed: HTTP {status_response.status_code} {status_response.text[:500]}"
            )
        status_data = status_value.get("data") or {}
        last_status = status_data.get("status", last_status)
        if last_status == "PUBLISH_COMPLETE":
            return {
                "status": "published", "publish_id": publish_id, "privacy": privacy,
                "post_ids": status_data.get("publicaly_available_post_id", []),
            }
        if last_status == "FAILED":
            raise PublishError(f"TikTok processing failed: {status_data.get('fail_reason', 'unknown reason')}")
        time.sleep(max(2, int(os.getenv("TIKTOK_POLL_SECONDS", "10"))))
    return {"status": "processing", "publish_id": publish_id, "privacy": privacy,
            "platform_status": last_status}


def publish_video(video_path: str | Path, platform: str = "youtube",
                  metadata: dict[str, Any] | None = None, *, live: bool = False) -> dict[str, Any]:
    """Prepare a publish package, optionally sending it when both safety switches are enabled."""
    package = prepare_publish(video_path, platform, metadata)
    if not live or os.getenv("PUBLISH_ENABLED", "0") != "1":
        return package
    video = Path(video_path).expanduser().resolve()
    package.update({"youtube": _youtube, "instagram": _instagram, "tiktok": _tiktok}[platform](
        video, package["metadata"]
    ))
    Path(package["package_path"]).write_text(
        json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return package
