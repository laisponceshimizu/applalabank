# models.py

from main import db # Importa a instância 'db' do seu app principal
from datetime import datetime

class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50))
    descricao = db.Column(db.String(300))
    valor = db.Column(db.Float)
    categoria = db.Column(db.String(100))
    metodo = db.Column(db.String(50))
    cartao = db.Column(db.String(100), nullable=True)
    conta = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.String(100), default=lambda: datetime.now().isoformat())

class CompraParcelada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(300))
    valor_total = db.Column(db.Float)
    num_parcelas = db.Column(db.Integer)
    cartao = db.Column(db.String(100))
    categoria = db.Column(db.String(100))
    data_inicio = db.Column(db.String(100), default=lambda: datetime.now().isoformat())
