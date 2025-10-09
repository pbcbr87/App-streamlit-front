import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from json import loads, dumps


st.write("Aportes")

#-----------------------------------------------------------
# Buscando dados na API
#-----------------------------------------------------------
if 'carteira_api' not in st.session_state:
    st.session_state['carteira_api'] == False
if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
#-----------------------------------------------------------
#Containers layout
#-----------------------------------------------------------
sl_cat_container = st.container(border=True, horizontal=True, vertical_alignment='center')
#-----------------------------------------------------------
#Seletor
#-----------------------------------------------------------
def sl_tudo_ex():       
    st.session_state['Key_SL_2'] = df_cat
def sl_nada_ex():       
    st.session_state['Key_SL_2'] = []
        
df_cat = list(df_carteira['categoria'].unique())    
if 'Key_SL_2' not in st.session_state:
    st.session_state['Key_SL_2'] = df_cat

#multiselect
with sl_cat_container:
    mult_sl_cat = st.pills('categoria', df_cat, key='Key_SL_2', selection_mode="multi")

    st.button("",icon=':material/cancel:', type='tertiary', help='Desmarcar tudo', key='Key_BT_3', on_click=sl_nada_ex)
    st.button("",icon=':material/checklist_rtl:', type='tertiary', help='Selecionar tudo', key='Key_BT_2', on_click=sl_tudo_ex)

    op_ordem = {
                'Valor de mercado': "Valor de mercado",
                'Custo': "Custo",
                'Lucro': "Lucro",
                'Percentual do lucro': "Lucro %",
                'Valor Planejado': 'Valor Planejado',
                'Aporte': 'Aporte',
                'Percentual do aporte': 'Aporte %'
                }
    option = st.selectbox("Ordendar por", list(op_ordem.keys()))

mask = df_carteira['categoria'].isin(mult_sl_cat)
df_carteira = df_carteira[mask]


