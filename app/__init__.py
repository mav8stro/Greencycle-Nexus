from flask import Flask, send_file, jsonify, request
import os
from app.config import Config
from app.extensions import db, cors
from app.routes import register_routes
from app.services.seed_service import seed_database
from app.services.auth_service import token_required, admin_required, make_token, hash_password, verify_password
from app.models import User, WasteEntry, Payment, Pickup

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='../static', template_folder='templates')
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": "*"}})

    # Register modular REST API blueprints
    register_routes(app)

    # Register root legacy routes blueprint for backwards compatibility
    try:
        from routes import bp as legacy_bp
        app.register_blueprint(legacy_bp)
    except ImportError:
        pass

    # Serve the upgraded GreenCycle Nexus Web Interface
    @app.route('/')
    @app.route('/app')
    @app.route('/app.html')
    def serve_frontend():
        # Check root app.html first
        root_html = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app.html'))
        if os.path.exists(root_html):
            return send_file(root_html)
        template_html = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates', 'index.html'))
        return send_file(template_html)

    # Health check
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'app': 'GreenCycle Nexus',
            'version': '2.0-kerala-civic'
        })

    # Initialize tables and seed realistic demo data
    with app.app_context():
        db.create_all()
        seed_database()

    return app
