# models.py

from main import db
from datetime import datetime
import json

# Modelo para Transações normais
class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    tipo = db.Column(db.String(50))
    descricao = db.Column(db.String(300))
    valor = db.Column(db.Float)
    categoria = db.Column(db.String(100))
    metodo = db.Column(db.String(50))
    cartao = db.Column(db.String(100), nullable=True)
    conta = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.String(100), default=lambda: datetime.now().isoformat())

# Modelo para Compras Parceladas
class CompraParcelada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    descricao = db.Column(db.String(300))
    valor_total = db.Column(db.Float)
    num_parcelas = db.Column(db.Integer)
    cartao = db.Column(db.String(100))
    categoria = db.Column(db.String(100))
    data_inicio = db.Column(db.String(100), default=lambda: datetime.now().isoformat())

# Modelo Genérico para guardar configurações, senhas, metas, etc.
class ConfiguracaoUsuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)
    chave = db.Column(db.String(100), nullable=False)
    valor_json = db.Column(db.Text, nullable=False)

    def set_valor(self, valor):
        self.valor_json = json.dumps(valor)

    def get_valor(self):
        return json.loads(self.valor_json)
