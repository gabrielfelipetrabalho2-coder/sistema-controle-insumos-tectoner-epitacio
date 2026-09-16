from flask import Flask
import firebase_admin
from firebase_admin import credentials, db

# Importando os módulos separados (Blueprints)
from routes.envios import envios_bp
from routes.produtos import produtos_bp
from routes.impressoras import impressoras_bp

app = Flask(__name__)
app.secret_key = 'chave_secreta_super_segura'

# Inicializa o Firebase apenas uma vez
cred = credentials.Certificate("firebase-key.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        cred, {'databaseURL': 'https://scitectoner-default-rtdb.firebaseio.com/'})

# --- NOVA MÁGICA: Injeta os módulos no Menu Lateral ---
@app.context_processor
def inject_modulos():
    try:
        estruturas = db.reference('estruturas_dinamicas').get() or {}
        lista = [{'id': k, 'nome': v.get('nome')} for k, v in estruturas.items()]
        return dict(modulos_dinamicos=sorted(lista, key=lambda x: x['nome']))
    except Exception:
        return dict(modulos_dinamicos=[])
# ------------------------------------------------------

# Registra os módulos no aplicativo principal
app.register_blueprint(envios_bp)
app.register_blueprint(produtos_bp)
app.register_blueprint(impressoras_bp)

if __name__ == '__main__':
    app.run(debug=True)