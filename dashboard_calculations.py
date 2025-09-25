from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import (
    get_transacoes_db, get_compras_parceladas_db, get_metas_db,
    get_contas_conhecidas, get_categorias, get_regras_cartoes_db,
    get_cartoes_conhecidos, get_lembretes_db
)

# --- Funções Auxiliares (sem alteração) ---
def _calcular_parcelas_do_mes(compras_parceladas, regras_cartoes):
    hoje = datetime.now()
    parcelas_do_mes = []
    for compra in compras_parceladas:
        data_inicio = datetime.fromisoformat(compra['data_inicio'])
        valor_parcela = compra['valor_total'] / compra['num_parcelas']

        for i in range(compra['num_parcelas']):
            dia_compra = data_inicio.day
            dia_fechamento = regras_cartoes.get(compra.get("cartao"), {}).get('fechamento', 30)
            mes_inicio_fatura = 0 if dia_compra <= dia_fechamento else 1
            data_parcela_fatura = data_inicio + relativedelta(months=i + mes_inicio_fatura)

            if data_parcela_fatura.year == hoje.year and data_parcela_fatura.month == hoje.month:
                parcelas_do_mes.append({
                    "tipo": "despesa", "descricao": f"{compra['descricao']} ({i+1}/{compra['num_parcelas']})",
                    "valor": valor_parcela, "categoria": compra['categoria'],
                    "metodo": "crédito", "cartao": compra['cartao'],
                    "conta": None, "timestamp": (data_inicio + relativedelta(months=i)).isoformat()
                })
    return parcelas_do_mes

def _calcular_saldos_por_conta(transacoes_completas, contas_conhecidas):
    saldos_por_conta = {}
    todas_as_contas = contas_conhecidas.get('contas', [])
    for conta in todas_as_contas:
        saldos_por_conta[conta] = {'receitas': 0, 'despesas': 0, 'saldo': 0}

    for t in transacoes_completas:
        if t.get('tipo') == 'receita' or (t.get('tipo') == 'despesa' and t.get('metodo') == 'débito'):
            conta = t.get('conta')
            if conta in saldos_por_conta:
                if t.get('tipo') == 'receita':
                    saldos_por_conta[conta]['receitas'] += t.get('valor', 0)
                elif t.get('tipo') == 'despesa':
                    saldos_por_conta[conta]['despesas'] += t.get('valor', 0)

    for conta in saldos_por_conta:
        saldos_por_conta[conta]['saldo'] = saldos_por_conta[conta]['receitas'] - saldos_por_conta[conta]['despesas']
    return saldos_por_conta

def _calcular_previsao_faturas(compras_parceladas, contas_conhecidas, regras_cartoes):
    hoje = datetime.now()
    meses_previsao_nomes = [(hoje + relativedelta(months=i)).strftime('%b/%y') for i in range(12)]
    previsao_faturas = {cartao: {m: 0 for m in meses_previsao_nomes} for cartao in contas_conhecidas.get('cartoes', [])}

    for compra in compras_parceladas:
        cartao = compra.get('cartao')
        if not cartao: continue
        
        data_inicio = datetime.fromisoformat(compra['data_inicio'])
        valor_parcela = compra['valor_total'] / compra['num_parcelas']
        num_parcelas = compra['num_parcelas']
        
        dia_fechamento = regras_cartoes.get(cartao, {}).get('fechamento', 30)
        mes_inicio_fatura = 0 if data_inicio.day <= dia_fechamento else 1

        for i in range(num_parcelas):
            data_fatura = data_inicio + relativedelta(months=i + mes_inicio_fatura)
            mes_ano_fatura = data_fatura.strftime('%b/%y')
            if cartao in previsao_faturas and mes_ano_fatura in meses_previsao_nomes:
                 previsao_faturas[cartao][mes_ano_fatura] += valor_parcela
    return previsao_faturas, meses_previsao_nomes

def _calcular_progresso_metas(transacoes_completas, metas):
    gastos_por_categoria = {}
    for t in transacoes_completas:
        if t.get('tipo') == 'despesa':
            cat = t.get('categoria', 'Outros')
            gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + t.get('valor', 0)

    progresso_metas = {}
    for categoria, valor_meta in metas.items():
        gasto_atual = gastos_por_categoria.get(categoria, 0)
        progresso = (gasto_atual / valor_meta) * 100 if valor_meta > 0 else 0
        progresso_metas[categoria] = {'gasto': gasto_atual, 'meta': valor_meta, 'percentual': min(progresso, 100)}
    return progresso_metas


# --- Função Principal ---
def calcular_dados_dashboard(user_id):
    transacoes_normais = [dict(t) for t in get_transacoes_db(user_id)]
    for t in transacoes_normais:
        t['is_deletable'] = True

    compras_parceladas = [dict(p) for p in get_compras_parceladas_db(user_id)]
    lembretes_manuais = [dict(l) for l in get_lembretes_db(user_id)]
    
    # --- ALTERAÇÃO 1: Ordena as metas por nome da categoria ---
    metas_data = get_metas_db(user_id)
    metas = dict(sorted(metas_data.items()))
    
    regras_cartoes = dict(get_regras_cartoes_db(user_id))
    contas_data = get_contas_conhecidas(user_id)
    
    # --- ALTERAÇÃO 2: Ordena as listas de contas e cartões ---
    contas_conhecidas = {
        'contas': sorted(list(contas_data.get('contas', []))),
        'cartoes': sorted(list(contas_data.get('cartoes', [])))
    }

    # --- ALTERAÇÃO 3: Ordena o dicionário de categorias pelo nome ---
    categorias_data = get_categorias(user_id)
    categorias_usuario = dict(sorted(categorias_data.items()))
    
    parcelas_do_mes = _calcular_parcelas_do_mes(compras_parceladas, regras_cartoes)
    for p in parcelas_do_mes:
        p['is_deletable'] = False

    transacoes_completas = sorted(transacoes_normais + parcelas_do_mes, key=lambda t: t.get('timestamp', ''), reverse=True)

    total_receitas = sum(t['valor'] for t in transacoes_completas if t.get('tipo') == 'receita')
    total_despesas = sum(t['valor'] for t in transacoes_completas if t.get('tipo') == 'despesa')
    balanco = total_receitas - total_despesas
    
    despesas_debito = [t for t in transacoes_completas if t.get('metodo') == 'débito' and t.get('tipo') == 'despesa']
    despesas_credito = [t for t in transacoes_completas if t.get('metodo') == 'crédito' and t.get('tipo') == 'despesa']
    total_gastos_debito = sum(t['valor'] for t in despesas_debito)
    total_gastos_credito = sum(t['valor'] for t in despesas_credito)
    
    saldos_por_conta = _calcular_saldos_por_conta(transacoes_completas, contas_conhecidas)
    
    faturas_atuais = {}
    for t in despesas_credito:
        cartao = t.get("cartao")
        if cartao:
            faturas_atuais[cartao] = faturas_atuais.get(cartao, 0) + t.get('valor', 0)

    previsao_faturas, meses_previsao_nomes = _calcular_previsao_faturas(compras_parceladas, contas_conhecidas, regras_cartoes)

    hoje = datetime.now()
    despesas_credito_a_vista = [t for t in transacoes_normais if t.get('metodo') == 'crédito' and t.get('tipo') == 'despesa']
    
    for t in despesas_credito_a_vista:
        cartao = t.get('cartao')
        if cartao and cartao in previsao_faturas:
            dia_compra = datetime.fromisoformat(t['timestamp']).day
            dia_fechamento = regras_cartoes.get(cartao, {}).get('fechamento', 30)
            mes_fatura = hoje if dia_compra <= dia_fechamento else hoje + relativedelta(months=1)
            mes_fatura_str = mes_fatura.strftime('%b/%y')

            if mes_fatura_str in previsao_faturas[cartao]:
                previsao_faturas[cartao][mes_fatura_str] += t.get('valor', 0)

    progresso_metas = _calcular_progresso_metas(transacoes_completas, metas)

    lembretes_automaticos = []
    mes_atual_fatura_str = hoje.strftime('%b/%y')
    
    for cartao, faturas in previsao_faturas.items():
        valor_fatura_atual = faturas.get(mes_atual_fatura_str, 0)
        
        if valor_fatura_atual > 0:
            dia_vencimento = regras_cartoes.get(cartao, {}).get('vencimento')
            if dia_vencimento:
                lembretes_automaticos.append({
                    "descricao": f"Fatura Cartão {cartao}",
                    "valor": valor_fatura_atual,
                    "dia_vencimento": dia_vencimento,
                    "is_deletable": False
                })
    
    lembretes_combinados = sorted(lembretes_manuais + lembretes_automaticos, key=lambda x: x.get('dia_vencimento', 99))

    return {
        'user_id': user_id, 'transacoes': transacoes_completas, 'total_receitas': total_receitas,
        'total_despesas': total_despesas, 'balanco': balanco, 'despesas_debito': despesas_debito,
        'despesas_credito': despesas_credito, 'total_gastos_debito': total_gastos_debito,
        'total_gastos_credito': total_gastos_credito, 'saldos_por_conta': saldos_por_conta,
        'faturas': faturas_atuais, 'previsao_faturas': previsao_faturas, 'meses_previsao': meses_previsao_nomes,
        'progresso_metas': progresso_metas, 'categorias_disponiveis': categorias_usuario,
        'contas_disponiveis': contas_conhecidas, 'metas': metas, 
        'lembretes': lembretes_combinados,
        'regras_cartoes': regras_cartoes
    }
