"""
Flask application factory. Keeps app construction isolated so tests can
create fresh app instances with different configs if needed.
"""
import os
from flask import Flask, render_template

from app.routes import api
from app.db import init_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )

    app.register_blueprint(api, url_prefix="/api")

    init_db()

    @app.route("/health", methods=["GET"])
    def health_check():
        return {"status": "ok"}, 200

    # ---------- Frontend view routes ----------
    # These only render templates; all data comes from the existing
    # /api/* endpoints via JavaScript fetch calls in static/js/script.js.
    # No business logic here — consistent with the thin-routes principle.

    @app.route("/", methods=["GET"])
    def index_page():
        return render_template("index.html")

    @app.route("/register", methods=["GET"])
    def register_page():
        return render_template("register.html")

    @app.route("/assistant", methods=["GET"])
    def assistant_page():
        return render_template("assistant.html")

    @app.route("/dashboard", methods=["GET"])
    def dashboard_page():
        return render_template("dashboard.html")

    @app.route("/donor/<int:donor_id>", methods=["GET"])
    def donor_details_page(donor_id):
        return render_template("donor_details.html")

    @app.route("/donations/<int:donor_id>", methods=["GET"])
    def donation_history_page(donor_id):
        return render_template("donation_history.html")

    @app.route("/constraints-demo", methods=["GET"])
    def constraints_demo_page():
        return render_template("constraints_demo.html")

    return app