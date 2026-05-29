import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .extensions import db, migrate
from .models import PersonLevel


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    default_db = Path(app.instance_path) / "mzcp.sqlite3"
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        JWT_SECRET=os.getenv("JWT_SECRET", "dev-jwt-secret-change-me"),
        ROOT_USERNAME=os.getenv("ROOT_USERNAME", "root"),
        ROOT_PASSWORD=os.getenv("ROOT_PASSWORD", "root123"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", f"sqlite:///{default_db}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        AUTO_CREATE_DB=os.getenv("AUTO_CREATE_DB", "true").lower()
        in ("1", "true", "yes"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    register_cli(app)

    if app.config["AUTO_CREATE_DB"]:
        with app.app_context():
            db.create_all()
            seed_defaults()

    return app


def register_cli(app):
    @app.cli.command("seed-data")
    def seed_data_command():
        seed_defaults()
        print("Default person levels are ready.")


def seed_defaults():
    if PersonLevel.query.count() > 0:
        return
    levels = [
        PersonLevel(name="A层级", description="默认预设层级", sort_order=1),
        PersonLevel(name="B层级", description="默认预设层级", sort_order=2),
        PersonLevel(name="C层级", description="默认预设层级", sort_order=3),
    ]
    db.session.add_all(levels)
    db.session.commit()
