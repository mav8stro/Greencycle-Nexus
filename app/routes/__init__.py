from app.routes.auth import auth_bp
from app.routes.citizen import citizen_bp
from app.routes.worker import worker_bp
from app.routes.volunteer import volunteer_bp
from app.routes.admin import admin_bp
from app.routes.waste import waste_bp
from app.routes.collection import collection_bp
from app.routes.payments import payments_bp
from app.routes.events import events_bp
from app.routes.reports import reports_bp

def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(citizen_bp)
    app.register_blueprint(worker_bp)
    app.register_blueprint(volunteer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(waste_bp)
    app.register_blueprint(collection_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(reports_bp)
