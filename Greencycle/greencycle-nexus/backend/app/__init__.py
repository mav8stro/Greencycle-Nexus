from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///greencycle.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'greencycle-nexus-secret-2024'

    CORS(app)
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        _seed_demo_data()

    return app


def _seed_demo_data():
    from .models import User
    if User.query.first():
        return

    import hashlib
    def hash_pin(pin):
        return hashlib.sha256(pin.encode()).hexdigest()

    users = [
        User(phone='9000000001', pin=hash_pin('1111'), role='admin'),
        User(phone='9000000002', pin=hash_pin('2222'), role='citizen'),
        User(phone='9000000003', pin=hash_pin('3333'), role='worker'),
    ]
    from app import db
    db.session.add_all(users)
    db.session.commit()
