import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px

def get_ativos():
    st.session_state['lista'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/Ativos/lista_ativos/{st.session_state['sl_cat']}?ativo={st.session_state['sl_ativo']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
if not 'sl_cat' in st.session_state:
    st.session_state['sl_cat'] = 'AÇÕES'
if not 'sl_ativo' in st.session_state:
    st.session_state['sl_ativo'] = ''
if not 'lista' in st.session_state:
    get_ativos()

with st.popover("Adiconar Ativo"):
    input_Cat = st.selectbox('Tipo:',['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)
    with st.container(border=True, horizontal=True):
        st.text_input("Pesquisa ativo", label_visibility='collapsed', placeholder="Pesquisa ativo", key='sl_ativo', on_change=get_ativos)
        input_Ativo = st.pills('Ativo:', options=st.session_state['lista'], label_visibility='collapsed', selection_mode="single")


if st.session_state['carteira_api'] == []:
    st.write('Carteira vazia ou não calculada')
if not st.session_state['carteira_api'] == []:
    df_carteira = pd.DataFrame(st.session_state['carteira_api'])

    df_resp = st.data_editor(df_carteira, column_order =("codigo_ativo", "peso"), width = "content")

    fig = px.pie(df_resp, values='peso', names='codigo_ativo', title='Ativos')
    st.plotly_chart(fig)