import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from json import loads, dumps
from decimal import Decimal, DivisionByZero


#------------------------------------------------
API_URL = 'https://pythonapi-production-6268.up.railway.app/'
#------------------------------------------------

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
        f'{API_URL}Ativos/lista_ativos/{st.session_state['sl_cat']}?ativo={st.session_state['sl_ativo']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

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
colunas_brl = ['preco_op_brl', 'custo_acum_brl', 'lucro_brl', 'dolar_bc'] 
colunas_usd = ['preco_op_usd', 'custo_acum_usd', 'lucro_usd']
culunas_numero = ['quant_', 'quant_acum', 'quant_fracao']
formatos = {col: 'R$ {:,.2f}' for col in colunas_brl}
formatos.update({col: 'US$ {:,.2f}' for col in colunas_usd})
formatos.update({col: '{:,.2f}' for col in culunas_numero})

df_movimentacao = df_movimentacao[['tipo','seq', 'fk_ativo', 'data_op_com', 
                                    'quant_', 'quant_acum', 
                                    'preco_op_brl', 'custo_acum_brl', 'lucro_brl',
                                    'preco_op_usd', 'custo_acum_usd', 'lucro_usd',
                                    'quant_fracao', 'moeda','dolar_bc']].style.format(formatos)
st.dataframe(df_movimentacao, hide_index=True, width='content', height=700)
