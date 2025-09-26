from main import db
from models import Transacao, CompraParcelada, ConfiguracaoUsuario
from datetime import datetime

# (Funções genéricas get/set_user_data)

def get_transacoes_db(user_id):
    # ...
def salvar_transacao_db(user_id, data):
    # ...
def apagar_transacao_db(user_id, timestamp):
    # ...

# --- INÍCIO DA FUNÇÃO QUE FALTAVA ---
def apagar_ultima_transacao_db(user_id):
    """Encontra e apaga a última transação de um usuário que não seja de parcela."""
    ultima_transacao = Transacao.query.filter_by(user_id=user_id).order_by(Transacao.timestamp.desc()).first()
    
    if ultima_transacao:
        descricao = ultima_transacao.descricao
        valor = ultima_transacao.valor
        db.session.delete(ultima_transacao)
        db.session.commit()
        return {"descricao": descricao, "valor": valor}
    
    return None
# --- FIM DA FUNÇÃO QUE FALTAVA ---

# (Resto do arquivo database.py)
# ...
