import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from json import loads, dumps

def get_ativos():
    st.session_state['lista'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/Ativos/lista_ativos/{st.session_state['sl_cat']}?ativo={st.session_state['sl_ativo']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

def envia_peso(dados):
    st.write(dados)

def envia_manual(dados):
    dados = dumps(dados)
    try:
        resp = requests.post('https://pythonapi-production-6268.up.railway.app/carteira/inserir_ativo', dados, headers={'Authorization':f'Bearer {st.session_state.token}'})
        if resp.status_code == 201:
            st.toast('Dados enviados')
            st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
        else:
            st.error(f'Erro ao enviar, Erro: {resp}')
    except TypeError as e:
        st.error(f'Erro ao enviar: {e}')

#--------------------------------------------------
# declaração de memoria
#--------------------------------------------------
if 'carteira_api' not in st.session_state:
    st.session_state['carteira_api'] = False
if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
if not 'sl_cat' in st.session_state:
    st.session_state['sl_cat'] = 'AÇÕES'
if not 'sl_ativo' in st.session_state:
    st.session_state['sl_ativo'] = ''
if not 'lista' in st.session_state:
    get_ativos()
if not 'block_envio' in st.session_state:
    st.session_state['block_envio'] = True

#-------------------------------------
# Layout Aba adiconar novo ativo
#-------------------------------------
cont_botao = st.container(horizontal=True):
with cont_botao.st.popover("Adiconar Ativo"):
    input_Cat = st.selectbox('Tipo:',['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)
    with st.container(border=True, horizontal=True):
        st.text_input("Pesquisa ativo", label_visibility='collapsed', placeholder="Pesquisa ativo", key='sl_ativo', on_change=get_ativos)
        input_Ativo = st.pills('Ativo:', options=st.session_state['lista'], label_visibility='collapsed', selection_mode="single")
    if input_Ativo:
        with st.container(border=True, horizontal=True):
            input_peso = st.number_input('Peso:', format='%f',step=0.01, min_value=0.01, value=None)
            input_nota = st.number_input('Nota:', step=1, min_value=0, max_value=10, value=None)
            dados = {
                "fk_usuario": st.session_state.id,
                "fk_ativo": f'{input_Ativo}_{input_Cat}',
                "peso": input_peso,
                "nota": input_nota
                }
        
            if input_peso != None and input_nota != None:
                st.session_state['block_envio'] = False
            else:
                st.session_state['block_envio'] = True
        if not st.session_state['block_envio']:
            st.button('Enviar', on_click= envia_manual, kwargs={'dados': dados})
#-------------------------------------
# Layout tabela e grafico
#-------------------------------------
if st.session_state['carteira_api'] == []:
    st.write('Carteira vazia ou não calculada')
if not st.session_state['carteira_api'] == []:
    with st.container(horizontal=True):
        df_carteira = pd.DataFrame(st.session_state['carteira_api'])

        df_resp = st.data_editor(df_carteira, column_order =("codigo_ativo", "peso"), width = "content")
        
        cont_botao.st.button('Enviar Peso', on_click= envia_peso, kwargs={'dados': df_resp})
        
        fig = px.pie(df_resp, values='peso', names='codigo_ativo', title='Ativos')
        st.plotly_chart(fig)