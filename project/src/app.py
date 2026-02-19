from __future__ import annotations

import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from src.storage import (
    create_event,
    delete_event,
    get_attendance_for_user,
    get_event_by_slug,
    get_user_by_email,
    get_user_by_id,
    list_visible_attendees,
    search_events,
    update_event,
    upsert_attendance,
)


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(str(user_id))


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        if current_user() is None:
            flash("Login required")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        user = current_user()
        if not user or user.get("role") != "ADMIN":
            flash("Admin access required")
            return redirect(url_for("events"))
        return view(*args, **kwargs)

    return wrapped


def format_iso(value: str | None) -> str:
    if not value:
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%b %d, %Y %H:%M UTC")


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

    @app.context_processor
    def inject_user() -> dict[str, Any]:
        return {"viewer": current_user(), "format_iso": format_iso}

    @app.get("/")
    def home() -> str:
        events = search_events()
        return render_template("home.html", events=events[:8])

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html", next_path=request.args.get("next", ""))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        expected_password = os.getenv("AUTH_CREDENTIALS_SEED_PASSWORD", "devpassword")

        user = get_user_by_email(email)
        if not user or password != expected_password:
            flash("Invalid credentials")
            return render_template("login.html", next_path=request.form.get("next", "")), 401

        session["user_id"] = user["id"]
        flash(f"Signed in as {user['email']}")
        next_path = request.form.get("next", "")
        return redirect(next_path or url_for("events"))

    @app.post("/logout")
    def logout():
        session.clear()
        flash("Signed out")
        return redirect(url_for("home"))

    @app.get("/events")
    def events() -> str:
        query = request.args.get("query")
        city = request.args.get("city")
        events_list = search_events(query=query, city=city)
        return render_template("events.html", events=events_list, query=query or "", city=city or "")

    @app.get("/events/<slug>")
    def event_details(slug: str):
        event = get_event_by_slug(slug)
        if event is None:
            return render_template("not_found.html"), 404

        viewer = current_user()
        existing_attendance = None
        if viewer:
            existing_attendance = get_attendance_for_user(slug, str(viewer["id"]))

        attendees = list_visible_attendees(
            slug,
            viewer,
            company=request.args.get("company"),
            title=request.args.get("title"),
            state=request.args.get("state"),
        )
        return render_template(
            "event_detail.html",
            event=event,
            attendees=attendees,
            existing_attendance=existing_attendance,
        )

    @app.post("/events/<slug>/attendance")
    @login_required
    def set_attendance(slug: str):
        user = current_user()
        if user is None:
            return redirect(url_for("login"))

        state = request.form.get("state", "INTERESTED")
        visibility = request.form.get("visibility", "PUBLIC")
        try:
            upsert_attendance(slug, str(user["id"]), state=state, visibility=visibility)
            flash("Attendance saved")
        except ValueError as exc:
            flash(str(exc))

        return redirect(url_for("event_details", slug=slug))

    @app.get("/admin/events")
    @admin_required
    def admin_events() -> str:
        return render_template("admin_events.html", events=search_events())

    @app.route("/admin/events/new", methods=["GET", "POST"])
    @admin_required
    def admin_events_new():
        if request.method == "GET":
            return render_template("admin_event_form.html", mode="create", event=None)

        payload = {
            "slug": request.form.get("slug", ""),
            "name": request.form.get("name", ""),
            "description": request.form.get("description", ""),
            "website_url": request.form.get("website_url", ""),
            "start_at": request.form.get("start_at", ""),
            "end_at": request.form.get("end_at", ""),
            "city": request.form.get("city", ""),
            "country": request.form.get("country", ""),
            "tags": request.form.get("tags", ""),
        }

        try:
            create_event(payload)
            flash("Event created")
            return redirect(url_for("admin_events"))
        except ValueError as exc:
            flash(str(exc))
            return render_template("admin_event_form.html", mode="create", event=payload), 400

    @app.route("/admin/events/<slug>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_events_edit(slug: str):
        event = get_event_by_slug(slug)
        if not event:
            return render_template("not_found.html"), 404

        if request.method == "GET":
            event_view = dict(event)
            event_view["tags"] = ", ".join(event.get("tags", []))
            return render_template("admin_event_form.html", mode="edit", event=event_view)

        payload = {
            "slug": request.form.get("slug", slug),
            "name": request.form.get("name", ""),
            "description": request.form.get("description", ""),
            "website_url": request.form.get("website_url", ""),
            "start_at": request.form.get("start_at", ""),
            "end_at": request.form.get("end_at", ""),
            "city": request.form.get("city", ""),
            "country": request.form.get("country", ""),
            "tags": request.form.get("tags", ""),
        }

        try:
            updated = update_event(slug, payload)
            flash("Event updated")
            return redirect(url_for("admin_events_edit", slug=updated["slug"]))
        except ValueError as exc:
            flash(str(exc))
            return render_template("admin_event_form.html", mode="edit", event=payload), 400

    @app.post("/admin/events/<slug>/delete")
    @admin_required
    def admin_events_delete(slug: str):
        try:
            delete_event(slug)
            flash("Event deleted")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("admin_events"))

    @app.get("/me")
    @login_required
    def me():
        user = current_user()
        return render_template("me.html", user=user)

    @app.get("/api/events")
    def api_events():
        query = request.args.get("query")
        city = request.args.get("city")
        return jsonify({"items": search_events(query=query, city=city)})

    @app.get("/api/events/<slug>")
    def api_event(slug: str):
        event = get_event_by_slug(slug)
        if event is None:
            return jsonify({"error": "Event not found"}), 404
        attendees = list_visible_attendees(
            slug,
            current_user(),
            company=request.args.get("company"),
            title=request.args.get("title"),
            state=request.args.get("state"),
        )
        payload = dict(event)
        payload["attendees"] = attendees
        return jsonify(payload)

    @app.get("/api/events/<slug>/attendees")
    def api_event_attendees(slug: str):
        event = get_event_by_slug(slug)
        if event is None:
            return jsonify({"error": "Event not found"}), 404
        return jsonify(
            list_visible_attendees(
                slug,
                current_user(),
                company=request.args.get("company"),
                title=request.args.get("title"),
                state=request.args.get("state"),
            )
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=os.getenv("FLASK_ENV") == "development")
