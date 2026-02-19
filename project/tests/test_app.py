from __future__ import annotations

import json
from pathlib import Path

import src.storage as storage
from src.app import create_app


def _write_seed(path: Path) -> None:
    payload = {
        "events": [
            {
                "slug": "event-a",
                "name": "Event A",
                "description": "Test event",
                "website_url": "https://example.com",
                "start_at": "2026-04-12T09:00:00Z",
                "end_at": "2026-04-14T17:00:00Z",
                "city": "Las Vegas",
                "country": "US",
                "tags": ["payments"]
            }
        ],
        "users": [
            {
                "id": "admin",
                "email": "admin@local.dev",
                "name": "Admin",
                "role": "ADMIN",
                "verified_email_domain": True,
                "company": "AdminCo",
                "title": "Admin",
                "plan": "PRO",
                "subscription_status": "ACTIVE"
            },
            {
                "id": "free",
                "email": "free@local.dev",
                "name": "Free User",
                "role": "USER",
                "verified_email_domain": False,
                "company": "Indie",
                "title": "Consultant",
                "plan": "FREE",
                "subscription_status": "CANCELED"
            },
            {
                "id": "verified",
                "email": "verified@stripe.com",
                "name": "Verified User",
                "role": "USER",
                "verified_email_domain": True,
                "company": "Stripe",
                "title": "Partnerships",
                "plan": "FREE",
                "subscription_status": "CANCELED"
            }
        ],
        "attendances": [
            {"event_slug": "event-a", "user_id": "free", "state": "INTERESTED", "visibility": "PUBLIC", "updated_at": "2026-02-08T12:00:00Z"},
            {"event_slug": "event-a", "user_id": "verified", "state": "ATTENDING", "visibility": "VERIFIED_ONLY", "updated_at": "2026-02-08T12:01:00Z"}
        ],
        "side_events": [],
        "meeting_requests": []
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _test_client(tmp_path: Path):
    data_file = tmp_path / "events.json"
    _write_seed(data_file)
    storage.DATA_FILE = data_file
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_home_page_loads(tmp_path: Path) -> None:
    client = _test_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert b"B2B Fintech Conference Intelligence" in response.data


def test_api_events_returns_items(tmp_path: Path) -> None:
    client = _test_client(tmp_path)
    response = client.get("/api/events")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    assert isinstance(payload.get("items"), list)
    assert len(payload["items"]) == 1


def test_attendee_privacy_anonymous_hides_verified_only(tmp_path: Path) -> None:
    client = _test_client(tmp_path)
    response = client.get("/api/events/event-a")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None
    attendees = payload["attendees"]["items"]
    assert len(attendees) == 1
    assert attendees[0]["visibility"] == "PUBLIC"


def test_admin_can_create_edit_delete_event(tmp_path: Path) -> None:
    client = _test_client(tmp_path)

    login = client.post(
        "/login",
        data={"email": "admin@local.dev", "password": "devpassword"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    created = client.post(
        "/admin/events/new",
        data={
            "slug": "new-event",
            "name": "New Event",
            "description": "Desc",
            "website_url": "https://new.example.com",
            "start_at": "2026-07-01T09:00:00Z",
            "end_at": "2026-07-01T17:00:00Z",
            "city": "NYC",
            "country": "US",
            "tags": "payments, b2b"
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    assert b"Event created" in created.data

    edited = client.post(
        "/admin/events/new-event/edit",
        data={
            "slug": "new-event",
            "name": "New Event Updated",
            "description": "Desc",
            "website_url": "https://new.example.com",
            "start_at": "2026-07-01T09:00:00Z",
            "end_at": "2026-07-01T17:00:00Z",
            "city": "NYC",
            "country": "US",
            "tags": "payments, b2b"
        },
        follow_redirects=True,
    )
    assert edited.status_code == 200
    assert b"Event updated" in edited.data

    deleted = client.post("/admin/events/new-event/delete", follow_redirects=True)
    assert deleted.status_code == 200
    assert b"Event deleted" in deleted.data
