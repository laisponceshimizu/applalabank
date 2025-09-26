# database.py (Versão Corrigida)

from main import db
from models import Transacao, CompraParcelada, ConfiguracaoUsuario
from datetime import datetime

# --- Funções Genéricas ---
def get_user_data(user_id, key, default_value):
    config = ConfiguracaoUsuario.query.filter_by(user_id=user_id, chave=key).first()
    if config:
        return config.get_valor()
    set_user_data(user_id, key, default_value)
    return default_value

def set_user_data(user_id, key, value):
    config = ConfiguracaoUsuario.query.filter_by(user_id=user_id, chave=key).first()
    if not config:
        config = ConfiguracaoUsuario(user_id=user_id, chave=key)
        db.session.add(config)
    config.set_valor(value)
    db.session.commit()

# --- Transações ---
def get_transacoes_db(user_id):
    transacoes_obj = Transacao.query.filter_by(user_id=user_id).all()
    return [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in transacoes_obj]

def salvar_transacao_db(user_id, data):
    nova_transacao = Transacao(
        user_id=user_id, tipo=data.get('tipo'), descricao=data.get('descricao'),
        valor=data.get('valor'), categoria=data.get('categoria'), metodo=data.get('metodo'),
        cartao=data.get('cartao'), conta=data.get('conta'),
        timestamp=data.get('timestamp', datetime.now().isoformat())
    )
    db.session.add(nova_transacao)
    db.session.commit()

def apagar_transacao_db(user_id, timestamp):
    transacao = Transacao.query.filter_by(user_id=user_id, timestamp=timestamp).first()
    if transacao:
        db.session.delete(transacao)
        db.session.commit()

# --- INÍCIO DA NOVA FUNÇÃO ---
def apagar_ultima_transacao_db(user_id):
    """Encontra e apaga a última transação de um usuário que não seja de parcela."""
    ultima_transacao = Transacao.query.filter(
        Transacao.user_id == user_id,
        Transacao.metodo != None  # As parcelas virtuais não têm método
    ).order_by(Transacao.timestamp.desc()).first()
    
    if ultima_transacao:
        descricao = ultima_transacao.descricao
        valor = ultima_transacao.valor
        db.session.delete(ultima_transacao)
        db.session.commit()
        return {"descricao": descricao, "valor": valor}
    
    return None
# --- FIM DA NOVA FUNÇÃO ---

# --- Compras Parceladas ---
def get_compras_parceladas_db(user_id):
    # ... (código sem alterações)
# ... (resto do arquivo database.py sem alterações)
