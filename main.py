#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_dotenv(path: Optional[Path] = None) -> None:
    env_path = path or Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config() -> Dict[str, Any]:
    load_dotenv()
    return {
        "base_url": os.getenv("MISSKEY_API_BASE_URL", "").rstrip("/"),
        "token": os.getenv("MISSKEY_ACCESS_TOKEN", "").strip(),
        "channel_id": os.getenv("MISSKEY_CHANNEL_ID", "").strip(),
        "mode": os.getenv("MISSKEY_MODE", "global").strip().lower(),
        "antenna_id": os.getenv("MISSKEY_ANTENNA_ID", "").strip(),
        "keywords": [item.strip() for item in os.getenv("MISSKEY_KEYWORDS", "").split(",") if item.strip()],
        "keywords_file": os.getenv("MISSKEY_KEYWORDS_FILE", "keywords.txt").strip(),
        "fetch_limit": int(os.getenv("MISSKEY_FETCH_LIMIT", "20")),
        "poll_interval_seconds": int(os.getenv("MISSKEY_POLL_INTERVAL_SECONDS", "60")),
        "state_file": os.getenv("MISSKEY_STATE_FILE", "state.json"),
        "visibility": os.getenv("MISSKEY_VISIBILITY", "public"),
        "media_mode": os.getenv("MISSKEY_MEDIA_MODE", "any").strip().lower(),
        "dry_run": False,
    }


def resolve_keywords(config: Dict[str, Any]) -> List[str]:
    keywords = list(config.get("keywords", []))
    keywords_file = config.get("keywords_file")
    if not keywords_file:
        return keywords

    path = Path(keywords_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value:
                continue
            if value.startswith("# ") or value.startswith("//"):
                continue
            keywords.append(value)
    return keywords


def matches_media_requirement(note: Dict[str, Any], media_mode: str) -> bool:
    if media_mode == "any":
        return True

    files = note.get("files") or []
    has_media = bool(files)
    if media_mode == "required":
        return has_media
    if media_mode == "absent":
        return not has_media
    return True


def save_state(path: Path, seen_ids: List[str]) -> None:
    path.write_text(json.dumps({"seen_ids": seen_ids[-1000:]}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("seen_ids", []))
    except json.JSONDecodeError:
        return []


def request_json(base_url: str, token: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/{endpoint.lstrip('/')}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else []
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{endpoint} failed with HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{endpoint} failed: {exc.reason}") from exc


def fetch_notes(config: Dict[str, Any], since_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if not config["base_url"]:
        raise RuntimeError("MISSKEY_API_BASE_URL is not set")
    if not config["token"]:
        raise RuntimeError("MISSKEY_ACCESS_TOKEN is not set")

    payload: Dict[str, Any] = {"limit": config["fetch_limit"]}
    if since_id:
        payload["sinceId"] = since_id

    if config["mode"] == "antenna":
        if not config["antenna_id"]:
            raise RuntimeError("MISSKEY_ANTENNA_ID is required when MISSKEY_MODE=antenna")
        candidates = [
            ("notes/antenna-timeline", {**payload, "antennaId": config["antenna_id"]}),
            ("antennas/notes", {**payload, "antennaId": config["antenna_id"]}),
        ]
    else:
        candidates = [("notes/global-timeline", payload)]

    last_error: Optional[Exception] = None
    for endpoint, body in candidates:
        try:
            response = request_json(config["base_url"], config["token"], endpoint, body)
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                return response.get("map") or []
            return []
        except RuntimeError as exc:
            last_error = exc
            print(f"[warn] {endpoint} failed: {exc}")
    if last_error:
        raise last_error
    return []


def match_keywords(note: Dict[str, Any], keywords: List[str]) -> bool:
    if not keywords:
        return True

    text_parts: List[str] = []
    for key in ("text", "cw"):
        value = note.get(key)
        if isinstance(value, str) and value:
            text_parts.append(value)

    tags = note.get("tags") or []
    if isinstance(tags, list):
        text_parts.append(" ".join(str(tag) for tag in tags))

    haystack = " ".join(text_parts).lower()
    for keyword in keywords:
        normalized = keyword.lower().strip()
        if not normalized:
            continue
        if normalized.startswith("#"):
            tag = normalized[1:]
            if tag in {str(item).lower() for item in tags if isinstance(item, str)}:
                return True
        elif normalized in haystack:
            return True
    return False


def create_renote(config: Dict[str, Any], note_id: str) -> None:
    payload: Dict[str, Any] = {
        "renoteId": note_id,
        "visibility": config["visibility"],
        "channelId": config["channel_id"] or None,
        "text": None,
        "localOnly": False,
        "noExtractMentions": False,
        "noExtractHashtags": False,
        "noExtractEmojis": False,
    }
    if config["dry_run"]:
        print(f"[dry-run] would renote note {note_id} into channel {config['channel_id']}")
        return
    response = request_json(config["base_url"], config["token"], "notes/create", payload)
    print(f"[ok] renoted note {note_id}: {response}")


def process_once(config: Dict[str, Any]) -> None:
    state_path = Path(config["state_file"])
    seen_ids = load_state(state_path)
    notes = fetch_notes(config)
    keywords = resolve_keywords(config)

    new_notes = []
    for note in notes:
        note_id = note.get("id")
        if not note_id or note_id in seen_ids:
            continue
        if matches_media_requirement(note, config.get("media_mode", "any")) and match_keywords(note, keywords):
            new_notes.append(note)

    if not new_notes:
        print("[info] no matching notes found")
        return

    for note in new_notes:
        note_id = note.get("id")
        if not note_id:
            continue
        create_renote(config, note_id)
        seen_ids.append(note_id)

    save_state(state_path, seen_ids)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatically renote matching notes from Misskey timeline into a channel")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without creating renotes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    config["dry_run"] = args.dry_run or config["dry_run"]

    if not config["base_url"] or not config["token"]:
        print("Set MISSKEY_API_BASE_URL and MISSKEY_ACCESS_TOKEN before running.", file=sys.stderr)
        return 2

    if args.once:
        try:
            process_once(config)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        return 0

    print("[info] starting watch loop")
    while True:
        try:
            process_once(config)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[error] {exc}", file=sys.stderr)
        time.sleep(config["poll_interval_seconds"])


if __name__ == "__main__":
    raise SystemExit(main())
