from flask import Flask
from .routes import load_admin
from flask_session import Session
from pathlib import Path


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Configurações básicas
    app.config["SECRET_KEY"] = "dev-secret-change-in-prod"
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = str(Path(".flask_session").absolute())
    app.config["SESSION_PERMANENT"] = False

    # Inicializa sessão no servidor (evita expor dados do carrinho no cookie)
    Session(app)

    # Importa e registra rotas
    from .routes import catalog_bp

    # Injeta admin_email nos templates
    @app.context_processor
    def inject_globals():
        admin = load_admin()
        return {"admin_email": admin.get("email")}

    app.register_blueprint(catalog_bp)

    return app


