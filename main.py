#!/usr/bin/env python3
import argparse
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_USER_AGENT = "MiChannelAutoRenoter/1.0"
LOGGER = logging.getLogger("michannel-autorenoter")


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
        os.environ[key] = value


def load_config() -> Dict[str, Any]:
    load_dotenv()
    token = os.getenv("MISSKEY_ACCESS_TOKEN", "").strip()
    return {
        "base_url": os.getenv("MISSKEY_API_BASE_URL", "").rstrip("/"),
        "token": token,
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
        "skip_renotes": os.getenv("MISSKEY_SKIP_RENOTES", "true").strip().lower() in {"1", "true", "yes", "on"},
        "ignore_self": os.getenv("MISSKEY_IGNORE_SELF", "true").strip().lower() in {"1", "true", "yes", "on"},
        "self_user_id": os.getenv("MISSKEY_SELF_USER_ID", "").strip(),
        "log_level": os.getenv("MISSKEY_LOG_LEVEL", "INFO").strip().upper(),
        "dry_run": False,
    }


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
        level_name = "INFO"
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    LOGGER.debug("log level set to %s", level_name)


def validate_config(config: Dict[str, Any]) -> None:
    required = {
        "MISSKEY_API_BASE_URL": config.get("base_url"),
        "MISSKEY_ACCESS_TOKEN": config.get("token"),
        "MISSKEY_CHANNEL_ID": config.get("channel_id"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Required configuration is missing: {', '.join(missing)}")


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


def should_process_note(note: Dict[str, Any], config: Dict[str, Any], seen_ids: List[str]) -> bool:
    note_id = note.get("id")
    if not note_id or note_id in seen_ids:
        return False

    if config.get("skip_renotes", True):
        if note.get("renoteId") or note.get("renote"):
            return False

    if config.get("ignore_self", True):
        self_user_id = config.get("self_user_id")
        note_user = note.get("user") or {}
        if self_user_id and isinstance(note_user, dict) and note_user.get("id") == self_user_id:
            return False

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
        "User-Agent": DEFAULT_USER_AGENT,
        "Content-Type": "application/json",
    }
    body = None
    if payload is not None:
        request_payload = dict(payload)
        request_payload.setdefault("i", token)
        body = json.dumps(request_payload).encode("utf-8")

    url = f"{base_url}/api/{endpoint.lstrip('/')}"
    LOGGER.debug("calling %s with payload=%s", url, payload)
    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        LOGGER.debug("response from %s: %s", url, detail)
        raise RuntimeError(f"{endpoint} failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        LOGGER.debug("network error for %s: %s", url, exc.reason)
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
            ("antennas/notes", {**payload, "antennaId": config["antenna_id"]}),
            ("notes/antenna-timeline", {**payload, "antennaId": config["antenna_id"]}),
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
            LOGGER.warning("%s failed: %s", endpoint, exc)
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
    if not config.get("channel_id"):
        raise RuntimeError("MISSKEY_CHANNEL_ID is required before creating a renote")

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
        LOGGER.info("[dry-run] would renote note %s into channel %s", note_id, config["channel_id"])
        return
    response = request_json(config["base_url"], config["token"], "notes/create", payload)
    LOGGER.info("renoted note %s", note_id)
    LOGGER.debug("notes/create response for %s: %s", note_id, response)


def process_once(config: Dict[str, Any]) -> None:
    state_path = Path(config["state_file"])
    seen_ids = load_state(state_path)
    notes = fetch_notes(config)
    keywords = resolve_keywords(config)

    new_notes = []
    skipped_by_state = 0
    filtered_out = 0
    for note in notes:
        note_id = note.get("id")
        if note_id and note_id in seen_ids:
            skipped_by_state += 1
            continue
        if not should_process_note(note, config, seen_ids):
            filtered_out += 1
            continue
        if not matches_media_requirement(note, config.get("media_mode", "any")):
            filtered_out += 1
            continue
        if not match_keywords(note, keywords):
            filtered_out += 1
            continue
        new_notes.append(note)

    LOGGER.debug("fetched %s notes from API", len(notes))
    LOGGER.debug("%s notes matched the filter criteria", len(new_notes))
    LOGGER.debug("%s notes were excluded by state", skipped_by_state)
    LOGGER.debug("%s notes were filtered out by rules", filtered_out)

    if not new_notes:
        LOGGER.debug("no matching notes found")
        return

    for note in new_notes:
        note_id = note.get("id")
        if not note_id:
            continue
        create_renote(config, note_id)
        if not config.get("dry_run", False):
            seen_ids.append(note_id)

    if not config.get("dry_run", False):
        save_state(state_path, seen_ids)
    else:
        LOGGER.debug("dry-run enabled; state was not persisted")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automatically renote matching notes from Misskey timeline into a channel")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without creating renotes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    config["dry_run"] = args.dry_run or config["dry_run"]
    configure_logging(config["log_level"])

    try:
        validate_config(config)
    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 2

    if args.once:
        try:
            process_once(config)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("%s", exc)
            return 1
        return 0

    LOGGER.info("starting watch loop")
    while True:
        try:
            process_once(config)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("%s", exc)
        time.sleep(config["poll_interval_seconds"])


if __name__ == "__main__":
    raise SystemExit(main())
