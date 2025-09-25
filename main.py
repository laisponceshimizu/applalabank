from flask import Flask, request, make_response, render_template, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

# --- INÍCIO DAS MODIFICAÇÕES PARA O RENDER ---

# 1. Inicializa o app Flask
app = Flask(__name__)

# 2. Configura a chave secreta e a URL do banco de dados a partir das variáveis de ambiente
#    Você vai configurar estas variáveis no painel do Render.
app.secret_key = os.environ.get('SECRET_KEY', 'uma-chave-padrao-para-desenvolvimento')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Inicializa o SQLAlchemy para conectar o app ao banco de dados
db = SQLAlchemy(app)

# --- FIM DAS MODIFICAÇÕES PARA O RENDER ---


# Importa as funções dos outros arquivos
from utils import processar_mensagem, send_whatsapp_message, verificar_e_enviar_lembretes
from database import (
    salvar_meta_db, apagar_categoria_db, apagar_conta_db,
    adicionar_conta_db, adicionar_categoria_db, apagar_meta_db,
    salvar_regras_cartao_db, apagar_lembrete_db, apagar_transacao_db,
    get_all_user_ids,
    verificar_senha_db
)
from dashboard_calculations import calcular_dados_dashboard

# Importa os modelos do banco de dados
from models import *

@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        data = request.get_json()
        if data is None:
            print("AVISO: Recebido POST request sem JSON.")
            return make_response("EVENT_RECEIVED", 200)

        try:
            message_data = data['entry'][0]['changes'][0]['value']['messages'][0]
            if message_data['type'] == 'text':
                phone_number = message_data['from']
                message_body = message_data['text']['body']

                resposta_bot = processar_mensagem(phone_number, message_body)

                if resposta_bot:
                    if isinstance(resposta_bot, tuple):
                        for msg in resposta_bot:
                            send_whatsapp_message(phone_number, msg)
                    else:
                        send_whatsapp_message(phone_number, resposta_bot)

        except (KeyError, IndexError):
            print(f"✅ Notificação recebida, mas não é uma mensagem de texto. Ignorando.")
            print(f"Dados completos recebidos: {data}")


        return make_response("EVENT_RECEIVED", 200)

    elif request.method == 'GET':
        from utils import VERIFY_TOKEN
        token_sent = request.args.get("hub.verify_token")
        if token_sent == VERIFY_TOKEN:
            challenge = request.args.get("hub.challenge")
            return make_response(challenge, 200)
        return make_response('Invalid verification token', 403)

@app.route("/")
@app.route("/dashboard")
def dashboard_home():
    user_ids = get_all_user_ids()
    return render_template('user_selection.html', user_ids=user_ids)

@app.route("/login/<user_id>", methods=['GET', 'POST'])
def login(user_id):
    if request.method == 'POST':
        senha = request.form.get('senha')
        if verificar_senha_db(user_id, senha):
            session['authenticated_user'] = user_id
            return redirect(url_for('dashboard', user_id=user_id))
        else:
            flash('Senha incorreta. Tente novamente.', 'error')

    return render_template('login.html', user_id=user_id)

@app.route("/logout")
def logout():
    session.pop('authenticated_user', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('dashboard_home'))

@app.route("/dashboard/<user_id>")
def dashboard(user_id):
    if 'authenticated_user' not in session or session['authenticated_user'] != user_id:
        return redirect(url_for('login', user_id=user_id))

    dados_dashboard = calcular_dados_dashboard(user_id)
    return render_template('dashboard.html', **dados_dashboard)

@app.route("/check_reminders")
def check_reminders():
    verificar_e_enviar_lembretes()
    return "Verificação de lembretes concluída."

# --- Rotas para a Aba de Configurações ---

@app.route("/add_category", methods=['POST'])
def add_category():
    data = request.get_json()
    adicionar_categoria_db(data['user_id'], data['nome_categoria'], data['palavras_chave'])
    return make_response("Categoria adicionada", 200)

@app.route("/delete_category", methods=['POST'])
def delete_category():
    data = request.get_json()
    apagar_categoria_db(data['user_id'], data['nome_categoria'])
    return make_response("Categoria apagada", 200)

@app.route("/add_account", methods=['POST'])
def add_account():
    data = request.get_json()
    adicionar_conta_db(data['user_id'], data['nome_conta'])
    return make_response("Conta adicionada", 200)

@app.route("/delete_account", methods=['POST'])
def delete_account():
    data = request.get_json()
    apagar_conta_db(data['user_id'], data['nome_conta'])
    return make_response("Conta apagada", 200)

@app.route("/add_meta", methods=['POST'])
def add_meta():
    data = request.get_json()
    salvar_meta_db(data['user_id'], data['categoria'], float(data['valor']))
    return make_response("Meta adicionada", 200)

@app.route("/delete_meta", methods=['POST'])
def delete_meta():
    data = request.get_json()
    apagar_meta_db(data['user_id'], data['categoria'])
    return make_response("Meta apagada", 200)

@app.route("/save_card_rules", methods=['POST'])
def save_card_rules():
    data = request.get_json()
    salvar_regras_cartao_db(data['user_id'], data['regras'])
    return make_response("Regras salvas", 200)

@app.route("/delete_lembrete", methods=['POST'])
def delete_lembrete():
    data = request.get_json()
    apagar_lembrete_db(data['user_id'], data['timestamp'])
    return make_response("Lembrete apagado", 200)

@app.route("/delete_transaction", methods=['POST'])
def delete_transaction():
    data = request.get_json()
    apagar_transacao_db(data['user_id'], data['timestamp'])
    return make_response("Transação apagada", 200)

# --- ROTA ADICIONADA PARA ATUALIZAR TRANSAÇÕES ---
@app.route("/update_transaction", methods=['POST'])
def update_transaction():
    data = request.get_json()
    # Acessa a transação pelo ID
    transacao = Transacao.query.get(data['id'])
    
    # Verifica se a transação existe e pertence ao usuário logado
    if not transacao or transacao.user_id != data['user_id']:
        return make_response("Transação não encontrada", 404)

    # Atualiza os campos com os novos valores do dashboard
    transacao.categoria = data.get('categoria')
    transacao.metodo = data.get('metodo')
    
    # Zera os campos de conta/cartão para evitar dados inconsistentes
    transacao.conta = None
    transacao.cartao = None
    
    # Define o campo correto baseado no método selecionado
    if transacao.metodo == 'débito':
        transacao.conta = data.get('conta_cartao')
    elif transacao.metodo == 'crédito':
        transacao.cartao = data.get('conta_cartao')

    # Salva as alterações no banco de dados
    db.session.commit()
    return make_response("Transação atualizada", 200)

if __name__ == "__main__":
    # Esta parte é para rodar localmente, o Render usará o gunicorn
    app.run(host='0.0.0.0', port=5000)
