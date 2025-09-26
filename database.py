# database.py (Versão para Render/SQLAlchemy)

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

# --- INÍCIO DA FUNÇÃO QUE FALTAVA ---
def apagar_ultima_transacao_db(user_id):
    """Encontra e apaga a última transação de um usuário que não seja de parcela."""
    # Busca a transação mais recente do usuário que foi registrada manualmente (não é parcela gerada)
    ultima_transacao = Transacao.query.filter(
        Transacao.user_id == user_id,
        Transacao.metodo != None
    ).order_by(Transacao.timestamp.desc()).first()
    
    if ultima_transacao:
        descricao = ultima_transacao.descricao
        valor = ultima_transacao.valor
        db.session.delete(ultima_transacao)
        db.session.commit()
        return {"descricao": descricao, "valor": valor}
    
    return None # Retorna None se não houver transações para apagar
# --- FIM DA FUNÇÃO QUE FALTAVA ---


# --- Compras Parceladas ---
def get_compras_parceladas_db(user_id):
    compras_obj = CompraParcelada.query.filter_by(user_id=user_id).all()
    return [{c.name: getattr(p, c.name) for c in p.__table__.columns} for p in compras_obj]

def salvar_compra_parcelada_db(user_id, data):
    nova_compra = CompraParcelada(
        user_id=user_id,
        descricao=data.get('descricao'), valor_total=data.get('valor_total'),
        num_parcelas=data.get('num_parcelas'), cartao=data.get('cartao'),
        categoria=data.get('categoria'),
        data_inicio=data.get('data_inicio', datetime.now().isoformat())
    )
    db.session.add(nova_compra)
    db.session.commit()

# --- Configurações (o resto do arquivo) ---
def get_categorias(user_id):
    default = {
        'Pagamentos': ['cartão de crédito', 'fatura', 'pagamento fatura'],
        'Compras': ['mercado pago', 'mercado livre', 'compras a vista', 'compras parceladas', 'computec'],
        'Assinaturas': ['assinatura', 'apple', 'netflix'], 'Investimentos': ['poupança', 'investi'],
        'Cuidados Pessoais': ['barbearia'], 'Educação': ['educação', 'curso', 'livro', 'puc'],
        'Saúde': ['farmacia', 'médico', 'remédio'],
        'Alimentação': ['ifood', 'marmitex', 'mercado', 'restaurante', 'dualcoffe', 'café', 'pizza', 'lanche'],
        'Transporte': ['carro', 'combustivel', 'combustível', 'uber', '99', 'gasolina', 'transporte'],
        'Salário': ['salário'], 'Outras Receitas': ['recebi', 'ganhei'], 'Outros': []
    }
    return get_user_data(user_id, "categorias", default)

def adicionar_categoria_db(user_id, nome, palavras_str):
    categorias = get_categorias(user_id)
    palavras = [p.strip().lower() for p in palavras_str.split(',')]
    categorias[nome.capitalize()] = palavras
    set_user_data(user_id, "categorias", categorias)

def apagar_categoria_db(user_id, nome):
    categorias = get_categorias(user_id)
    if nome in categorias:
        del categorias[nome]
        set_user_data(user_id, "categorias", categorias)

def get_contas_conhecidas(user_id):
    default = {'contas': ['Swile', 'Itaú', 'Nubank', 'Inter'], 'cartoes': ['Mercado Pago', 'Nubank', 'Itaú']}
    return get_user_data(user_id, "contas", default)

def get_cartoes_conhecidos(user_id):
    return get_contas_conhecidas(user_id).get('cartoes', [])

def adicionar_conta_db(user_id, nome):
    contas = get_contas_conhecidas(user_id)
    nome_cap = nome.capitalize()
    if nome_cap not in contas['contas']: contas['contas'].append(nome_cap)
    if nome_cap not in contas['cartoes']: contas['cartoes'].append(nome_cap)
    set_user_data(user_id, "contas", contas)

def apagar_conta_db(user_id, nome):
    contas = get_contas_conhecidas(user_id)
    if nome in contas.get('contas', []): contas['contas'].remove(nome)
    if nome in contas.get('cartoes', []): contas['cartoes'].remove(nome)
    set_user_data(user_id, "contas", contas)

def definir_contas_iniciais_db(user_id, nomes_contas):
    nomes_unicos = sorted(list(set(nomes_contas)))
    contas_obj = {'contas': nomes_unicos, 'cartoes': nomes_unicos}
    set_user_data(user_id, "contas", contas_obj)

def get_regras_cartoes_db(user_id):
    default = {
        'Mercado Pago': {'fechamento': 28, 'vencimento': 7},
        'Nubank': {'fechamento': 25, 'vencimento': 4},
        'Itaú': {'fechamento': 20, 'vencimento': 1}
    }
    return get_user_data(user_id, "regras_cartoes_v2", default)

def salvar_regras_cartao_db(user_id, regras):
    regras_atuais = get_regras_cartoes_db(user_id)
    for cartao, datas in regras.items():
        if str(datas.get('fechamento')).isdigit() and str(datas.get('vencimento')).isdigit():
            regras_atuais[cartao] = {
                'fechamento': int(datas['fechamento']),
                'vencimento': int(datas['vencimento'])
            }
    set_user_data(user_id, "regras_cartoes_v2", regras_atuais)

def get_metas_db(user_id):
    return get_user_data(user_id, "metas", {})

def salvar_meta_db(user_id, categoria, valor):
    metas = get_metas_db(user_id)
    metas[categoria] = valor
    set_user_data(user_id, "metas", metas)

def apagar_meta_db(user_id, categoria):
    metas = get_metas_db(user_id)
    if categoria in metas:
        del metas[categoria]
        set_user_data(user_id, "metas", metas)

def get_lembretes_db(user_id):
    return get_user_data(user_id, "lembretes", [])

def salvar_lembrete_db(user_id, data):
    lembretes = get_lembretes_db(user_id)
    lembretes.append(data)
    set_user_data(user_id, "lembretes", lembretes)

def apagar_lembrete_db(user_id, timestamp):
    lembretes = get_lembretes_db(user_id)
    novos = [l for l in lembretes if l.get('timestamp') != timestamp]
    set_user_data(user_id, "lembretes", novos)

def salvar_senha_db(user_id, senha):
    set_user_data(user_id, "senha", senha)

def verificar_senha_db(user_id, senha):
    senha_salva = get_user_data(user_id, "senha", None)
    return senha_salva is not None and senha_salva == senha

def get_all_user_ids():
    user_ids_tuplas = db.session.query(ConfiguracaoUsuario.user_id).distinct().all()
    return sorted([uid[0] for uid in user_ids_tuplas])
