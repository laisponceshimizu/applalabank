import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import requests
from replit import db

from database import (
    get_user_data, set_user_data,
    salvar_transacao_db, salvar_compra_parcelada_db,
    get_categorias, get_contas_conhecidas, get_cartoes_conhecidos,
    salvar_lembrete_db, get_lembretes_db, adicionar_conta_db,
    salvar_senha_db, get_transacoes_db, get_compras_parceladas_db
)

VERIFY_TOKEN = "teste"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL") # Carrega a URL do dashboard

def send_whatsapp_message(phone_number, message):
    """
    Função para enviar uma mensagem de texto simples de volta para o utilizador.
    """
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

# --- Funções de Processamento de Mensagens ---

def processar_comando_senha(user_id, texto):
    """Processa o comando para definir ou alterar a senha."""
    partes = texto.split()
    if len(partes) < 2 or not partes[1]:
        return "❌ Formato inválido. Use: senha [sua_senha_aqui]"

    nova_senha = partes[1]
    salvar_senha_db(user_id, nova_senha)
    return "✅ Senha definida com sucesso! Use esta senha para acessar seu dashboard na web."

def processar_mensagem(user_id, texto):
    """
    Função principal que decide o que fazer com a mensagem do utilizador.
    """
    texto_lower = texto.lower()

    # --- Lógica para Resetar Usuário (PARA TESTES) ---
    if texto_lower == "resetar meus dados":
        return (
            "⚠️ ATENÇÃO! ⚠️",
            "Você tem certeza que deseja apagar TODOS os seus dados? Esta ação não pode ser desfeita.",
            "Para confirmar, envie: `sim apagar tudo`"
        )

    if texto_lower == "sim apagar tudo":
        chaves_para_apagar = [
           "transacoes", "parceladas", "categorias", "contas",
           "regras_cartoes", "metas", "lembretes", "senha", "ultima_pergunta"
        ]
        for chave in chaves_para_apagar:
            chave_db = f"{chave}_{user_id}"
            if chave_db in db:
                del db[chave_db]
        return "✅ Seus dados foram apagados com sucesso. Sua próxima mensagem será tratada como um novo usuário."

    # --- Lógica de Boas-Vindas baseada na existência de senha ---
    senha_definida = get_user_data(user_id, "senha", None)

    if not senha_definida:
        if texto_lower.startswith("senha "):
            # Se a primeira interação é definir a senha, processa e dá as boas-vindas
            resposta_senha = processar_comando_senha(user_id, texto)
            return (
                "Olá! Bem-vindo(a) ao Lalabank! 👋",
                resposta_senha,
                "Agora você pode começar a registrar suas finanças!\n\n"
                "Digite `dashboard` para receber o link de acesso ou `ajuda` para ver todos os comandos."
            )
        else:
            # Se for qualquer outra mensagem, instrui a criar a senha e ignora a mensagem atual
            return (
                "Olá! Bem-vindo(a) ao Lalabank, seu assistente financeiro pessoal! 👋",
                "Para começar e garantir a segurança dos seus dados, o primeiro passo é criar uma senha.",
                "Por favor, envie uma mensagem no seguinte formato:\n`senha sua_senha_aqui`"
            )

    # --- Se a senha já existe, o usuário não é novo. Processa comandos normalmente. ---

    # --- Lógica para comando de ajuda ---
    if texto_lower == "ajuda":
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}" if DASHBOARD_URL else "O link do dashboard não está configurado."
        mensagem_ajuda = (
            "Aqui estão os comandos que você pode usar:\n\n"
            "*Finanças:*\n"
            "- Para registrar um gasto: `gastei 50 no mercado com o cartão Nubank`\n"
            "- Para registrar uma receita: `recebi 1000 de salário no Itaú`\n\n"
            "*Recursos:*\n"
            "- Para compras parceladas, digite `parcelado`.\n"
            "- Para lembretes de contas, digite `lembrete`.\n"
            "- Para definir uma meta de gastos: `meta Alimentação 800`\n\n"
            "*Conta:*\n"
            "- Para alterar sua senha: `senha [nova_senha]`\n"
            f"- Para acessar seu dashboard: {link_dashboard}"
        )
        return mensagem_ajuda

    # --- Lógica para Comandos Específicos ---
    if texto_lower in ["dashboard", "link"]:
        if not DASHBOARD_URL:
            return "❌ O administrador ainda não configurou a URL do dashboard."
        link_dashboard = f"{DASHBOARD_URL}/login/{user_id}"
        return (
            "Aqui está o seu link de acesso pessoal ao dashboard:",
            link_dashboard
        )

    if texto_lower.startswith("senha "):
        return processar_comando_senha(user_id, texto)

    if texto_lower.startswith("meta "):
        return processar_comando_meta(user_id, texto)

    if texto_lower == "lembrete":
        return (
            "Para registar um lembrete, copie o modelo abaixo, preencha e envie:",
            "lembrete: [descrição]\nvalor: [valor]\nvence dia: [dia]"
        )

    if texto_lower.startswith("lembrete:"):
        return processar_comando_lembrete(user_id, texto)

    if texto_lower == "parcelado":
        return gerar_modelo_parcelado(user_id)

    if texto_lower.startswith("parcelado:"):
        return processar_compra_parcelada(user_id, texto)

    # --- Lógica para Respostas a Perguntas do Bot ---
    ultima_pergunta = get_user_data(user_id, "ultima_pergunta", None)
    if ultima_pergunta:
        return processar_resposta_pergunta(user_id, texto_lower, ultima_pergunta)

    # --- Se não for nenhum comando, trata como uma transação normal ---
    return processar_transacao_normal(user_id, texto)

def processar_comando_lembrete(user_id, texto):
    """Extrai dados de uma mensagem de lembrete formatada."""
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

def processar_resposta_pergunta(user_id, texto_resposta, ultima_pergunta):
    set_user_data(user_id, "ultima_pergunta", None) # Limpa a pergunta

    if texto_resposta == "sim":
        tipo_pergunta = ultima_pergunta.get("tipo")
        novo_item = ultima_pergunta.get("item")

        if tipo_pergunta == "nova_conta":
            adicionar_conta_db(user_id, novo_item)
            return f"✅ Conta '{novo_item.capitalize()}' adicionada com sucesso!"
        # Adicionar lógica para nova categoria aqui se necessário

    return "Ok, não vou adicionar."

def gerar_modelo_parcelado(user_id):
    """Gera as duas mensagens de instrução para compras parceladas."""
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
    """Extrai dados de uma mensagem de parcelamento formatada."""
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
    """Processa uma mensagem de transação normal (receita ou despesa)."""
    tipo, valor, descricao_original, metodo, cartao, conta = extrair_dados_transacao_normal(user_id, texto)

    if valor is None:
        return "Não consegui identificar um valor na sua mensagem. Tente novamente."

    # --- NOVA VALIDAÇÃO ---
    if tipo == 'despesa':
        if metodo == 'outro':
            return ("Faltou o método de pagamento. Tente de novo, especificando se foi `débito` ou `crédito`.\n\n"
                    "Ex: `gastei 50 no mercado com o cartão Nubank`")
        if metodo == 'crédito' and cartao is None:
            cartoes = get_cartoes_conhecidos(user_id)
            return (f"Você usou crédito, mas não disse qual cartão. Por favor, tente de novo.\n\n"
                    f"Cartões disponíveis: {', '.join(cartoes)}\n"
                    f"Ex: `gastei 50 no mercado com o cartão {cartoes[0] if cartoes else 'Nubank'}`")
        if metodo == 'débito' and conta is None:
            contas = get_contas_conhecidas(user_id).get('contas', [])
            return (f"Você usou débito, mas não disse de qual conta. Por favor, tente de novo.\n\n"
                    f"Contas disponíveis: {', '.join(contas)}\n"
                    f"Ex: `paguei 50 no mercado com a conta {contas[0] if contas else 'Itaú'}`")

    if tipo == 'receita' and conta is None:
        contas = get_contas_conhecidas(user_id).get('contas', [])
        return (f"Faltou dizer em qual conta a receita entrou. Por favor, tente de novo.\n\n"
                f"Contas disponíveis: {', '.join(contas)}\n"
                f"Ex: `recebi 1000 de salário na conta {contas[0] if contas else 'Itaú'}`")

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
    tipo, valor, metodo, cartao, conta = 'desconhecido', None, 'outro', None, None
    texto_lower = texto.lower()

    palavras_despesa = ['comprei', 'gastei', 'paguei']
    palavras_receita = ['recebi', 'ganhei', 'salário']

    if any(p in texto_lower for p in palavras_despesa): tipo = 'despesa'
    elif any(p in texto_lower for p in palavras_receita): tipo = 'receita'

    # --- LÓGICA DE EXTRAÇÃO DE VALOR MELHORADA ---
    valor = None
    # Regex para encontrar valores como 10, 10.50, 10,50, 2k, 2mil, 1.5k
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
            valor = None # Se a conversão falhar, continua nulo

    # Define o método primeiro, pois é mais explícito
    if 'crédito' in texto_lower or 'cartao' in texto_lower or 'cartão' in texto_lower:
        metodo = 'crédito'
    elif 'débito' in texto_lower or 'pix' in texto_lower:
        metodo = 'débito'

    # Se o método for crédito, procura por um cartão conhecido
    if metodo == 'crédito':
        cartoes = get_cartoes_conhecidos(user_id)
        for c in cartoes:
            if c.lower() in texto_lower:
                cartao = c
                break
    # Se for débito ou receita, procura por uma conta conhecida
    elif metodo == 'débito' or tipo == 'receita':
        metodo = 'débito' # Garante que receitas sejam marcadas como débito (entrada em conta)
        contas = get_contas_conhecidas(user_id).get('contas', [])
        for c in contas:
            if c.lower() in texto_lower:
                conta = c
                break

    # Caso especial para "pagamento de fatura", que é sempre débito
    if categorizar_transacao(texto, 'despesa', user_id) == 'Pagamentos':
        metodo = 'débito'
        # Tenta identificar a conta do pagamento da fatura
        if not conta:
            contas = get_contas_conhecidas(user_id).get('contas', [])
            for c in contas:
                if c.lower() in texto_lower:
                    conta = c
                    break

    return tipo, valor, texto, metodo, cartao, conta

def categorizar_transacao(descricao, tipo, user_id):
    """Categoriza uma transação com base no tipo (receita ou despesa)."""
    categorias = get_categorias(user_id)
    descricao_lower = descricao.lower()

    # Define categorias específicas para receitas
    categorias_receita = {
        'Salário': ['salário'],
        'Outras Receitas': ['recebi', 'ganhei', 'investimentos']
    }

    if tipo == 'receita':
        for categoria, palavras in categorias_receita.items():
            if any(palavra in descricao_lower for palavra in palavras):
                return categoria
        return 'Outras Receitas' # Padrão para receitas não categorizadas

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
    hoje = datetime.now()
    chaves_lembretes = db.prefix("lembretes_") 

    for chave in chaves_lembretes:
        user_id = chave.split("_")[-1]
        lembretes = get_lembretes_db(user_id)

        for lembrete in lembretes:
            dia_vencimento = lembrete.get('dia_vencimento')

            # Lógica para avisar 2 dias antes
            dia_para_avisar = dia_vencimento - 2
            if dia_para_avisar <= 0:
                data_vencimento_mes_atual = datetime(hoje.year, hoje.month, dia_vencimento)
                data_aviso = data_vencimento_mes_atual - relativedelta(days=2)
                dia_para_avisar = data_aviso.day

            if hoje.day == dia_para_avisar:
                mensagem = (
                    f"🔔 Lembrete de Pagamento!\n\n"
                    f"Conta: {lembrete['descricao']}\n"
                    f"Valor: R$ {lembrete['valor']:.2f}\n"
                    f"Vence no dia: {dia_vencimento}"
                )
                send_whatsapp_message(user_id, mensagem)
                print(f"Enviando lembrete para {user_id} sobre '{lembrete['descricao']}'")

