import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import requests

# Importa os componentes do novo banco de dados (SQLAlchemy)
from main import db
from models import Transacao, CompraParcelada, ConfiguracaoUsuario
from database import (
    get_user_data, set_user_data,
    salvar_transacao_db, salvar_compra_parcelada_db,
    get_categorias, get_contas_conhecidas, get_cartoes_conhecidos,
    salvar_lembrete_db, get_lembretes_db, adicionar_conta_db,
    salvar_senha_db, get_transacoes_db, get_compras_parceladas_db,
    definir_contas_iniciais_db,
    apagar_ultima_transacao_db
)

VERIFY_TOKEN = "teste"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL")

def send_whatsapp_message(phone_number, message):
    # ... (código sem alterações) ...
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone_number, "text": {"body": message}}
    print(f"Tentando enviar para {phone_number}: '{message}'")
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        print(f"Resposta da API da Meta ao enviar: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        if e.response is not None:
            print(f"Resposta recebida da Meta: {e.response.json()}")
        else:
            print("Nenhuma resposta recebida do servidor.")
    return None


def processar_comando_senha(user_id, texto):
    # ... (código sem alterações) ...
    partes = texto.split()
    if len(partes) < 2 or not partes[1]:
        return "❌ Formato inválido. Use: senha [sua_senha_aqui]"
    nova_senha = partes[1]
    salvar_senha_db(user_id, nova_senha)
    return "✅ Senha definida com sucesso! Use esta senha para acessar seu dashboard na web."

# --- INÍCIO DA CORREÇÃO ---
def processar_configuracao_contas(user_id, texto):
    """Processa a resposta do usuário durante a configuração inicial de contas."""
    # Converte para minúsculas e remove espaços para uma verificação mais robusta
    if texto.lower().strip() == 'pular':
        set_user_data(user_id, 'estado_usuario', None) # Limpa o estado
        return (
            "Sem problemas! Você pode configurar suas contas, categorias e metas a qualquer momento na aba 'Configurações' do seu dashboard.",
            "Digite `ajuda` para ver os comandos ou simplesmente comece a registrar suas transações."
        )
    
    # Processa a lista de contas enviada pelo usuário
    nomes_contas = [nome.strip().capitalize() for nome in texto.split(',') if nome.strip()]
    
    if not nomes_contas:
        return "Não consegui identificar nenhum nome de conta. Por favor, tente novamente (ex: Bradesco, Nubank)."

    definir_contas_iniciais_db(user_id, nomes_contas)
    set_user_data(user_id, 'estado_usuario', None) # Limpa o estado

    return (
        "✅ Ótimo! Suas contas foram salvas.",
        "Agora você está pronto para começar! Digite `ajuda` para ver todos os comandos."
    )
# --- FIM DA CORREÇÃO ---

def processar_mensagem(user_id, texto):
    texto_lower = texto.lower()

    if texto_lower == "resetar meus dados":
        return ("⚠️ ATENÇÃO! ⚠️", "Você tem certeza que deseja apagar TODOS os seus dados? Esta ação não pode ser desfeita.", "Para confirmar, envie: `sim apagar tudo`")
    
    if texto_lower == "sim apagar tudo":
        ConfiguracaoUsuario.query.filter_by(user_id=user_id).delete()
        Transacao.query.filter_by(user_id=user_id).delete()
        CompraParcelada.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return "✅ Seus dados foram apagados com sucesso."

    estado_usuario = get_user_data(user_id, "estado_usuario", None)
    
    if estado_usuario == 'aguardando_contas':
        # Passa o texto original para a função, que agora lida com maiúsculas/minúsculas
        return processar_configuracao_contas(user_id, texto)

    senha_definida = get_user_data(user_id, "senha", None)
    if not senha_definida:
        if texto_lower.startswith("senha "):
            resposta_senha = processar_comando_senha(user_id, texto)
            set_user_data(user_id, 'estado_usuario', 'aguardando_contas')
            return ("Olá! Bem-vindo(a) ao Lalabank! 👋", resposta_senha, "\nAntes de começar, vamos configurar suas contas para facilitar os registros.", "Por favor, envie os nomes dos bancos e cartões que você usa, separados por vírgula (ex: Bradesco, Nubank, C6 Bank).", "Se preferir, digite `pular` para começar com as contas padrão e configure depois no dashboard.")
        else:
            return ("Olá! Bem-vindo(a) ao Lalabank, seu assistente financeiro pessoal! 👋", "Para começar e garantir a segurança dos seus dados, o primeiro passo é criar uma senha.", "Por favor, envie uma mensagem no seguinte formato:\n`senha sua_senha_aqui`")

    # (O resto da função continua igual)
    # ...
