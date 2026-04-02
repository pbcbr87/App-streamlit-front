import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from json import loads, dumps
from decimal import Decimal, DivisionByZero
from settings import API_URL

#------------------------------------------------
# API_URL = 'https://pythonapi-production-6268.up.railway.app/'
# API_URL = 'python_api.railway.internal'
#------------------------------------------------

def divisao_percentual_segura(row: pd.Series, coluna_numerador: str, coluna_denominador: str) -> Decimal:     
    # 1. Tenta extrair os valores (eles devem ser objetos Decimal)
    numerador = row.get(coluna_numerador)
    denominador = row.get(coluna_denominador)
    
    # Se algum valor estiver faltando ou for None, retorna 0
    if numerador is None or denominador is None:
        return Decimal('0')
    # 2. Verifica e trata a divisão por zero
    try:
        if denominador == Decimal('0'):
            return Decimal('0')
    except Exception:
        # Se o denominador não for um Decimal válido (ex: 'abc'), tratamos como 0
        return Decimal('0')
    # 3. Tenta a divisão real
    try:
        return numerador / denominador
    except DivisionByZero:
        # Linha de defesa contra o erro Decimal.
        return Decimal('0')
    except Exception:
        # Captura qualquer outro erro de operação, como tipos misturados
        return Decimal('0')

@st.dialog("Escolha qual ativo")
def proc_ativo():
    st.selectbox('Tipo:',['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)
    st.text_input("Pesquisa ativo", placeholder="Pesquisa ativo", key='sl_ativo', on_change=get_ativos)
    ativo = st.pills('Ativo:', options=st.session_state['lista'], label_visibility='collapsed', selection_mode="single", on_change=get_ativos)
    if ativo:
        st.session_state['sl_ativo_pill'] = ativo
        st.session_state['movimentacao_api'] = get_movimentacao(st.session_state.token)
        st.rerun()

def get_movimentacao(token):
    resp = requests.get(f'{API_URL}ordem_cal/pegar_ordens/{st.session_state.get("id", 0)}?fk_ativo={st.session_state.get("sl_ativo_pill", 0)}_{st.session_state.get("sl_cat", 0)}', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code == 404:
        st.session_state['movimentacao_api'] = []
        return

    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar movimentação: Status {resp.status_code}")
        st.session_state['movimentacao_api'] = []
        return
    
    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        st.session_state['movimentacao_api'] = []
        return

    for item in dict_resp:
        for item_key, valor in item.items():
            if isinstance(valor, str):
                valor_limpo = valor.strip()
                if not valor_limpo:
                    continue
                try:
                    # A conversão de str para Decimal
                    item[item_key] = Decimal(valor_limpo)
                except Exception:
                    pass # Deixa como string se não for um número
    st.session_state['movimentacao_api'] = dict_resp
    return dict_resp

def get_ativos():
    st.session_state['lista'] = requests.get(
        f'{API_URL}ativos/lista_ativos/{st.session_state['sl_cat']}?ativo={st.session_state['sl_ativo']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

#------------------------------------------------
#Delcarar sessions
#------------------------------------------------
if 'sl_ativo_pill' not in st.session_state or st.session_state['sl_ativo_pill'] is None:
    st.session_state['sl_ativo_pill'] = 'Selecione o ativo'

if 'sl_cat' not in st.session_state:
    st.session_state['sl_cat'] = 'AÇÕES'

if 'sl_ativo' not in st.session_state:
    st.session_state['sl_ativo'] = ""

if not 'lista' in st.session_state:
    st.session_state['lista'] = get_ativos()

if 'movimentacao_api' not in st.session_state or st.session_state['movimentacao_api'] is None:    
    st.session_state['movimentacao_api'] = []

#-----------------------------------------------
# Layout
#-----------------------------------------------
with st.container(horizontal=True, horizontal_alignment='right'):
    st.header(f"Movimentação {st.session_state['sl_cat']} {st.session_state['sl_ativo_pill']}")
    st.button(f'{st.session_state['sl_ativo_pill']}',type='primary', on_click=proc_ativo)


# Trantando dados recebidos
if not st.session_state['movimentacao_api']:
   st.info('Ativo selecionado não tem em carteira.')
   st.stop()

df_movimentacao = pd.DataFrame(st.session_state['movimentacao_api'])
df_movimentacao['tipo'] = np.where(df_movimentacao['tipo'].isna(), 'Ordem', df_movimentacao['tipo'])
df_movimentacao['p_unit_brl'] = df_movimentacao.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='preco_op_brl', coluna_denominador='quant_'), axis=1)

colunas_brl = ['preco_op_brl', 'custo_acum_brl', 'lucro_brl', 'dolar_bc', 'p_unit_brl'] 
colunas_usd = ['preco_op_usd', 'custo_acum_usd', 'lucro_usd']
culunas_numero = ['quant_', 'quant_acum', 'quant_fracao']
formatos = {col: 'R$ {:,.2f}' for col in colunas_brl}
formatos.update({col: 'US$ {:,.2f}' for col in colunas_usd})
formatos.update({col: '{:,.2f}' for col in culunas_numero})

df_movimentacao = df_movimentacao[['tipo','seq', 'fk_ativo', 'data_op_com', 
                                    'quant_', 'quant_acum', 
                                    'preco_op_brl', 'custo_acum_brl', 'lucro_brl', 'p_unit_brl',
                                    'preco_op_usd', 'custo_acum_usd', 'lucro_usd',
                                    'quant_fracao', 'moeda','dolar_bc']].style.format(formatos)
st.dataframe(df_movimentacao, hide_index=True, width='content', height=700)
