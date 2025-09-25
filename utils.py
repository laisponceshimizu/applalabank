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
    definir_contas_iniciais_db # Importa a nova função de onboarding
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
    """Processa a resposta do usuário durante a configuração inicial de contas."""
    if texto == 'pular':
        set_user_data(user_id, 'estado_usuario', None) # Limpa o estado
        return (
            "Sem problemas! Você pode configurar suas contas, categorias e metas a qualquer momento na aba 'Configurações' do seu dashboard.",
            "Digite `ajuda` para ver os comandos ou simplesmente comece a registrar suas transações."
        )
    
    nomes_contas = [nome.strip().capitalize() for nome in texto.split(',') if nome.strip()]
    
    if not nomes_contas:
        return "Não consegui identificar nenhum nome de conta. Por favor, tente novamente (ex: Bradesco, Nubank)."

    definir_contas_iniciais_db(user_id, nomes_contas)
    set_user_data(user_id, 'estado_usuario', None) # Limpa o estado

    return (
        "✅ Ótimo! Suas contas foram salvas.",
        "Agora você está pronto para começar! Digite `ajuda` para ver todos os comandos."
    )

def processar_mensagem(user_id, texto):
    """
    Função principal que decide o que fazer com a mensagem do utilizador,
    com fluxo de onboarding e ajuda para senha.
    """
    texto_lower = texto.lower()

    # --- Lógica de Resetar Usuário ---
    if texto_lower == "resetar meus dados":
        return ("⚠️ ATENÇÃO! ⚠️", "Você tem certeza que deseja apagar TODOS os seus dados? Esta ação não pode ser desfeita.", "Para confirmar, envie: `sim apagar tudo`")
    
    if texto_lower == "sim apagar tudo":
        ConfiguracaoUsuario.query.filter_by(user_id=user_id).delete()
        Transacao.query.filter_by(user_id=user_id).delete()
        CompraParcelada.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return "✅ Seus dados foram apagados com sucesso."

    # --- Lógica de Estado do Usuário ---
    estado_usuario = get_user_data(user_id, "estado_usuario", None)
    
    if estado_usuario == 'aguardando_contas':
        return processar_configuracao_contas(user_id, texto)

    # --- Lógica de Novo Usuário ---
    senha_definida = get_user_data(user_id, "senha", None)
    if not senha_definida:
        if texto_lower.startswith("senha "):
            resposta_senha = processar_comando_senha(user_id, texto)
            set_user_data(user_id, 'estado_usuario', 'aguardando_contas')
            return ("Olá! Bem-vindo(a) ao Lalabank! 👋", resposta_senha, "\nAntes de começar, vamos configurar suas contas para facilitar os registros.", "Por favor, envie os nomes dos bancos e cartões que você usa, separados por vírgula (ex: Bradesco, Nubank, C6 Bank).", "Se preferir, digite `pular` para começar com as contas padrão e configure depois no dashboard.")
        else:
            return ("Olá! Bem-vindo(a) ao Lalabank, seu assistente financeiro pessoal! 👋", "Para começar e garantir a segurança dos seus dados, o primeiro passo é criar uma senha.", "Por favor, envie uma mensagem no seguinte formato:\n`senha sua_senha_aqui`")

    # --- Lógica de Comandos para Usuários Existentes ---
    if texto_lower == "ajuda":
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}" if DASHBOARD_URL else "O link do dashboard não está configurado."
        mensagem_ajuda = ("Aqui estão os comandos que você pode usar:\n\n"
                          "*Finanças:*\n- Para registrar um gasto: `gastei 50 no mercado com o cartão Nubank`\n- Para registrar uma receita: `recebi 1000 de salário no Itaú`\n\n"
                          "*Recursos:*\n- Para compras parceladas, digite `parcelado`.\n- Para lembretes de contas, digite `lembrete`.\n- Para definir uma meta de gastos: `meta Alimentação 800`\n\n"
                          "*Conta:*\n- Para alterar sua senha: `senha [nova_senha]`\n"
                          f"- Para acessar seu dashboard: {link_dashboard}")
        return mensagem_ajuda

    if texto_lower in ["dashboard", "link"]:
        if not DASHBOARD_URL:
            return "❌ O administrador ainda não configurou a URL do dashboard."
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}"
        return ("Aqui está o seu link de acesso pessoal ao dashboard:", link_dashboard)

    # --- INÍCIO DA NOVA LÓGICA DE "ESQUECI A SENHA" ---
    palavras_chave_senha = ["esqueci a senha", "perdi a senha", "mudar a senha", "alterar senha", "redefinir senha"]
    if any(palavra in texto_lower for palavra in palavras_chave_senha):
        return "Para criar ou redefinir sua senha, basta enviar uma nova no formato:\n`senha sua_nova_senha_aqui`"
    # --- FIM DA NOVA LÓGICA ---
    
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

def processar_comando_lembrete(user_id, texto):
    try:
        dados = {}
        for linha in texto.split('\n'):
            if ':' in linha:
                chave, valor = linha.split(':', 1)
                dados[chave.strip().lower()] = valor.strip()

        descricao = dados['lembrete']
        valor = float(dados['valor'].replace(',', '.'))
        dia_vencimento = int(dados['vence dia'])

        if not (1 <= dia_vencimento <= 31):
            return "❌ O dia do vencimento deve ser um número entre 1 e 31."

        lembrete_data = {
            "descricao": descricao, "valor": valor, 
            "dia_vencimento": dia_vencimento, "timestamp": datetime.now().isoformat()
        }
        salvar_lembrete_db(user_id, lembrete_data)
        return f"✅ Lembrete registado: '{descricao}' no valor de R$ {valor:.2f}, com vencimento todo dia {dia_vencimento}."
    except (ValueError, KeyError, IndexError):
        return "❌ Formato do lembrete inválido. Por favor, use o modelo exato que eu enviei."

def processar_comando_meta(user_id, texto):
    try:
        partes = texto.split()
        if len(partes) < 3:
            return "❌ Formato inválido. Use: meta [categoria] [valor]"

        nome_categoria = partes[1].capitalize()
        valor_meta = float(partes[2].replace(',', '.'))

        categorias_usuario = get_categorias(user_id)
        if nome_categoria not in categorias_usuario:
            return (f"❌ Categoria '{nome_categoria}' não encontrada.\n\n"
                    f"Categorias disponíveis são: {', '.join(categorias_usuario.keys())}")

        from database import salvar_meta_db
        salvar_meta_db(user_id, nome_categoria, valor_meta)
        return f"✅ Meta de R$ {valor_meta:.2f} definida para a categoria '{nome_categoria}'."

    except (ValueError, IndexError):
        return "❌ Formato inválido. Use: meta [categoria] [valor]"

def gerar_modelo_parcelado(user_id):
    cartoes = get_cartoes_conhecidos(user_id)
    instrucao = (
        "Para registar uma compra parcelada, por favor, copie o modelo abaixo, preencha os dados e envie:"
    )
    modelo = (
        "parcelado: [descrição da compra]\n"
        "valor: [valor total]\n"
        "parcelas: [Nº de parcelas]\n"
        f"cartão: [um de: {', '.join(cartoes)}]"
    )
    return instrucao, modelo

def processar_compra_parcelada(user_id, texto):
    try:
        dados = {}
        linhas = texto.split('\n')

        descricao = linhas[0].split(':', 1)[1].strip()

        for linha in linhas[1:]:
            if ':' in linha:
                chave, valor = linha.split(':', 1)
                dados[chave.strip().lower()] = valor.strip()

        valor_total = float(dados['valor'].replace(',', '.'))
        num_parcelas = int(dados['parcelas'])
        cartao = dados['cartão'].capitalize()

        cartoes_conhecidos = get_cartoes_conhecidos(user_id)
        if cartao not in cartoes_conhecidos:
            return f"❌ Cartão '{cartao}' não reconhecido. Cartões disponíveis: {', '.join(cartoes_conhecidos)}."

        valor_parcela = valor_total / num_parcelas
        categoria = categorizar_transacao(descricao, 'despesa', user_id)

        compra_data = {
            "descricao": descricao, "valor_total": valor_total,
            "num_parcelas": num_parcelas, "cartao": cartao,
            "categoria": categoria, "data_inicio": datetime.now().isoformat()
        }
        salvar_compra_parcelada_db(user_id, compra_data)

        return (f"✅ Compra parcelada registada: '{descricao}'\n"
                f"Valor: R$ {valor_total:.2f} em {num_parcelas}x de R$ {valor_parcela:.2f}\n"
                f"Cartão: {cartao}")

    except (ValueError, KeyError, IndexError):
        return "❌ Formato da compra parcelada inválido. Por favor, use o modelo exato que eu enviei."

def processar_transacao_normal(user_id, texto):
    tipo, valor, descricao_original, metodo, cartao, conta = extrair_dados_transacao_normal(user_id, texto)

    if valor is None:
        return "Não consegui identificar um valor na sua mensagem. Tente novamente."

    categoria = categorizar_transacao(descricao_original, tipo, user_id)

    transacao_data = {
        "tipo": tipo, "descricao": descricao_original, "valor": valor,
        "categoria": categoria, "metodo": metodo, "cartao": cartao,
        "conta": conta, "timestamp": datetime.now().isoformat()
    }
    salvar_transacao_db(user_id, transacao_data)

    if tipo == 'despesa':
        return f"✅ Despesa registada: '{descricao_original}' (R$ {valor:.2f})."
    elif tipo == 'receita':
        return f"✅ Receita registada: '{descricao_original}' (R$ {valor:.2f})."

def extrair_dados_transacao_normal(user_id, texto):
    tipo, valor, metodo, cartao, conta = 'despesa', None, None, None, None
    texto_lower = texto.lower()

    palavras_despesa = ['comprei', 'gastei', 'paguei']
    palavras_receita = ['recebi', 'ganhei', 'salário']

    if any(p in texto_lower for p in palavras_despesa): tipo = 'despesa'
    if any(p in texto_lower for p in palavras_receita): tipo = 'receita'

    match_valor = re.search(r'([\d,]+(?:[.,]\d+)?)(\s*(k|mil))?', texto_lower, re.IGNORECASE)
    if match_valor:
        try:
            numero_str = match_valor.group(1).replace(',', '.')
            numero = float(numero_str)
            sufixo = match_valor.group(3)
            if sufixo and sufixo.lower() in ['k', 'mil']:
                numero *= 1000
            valor = numero
        except (ValueError, IndexError):
            valor = None

    if 'crédito' in texto_lower or 'cartao' in texto_lower or 'cartão' in texto_lower:
        metodo = 'crédito'
        cartoes = get_cartoes_conhecidos(user_id)
        for c in cartoes:
            if c.lower() in texto_lower:
                cartao = c
                break
    elif 'débito' in texto_lower or 'pix' in texto_lower:
        metodo = 'débito'
        contas = get_contas_conhecidas(user_id).get('contas', [])
        for c in contas:
            if c.lower() in texto_lower:
                conta = c
                break

    if tipo == 'receita':
        metodo = 'débito' # Entrada em conta
        contas = get_contas_conhecidas(user_id).get('contas', [])
        for c in contas:
            if c.lower() in texto_lower:
                conta = c
                break

    return tipo, valor, texto, metodo, cartao, conta

def categorizar_transacao(descricao, tipo, user_id):
    categorias = get_categorias(user_id)
    descricao_lower = descricao.lower()

    categorias_receita = {
        'Salário': ['salário'],
        'Outras Receitas': ['recebi', 'ganhei', 'investimentos']
    }

    if tipo == 'receita':
        for categoria, palavras in categorias_receita.items():
            if any(palavra in descricao_lower for palavra in palavras):
                return categoria
        return 'Outras Receitas'

    elif tipo == 'despesa':
        for categoria, palavras in categorias.items():
            if categoria not in ['Salário', 'Outras Receitas']:
                if any(palavra in descricao_lower for palavra in palavras):
                    return categoria
    return 'Outros'

def verificar_e_enviar_lembretes():
    """
    Verifica todos os lembretes de todos os utilizadores e envia notificações
    para aqueles que estão próximos do vencimento.
    """
    # Esta função precisaria ser adaptada para iterar sobre todos os usuários no novo banco de dados,
    # em vez de escanear chaves do replit.db.
    # Por enquanto, esta função não funcionará no Render sem uma nova lógica para obter todos os user_ids.
    print("Verificação de lembretes iniciada (lógica a ser adaptada para SQLAlchemy).")
