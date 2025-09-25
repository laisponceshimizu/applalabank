import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import requests

# Importa os componentes do novo banco de dados
from main import db
from models import Transacao, CompraParcelada, ConfiguracaoUsuario
from database import (
    get_user_data, set_user_data,
    salvar_transacao_db, salvar_compra_parcelada_db,
    get_categorias, get_contas_conhecidas, get_cartoes_conhecidos,
    salvar_lembrete_db, get_lembretes_db, adicionar_conta_db,
    salvar_senha_db, definir_contas_iniciais_db
)

VERIFY_TOKEN = "teste"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL")

def send_whatsapp_message(phone_number, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
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
    partes = texto.split()
    if len(partes) < 2 or not partes[1]:
        return "❌ Formato inválido. Use: senha [sua_senha_aqui]"
    nova_senha = partes[1]
    salvar_senha_db(user_id, nova_senha)
    return "✅ Senha definida com sucesso! Use esta senha para acessar seu dashboard na web."

def processar_configuracao_contas(user_id, texto):
    if texto == 'pular':
        set_user_data(user_id, 'estado_usuario', None)
        return ("Sem problemas! Você pode configurar suas contas, categorias e metas a qualquer momento na aba 'Configurações' do seu dashboard.", "Digite `ajuda` para ver os comandos ou simplesmente comece a registrar suas transações.")
    
    nomes_contas = [nome.strip().capitalize() for nome in texto.split(',') if nome.strip()]
    
    if not nomes_contas:
        return "Não consegui identificar nenhum nome de conta. Por favor, tente novamente (ex: Bradesco, Nubank)."

    definir_contas_iniciais_db(user_id, nomes_contas)
    set_user_data(user_id, 'estado_usuario', None)

    return ("✅ Ótimo! Suas contas foram salvas.", "Agora você está pronto para começar! Digite `ajuda` para ver todos os comandos.")

def processar_mensagem(user_id, texto):
    texto_lower = texto.lower()

    # --- LÓGICA DE RESETAR USUÁRIO (CORRIGIDA) ---
    if texto_lower == "resetar meus dados":
        return ("⚠️ ATENÇÃO! ⚠️", "Você tem certeza que deseja apagar TODOS os seus dados? Esta ação não pode ser desfeita.", "Para confirmar, envie: `sim apagar tudo`")
    
    if texto_lower == "sim apagar tudo":
        # Apaga todas as configurações genéricas do usuário
        ConfiguracaoUsuario.query.filter_by(user_id=user_id).delete()
        # Apaga todas as transações do usuário
        Transacao.query.filter_by(user_id=user_id).delete()
        # Apaga todas as compras parceladas do usuário
        CompraParcelada.query.filter_by(user_id=user_id).delete()
        # Confirma as alterações no banco de dados
        db.session.commit()
        return "✅ Seus dados foram apagados com sucesso."
    # --- FIM DA CORREÇÃO ---

    estado_usuario = get_user_data(user_id, "estado_usuario", None)
    
    if estado_usuario == 'aguardando_contas':
        return processar_configuracao_contas(user_id, texto_lower)

    senha_definida = get_user_data(user_id, "senha", None)
    if not senha_definida:
        if texto_lower.startswith("senha "):
            resposta_senha = processar_comando_senha(user_id, texto)
            set_user_data(user_id, 'estado_usuario', 'aguardando_contas')
            return (
                "Olá! Bem-vindo(a) ao Lalabank! 👋",
                resposta_senha,
                "\nAntes de começar, vamos configurar suas contas para facilitar os registros.",
                "Por favor, envie os nomes dos bancos e cartões que você usa, separados por vírgula (ex: Bradesco, Nubank, C6 Bank).",
                "Se preferir, digite `pular` para começar com as contas padrão e configure depois no dashboard."
            )
        else:
            return ("Olá! Bem-vindo(a) ao Lalabank, seu assistente financeiro pessoal! 👋", "Para começar e garantir a segurança dos seus dados, o primeiro passo é criar uma senha.", "Por favor, envie uma mensagem no seguinte formato:\n`senha sua_senha_aqui`")

    if texto_lower == "ajuda":
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}" if DASHBOARD_URL else "O link do dashboard não está configurado."
        mensagem_ajuda = ("Aqui estão os comandos que você pode usar:\n\n"
                          "*Finanças:*\n"
                          "- Para registrar um gasto: `gastei 50 no mercado com o cartão Nubank`\n"
                          "- Para registrar uma receita: `recebi 1000 de salário no Itaú`\n\n"
                          "*Recursos:*\n"
                          "- Para compras parceladas, digite `parcelado`.\n"
                          "- Para lembretes de contas, digite `lembrete`.\n"
                          "- Para definir uma meta de gastos: `meta Alimentação 800`\n\n"
                          "*Conta:*\n"
                          "- Para alterar sua senha: `senha [nova_senha]`\n"
                          f"- Para acessar seu dashboard: {link_dashboard}")
        return mensagem_ajuda

    if texto_lower in ["dashboard", "link"]:
        if not DASHBOARD_URL:
            return "❌ O administrador ainda não configurou a URL do dashboard."
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}"
        return ("Aqui está o seu link de acesso pessoal ao dashboard:", link_dashboard)

    if texto_lower.startswith("senha "):
        return processar_comando_senha(user_id, texto)

    if texto_lower.startswith("meta "):
        return processar_comando_meta(user_id, texto)

    if texto_lower == "lembrete":
        return ("Para registar um lembrete, copie o modelo abaixo, preencha e envie:", "lembrete: [descrição]\nvalor: [valor]\nvence dia: [dia]")

    if texto_lower.startswith("lembrete:"):
        return processar_comando_lembrete(user_id, texto)

    if texto_lower == "parcelado":
        return gerar_modelo_parcelado(user_id)

    if texto_lower.startswith("parcelado:"):
        return processar_compra_parcelada(user_id, texto)
    
    return processar_transacao_normal(user_id, texto)

# O restante das funções em utils.py (processar_comando_lembrete, gerar_modelo_parcelado, etc.)
# podem permanecer as mesmas.
