from flask import Flask, request, make_response, render_template
import re
from replit import db
from datetime import datetime
from dateutil.relativedelta import relativedelta # Para cálculos com meses
import requests
import os

# --- SUAS CONFIGURAÇÕES ---
VERIFY_TOKEN = "teste"
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
# -------------------------

app = Flask(__name__)

@app.route('/')
def index():
    """Homepage redirect to dashboard"""
    return render_template('index.html')

# --- (Funções de categorização e processamento de mensagem normal) ---
def categorizar_despesa(descricao):
    # ... (código igual ao anterior)
    descricao_lower = descricao.lower()
    categorias = {
        'Pagamentos': ['cartão de crédito', 'fatura', 'pagamento fatura'],
        'Compras': ['mercado pago', 'mercado livre', 'compras a vista', 'compras parceladas', 'computec'],
        'Assinaturas': ['assinatura', 'apple', 'netflix'], 'Investimentos': ['poupança', 'investi'],
        'Cuidados Pessoais': ['barbearia'], 'Educação': ['educação', 'curso', 'livro', 'puc'],
        'Saúde': ['farmacia', 'médico', 'remédio'],
        'Alimentação': ['ifood', 'marmitex', 'mercado', 'restaurante', 'dualcoffe', 'café', 'pizza', 'lanche'],
        'Transporte': ['carro', 'combustivel', 'combustível', 'uber', '99'],
    }
    for cat, pal in categorias.items():
        if any(p in descricao_lower for p in pal): return cat
    return 'Outros'

def processar_mensagem_normal(texto):
    # ... (código similar ao anterior, mas sem a lógica de parcelamento)
    tipo, valor, descricao, metodo, cartao, conta = 'desconhecido', None, texto, 'outro', None, None
    palavras_despesa = ['comprei', 'gastei', 'paguei']
    palavras_receita = ['recebi', 'ganhei', 'salário']
    texto_lower = texto.lower()
    if any(p in texto_lower for p in palavras_despesa): tipo = 'despesa'
    elif any(p in texto_lower for p in palavras_receita): tipo = 'receita'
    if tipo != 'desconhecido':
        match = re.search(r'[\d,.]+', texto)
        if match: valor = float(match.group(0).replace(',', '.'))
    if tipo == 'receita':
        metodo = 'débito'
        contas_conhecidas = ['itaú', 'swile', 'nubank']
        for c in contas_conhecidas:
            if c in texto_lower: conta = c.capitalize(); break
    elif tipo == 'despesa':
        if 'crédito' in texto_lower or 'cartao' in texto_lower or 'cartão' in texto_lower:
            metodo = 'crédito'
            cartoes_conhecidos = ['itau', 'mercado pago', 'nubank']
            for c in cartoes_conhecidos:
                if c in texto_lower: cartao = c.capitalize(); break
        elif 'débito' in texto_lower or 'pix' in texto_lower or 'swile' in texto_lower:
            metodo = 'débito'
            contas_conhecidas = ['itaú', 'swile', 'nubank']
            for c in contas_conhecidas:
                if c in texto_lower: conta = c.capitalize(); break
    if categorizar_despesa(texto) == 'Pagamentos': metodo = 'débito'
    return tipo, valor, descricao, metodo, cartao, conta


@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        data = request.get_json()
        try:
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            if message_data['type'] == 'text':
                phone_number = message_data['from']
                message_body = message_data['text']['body']

                # --- NOVA LÓGICA: Verifica se é uma compra parcelada ---
                match_parcelado = re.search(r'(.+?)\s+de\s+([\d,.]+)\s+em\s+(\d+)x', message_body, re.IGNORECASE)

                if match_parcelado:
                    # É UMA COMPRA PARCELADA
                    descricao_total = match_parcelado.group(1).strip()
                    valor_total = float(match_parcelado.group(2).replace(',', '.'))
                    num_parcelas = int(match_parcelado.group(3))
                    valor_parcela = valor_total / num_parcelas

                    # Identifica o cartão
                    cartao = None
                    cartoes_conhecidos = ['itau', 'mercado pago', 'nubank']
                    for c in cartoes_conhecidos:
                        if c in message_body.lower():
                            cartao = c.capitalize()
                            break

                    if cartao:
                        db_key = f"parceladas_{phone_number}"
                        if db_key not in db.keys():
                            db[db_key] = []

                        nova_compra_parcelada = {
                            "descricao": descricao_total,
                            "valor_total": valor_total,
                            "num_parcelas": num_parcelas,
                            "valor_parcela": valor_parcela,
                            "cartao": cartao,
                            "data_inicio": datetime.now().isoformat(),
                            "id": datetime.now().timestamp() # um ID único
                        }
                        db[db_key].append(nova_compra_parcelada)
                        print(f"✅ Compra parcelada salva para o usuário {phone_number}!")
                    else:
                         print("❌ Compra parcelada sem cartão especificado.")

                else:
                    # É UMA TRANSAÇÃO NORMAL
                    tipo, valor, descricao, metodo, cartao, conta = processar_mensagem_normal(message_body)
                    if valor is not None:
                        categoria = categorizar_despesa(descricao) if tipo == 'despesa' else "Salário"
                        db_key = f"transacoes_{phone_number}"
                        if db_key not in db.keys(): db[db_key] = []

                        nova_transacao = {
                            "tipo": tipo, "descricao": descricao, "valor": valor, "categoria": categoria, 
                            "metodo": metodo, "cartao": cartao, "conta": conta,
                            "timestamp": datetime.now().isoformat()
                        }
                        db[db_key].append(nova_transacao)
                        print(f"✅ Transação ('{tipo}') salva!")

        except (KeyError, IndexError):
            pass
    elif request.method == 'GET':
        # ... (código de verificação)
        token_sent = request.args.get("hub.verify_token")
        if token_sent == VERIFY_TOKEN: return make_response(request.args.get("hub.challenge"), 200)
        return make_response('Invalid verification token', 403)

    return make_response("EVENT_RECEIVED", 200)


@app.route("/dashboard")
def dashboard():
    meu_numero = "554398091663" 

    # Pega transações normais e compras parceladas
    transacoes_normais = [dict(t) for t in db.get(f"transacoes_{meu_numero}", [])]
    compras_parceladas = [dict(c) for c in db.get(f"parceladas_{meu_numero}", [])]

    # --- LÓGICA DE PROJEÇÃO DE FATURAS ---
    hoje = datetime.now()
    faturas_atuais = {}
    previsao_faturas = {} # Para os próximos meses

    # 1. Adiciona compras normais no crédito à fatura atual
    for t in transacoes_normais:
        if t.get('metodo') == 'crédito' and t.get('cartao'):
            cartao = t['cartao']
            data_transacao = datetime.fromisoformat(t['timestamp'])
            if data_transacao.year == hoje.year and data_transacao.month == hoje.month:
                 faturas_atuais[cartao] = faturas_atuais.get(cartao, 0) + t['valor']

    # 2. Adiciona as parcelas do mês atual e dos próximos meses
    for compra in compras_parceladas:
        data_inicio = datetime.fromisoformat(compra['data_inicio'])
        for i in range(compra['num_parcelas']):
            data_parcela = data_inicio + relativedelta(months=i)
            # Verifica se a parcela ainda está ativa
            if data_parcela >= hoje - relativedelta(months=1): # Pega o mês atual e futuros
                cartao = compra['cartao']
                chave_mes = data_parcela.strftime("%b/%y") # Ex: Set/25

                # Adiciona na fatura do mês corrente
                if data_parcela.year == hoje.year and data_parcela.month == hoje.month:
                    faturas_atuais[cartao] = faturas_atuais.get(cartao, 0) + compra['valor_parcela']

                # Adiciona na previsão de faturas
                if cartao not in previsao_faturas: previsao_faturas[cartao] = {}
                previsao_faturas[cartao][chave_mes] = previsao_faturas[cartao].get(chave_mes, 0) + compra['valor_parcela']

    # Prepara os dados para o dashboard
    # (cálculos de totais, balanço, etc. como antes)
    total_receitas = sum(t['valor'] for t in transacoes_normais if t.get('tipo') == 'receita')
    total_despesas_geral = sum(t['valor'] for t in transacoes_normais if t.get('tipo') == 'despesa')
    balanco = total_receitas - total_despesas_geral

    return render_template('dashboard.html', 
                           transacoes=transacoes_normais,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas_geral,
                           balanco=balanco,
                           faturas=faturas_atuais,
                           previsao_faturas=previsao_faturas # Envia a nova previsão
                          )

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

