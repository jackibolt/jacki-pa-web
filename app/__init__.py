from flask import Flask, current_app, request, session, g
from flask_login import current_user, LoginManager, UserMixin
from flask_jwt_extended import JWTManager
import os


# You may already have this class or will add it later
class User(UserMixin):
    def __init__(self, id, email=None):
        self.id = id
        self.email = email

    def get_id(self):
        return str(self.id)
    

def create_app():
    # Absolute path to the 'static' folder in the root directory
    static_folder_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'static')

    app = Flask(__name__, template_folder="../templates", static_url_path='/static', static_folder=static_folder_path)

    # Load config early, before anything else:
    env = os.environ.get('FLASK_ENV', 'development').lower()
    if env == 'production':
        app.config.from_object('config.ProductionConfig')
    else:
        app.config.from_object('config.DevelopmentConfig')

    # Now extensions can be initialized and routes registered...

    # Initialize flask_jwt_extended AFTER config is loaded
    from flask_jwt_extended import JWTManager
    jwt = JWTManager(app)

    # Initialize routes
    from .routes import routes
    app.register_blueprint(routes)

    # Debug: print all registered routes
    print("\n📍 REGISTERED ROUTES:")
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/static'):
            print(f"  {rule.methods - {'OPTIONS', 'HEAD'}} {rule.rule}")
    print()

    login_manager = LoginManager()
    login_manager.init_app(app)

    app.jinja_env.add_extension('jinja2.ext.do')

    @app.context_processor
    def inject_environment():
        return dict(env=os.environ.get('FLASK_ENV'))

    @app.context_processor
    def inject_api_base():
        return dict(api_base_url=os.environ.get('API_BASE_URL'))

    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User(id=user_id)
    
    @app.before_request
    def load_logged_in_user():
        g.access_token = session.get("access_token")

    @app.after_request
    def apply_after_request_callbacks(response):
        view = request.endpoint and current_app.view_functions.get(request.endpoint)
        if view and hasattr(view, 'after_request'):
            return view.after_request(response)
        return response

    return app
