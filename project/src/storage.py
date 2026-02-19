from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "events.json"
FREE_ATTENDEE_LIMIT = 25
PRO_ATTENDEE_LIMIT = 500


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_data() -> dict[str, Any]:
    return {
        "events": [],
        "users": [],
        "attendances": [],
        "side_events": [],
        "meeting_requests": []
    }


def read_data() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return _default_data()
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return _default_data()

    data = _default_data()
    for key in data:
        value = payload.get(key, data[key])
        data[key] = value if isinstance(value, list) else data[key]
    return data


def write_data(data: dict[str, Any]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def read_events() -> list[dict[str, Any]]:
    return read_data()["events"]


def search_events(query: str | None = None, city: str | None = None) -> list[dict[str, Any]]:
    events = read_events()
    q = (query or "").strip().lower()
    c = (city or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    for event in events:
        name = str(event.get("name", "")).lower()
        description = str(event.get("description", "")).lower()
        event_city = str(event.get("city", "")).lower()
        if q and q not in name and q not in description:
            continue
        if c and c not in event_city:
            continue
        filtered.append(event)

    filtered.sort(key=lambda e: (str(e.get("start_at", "")), str(e.get("slug", ""))))
    return filtered


def get_event_by_slug(slug: str) -> dict[str, Any] | None:
    for event in read_events():
        if str(event.get("slug")) == slug:
            return event
    return None


def _slugify(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")


def create_event(payload: dict[str, Any]) -> dict[str, Any]:
    data = read_data()
    slug = _slugify(str(payload.get("slug") or payload.get("name") or ""))
    if not slug:
        raise ValueError("Slug or name is required")
    if any(str(event.get("slug")) == slug for event in data["events"]):
        raise ValueError("Event slug already exists")

    event = {
        "slug": slug,
        "name": str(payload.get("name", "")).strip(),
        "description": str(payload.get("description", "")).strip(),
        "website_url": str(payload.get("website_url", "")).strip(),
        "start_at": str(payload.get("start_at", "")).strip(),
        "end_at": str(payload.get("end_at", "")).strip(),
        "city": str(payload.get("city", "")).strip(),
        "country": str(payload.get("country", "")).strip(),
        "tags": [token.strip() for token in str(payload.get("tags", "")).split(",") if token.strip()]
    }

    if not event["name"]:
        raise ValueError("Event name is required")

    data["events"].append(event)
    write_data(data)
    return event


def update_event(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = read_data()
    events = data["events"]
    found: dict[str, Any] | None = None
    for event in events:
        if str(event.get("slug")) == slug:
            found = event
            break

    if found is None:
        raise ValueError("Event not found")

    new_slug = _slugify(str(payload.get("slug") or slug))
    if new_slug != slug and any(str(event.get("slug")) == new_slug for event in events):
        raise ValueError("Event slug already exists")

    found.update(
        {
            "slug": new_slug,
            "name": str(payload.get("name", found.get("name", ""))).strip(),
            "description": str(payload.get("description", found.get("description", ""))).strip(),
            "website_url": str(payload.get("website_url", found.get("website_url", ""))).strip(),
            "start_at": str(payload.get("start_at", found.get("start_at", ""))).strip(),
            "end_at": str(payload.get("end_at", found.get("end_at", ""))).strip(),
            "city": str(payload.get("city", found.get("city", ""))).strip(),
            "country": str(payload.get("country", found.get("country", ""))).strip(),
            "tags": [token.strip() for token in str(payload.get("tags", ",".join(found.get("tags", [])))).split(",") if token.strip()]
        }
    )

    if new_slug != slug:
        for attendance in data["attendances"]:
            if attendance.get("event_slug") == slug:
                attendance["event_slug"] = new_slug

    write_data(data)
    return found


def delete_event(slug: str) -> None:
    data = read_data()
    before = len(data["events"])
    data["events"] = [event for event in data["events"] if str(event.get("slug")) != slug]
    if len(data["events"]) == before:
        raise ValueError("Event not found")

    data["attendances"] = [a for a in data["attendances"] if a.get("event_slug") != slug]
    data["side_events"] = [s for s in data["side_events"] if s.get("event_slug") != slug]
    data["meeting_requests"] = [m for m in data["meeting_requests"] if m.get("event_slug") != slug]
    write_data(data)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    lookup = email.strip().lower()
    for user in read_data()["users"]:
        if str(user.get("email", "")).lower() == lookup:
            return user
    return None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    for user in read_data()["users"]:
        if str(user.get("id")) == user_id:
            return user
    return None


def can_view_verified_only(viewer: dict[str, Any] | None) -> bool:
    if not viewer:
        return False
    if viewer.get("role") == "ADMIN":
        return True
    if viewer.get("verified_email_domain"):
        return True
    return viewer.get("plan") == "PRO" and viewer.get("subscription_status") == "ACTIVE"


def attendee_limit(viewer: dict[str, Any] | None) -> int:
    if viewer and (viewer.get("role") == "ADMIN" or (viewer.get("plan") == "PRO" and viewer.get("subscription_status") == "ACTIVE")):
        return PRO_ATTENDEE_LIMIT
    return FREE_ATTENDEE_LIMIT


def get_attendance_for_user(event_slug: str, user_id: str) -> dict[str, Any] | None:
    for row in read_data()["attendances"]:
        if row.get("event_slug") == event_slug and row.get("user_id") == user_id:
            return row
    return None


def upsert_attendance(event_slug: str, user_id: str, state: str, visibility: str) -> dict[str, Any]:
    if state not in {"INTERESTED", "ATTENDING"}:
        raise ValueError("Invalid attendance state")
    if visibility not in {"PUBLIC", "VERIFIED_ONLY", "PRIVATE"}:
        raise ValueError("Invalid attendance visibility")

    data = read_data()
    if not any(str(event.get("slug")) == event_slug for event in data["events"]):
        raise ValueError("Event not found")

    existing: dict[str, Any] | None = None
    for row in data["attendances"]:
        if row.get("event_slug") == event_slug and row.get("user_id") == user_id:
            existing = row
            break

    now = now_iso()
    if existing:
        existing.update({"state": state, "visibility": visibility, "updated_at": now})
        write_data(data)
        return existing

    created = {
        "event_slug": event_slug,
        "user_id": user_id,
        "state": state,
        "visibility": visibility,
        "updated_at": now
    }
    data["attendances"].append(created)
    write_data(data)
    return created


def list_visible_attendees(
    event_slug: str,
    viewer: dict[str, Any] | None,
    company: str | None = None,
    title: str | None = None,
    state: str | None = None
) -> dict[str, Any]:
    data = read_data()
    users = {str(user.get("id")): user for user in data["users"]}

    rows = [a for a in data["attendances"] if a.get("event_slug") == event_slug]
    rows.sort(key=lambda a: (str(a.get("updated_at", "")), str(a.get("user_id", ""))), reverse=True)

    c = (company or "").strip().lower()
    t = (title or "").strip().lower()

    visible: list[dict[str, Any]] = []
    for row in rows:
        if state and row.get("state") != state:
            continue

        user = users.get(str(row.get("user_id")))
        if not user:
            continue

        visibility = row.get("visibility")
        can_see = False
        if viewer and viewer.get("role") == "ADMIN":
            can_see = True
        elif visibility == "PUBLIC":
            can_see = True
        elif visibility == "VERIFIED_ONLY":
            can_see = can_view_verified_only(viewer)
        elif visibility == "PRIVATE":
            can_see = bool(viewer and viewer.get("id") == row.get("user_id"))

        if not can_see:
            continue

        if c and c not in str(user.get("company", "")).lower():
            continue
        if t and t not in str(user.get("title", "")).lower():
            continue

        visible.append(
            {
                "user_id": user.get("id"),
                "name": user.get("name"),
                "email": user.get("email"),
                "company": user.get("company", ""),
                "title": user.get("title", ""),
                "state": row.get("state"),
                "visibility": visibility,
                "updated_at": row.get("updated_at")
            }
        )

    limit = attendee_limit(viewer)
    limited = visible[:limit]
    return {
        "items": limited,
        "total_visible": len(visible),
        "limit": limit
    }
