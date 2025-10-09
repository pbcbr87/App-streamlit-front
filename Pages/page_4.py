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
    st.session_state['carteira_api'] = False
if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

df_carteira = pd.DataFrame(st.session_state['carteira_api'])
df_carteira['pais'] = np.where((df_carteira['categoria'] == "AÇÕES") | (df_carteira['categoria'] == "FII"), 'BRL', 'USD')
df_carteira['%_lucro'] =  df_carteira['lucro_brl'] / df_carteira['custo_brl']
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
                'Aporte': 'aporte',
                'Percentual do aporte': 'aporte_per'
                }
    option = st.selectbox("Ordendar por", list(op_ordem.keys()))
    
mask = df_carteira['categoria'].isin(mult_sl_cat)
df_carteira = df_carteira[mask]
st.write(df_carteira)
#----------------------------------------------------------------------
# Aporte
#---------------------------------------------------------------------
# Valor a ser aportado
valor_aporte = st.number_input('Valor de aporte:',value=None, format="%.2f", min_value=0.00)
if not valor_aporte:
    valor_aporte = 0
 
# Calculo
valor_total = df_carteira['valor_mercado_brl'].sum() + valor_aporte
peso_total =  df_carteira['peso'].sum()

df_carteira['valor_plan_brl'] = df_carteira['peso']*valor_total/peso_total
df_carteira['aporte'] =  df_carteira['valor_plan_brl'] - df_carteira['valor_mercado_brl']
df_carteira['aporte_per'] = np.where(df_carteira['valor_mercado_brl'] == 0, 1, df_carteira['aporte'] / df_carteira['valor_mercado_brl'])
df_carteira = df_carteira[df_carteira['aporte'] > 0]
st.write(df_carteira)

# quantidade de ativos
qt_ativo_aporte = st.number_input('Quantos ativos', value=len(df_carteira), format='%i', min_value=0, max_value=len(df_carteira))
st.write(df_carteira[['codigo_ativo', 'categoria','valor_mercado_brl', 'aporte', 'aporte_per']].head(qt_ativo_aporte).sort_values(op_ordem[option], ascending=[False]).style.format({
    'aporte_per': '{:,.2%}',    
    'valor_mercado_brl': 'R$ {:.,2f}'
}))
