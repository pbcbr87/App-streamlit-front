import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px


if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

if st.session_state['carteira_api'] == []:
    st.write('Carteira vazia ou não calculada')
if not st.session_state['carteira_api'] == []:
    df_carteira = pd.DataFrame(st.session_state['carteira_api'])
    
    df_resp = st.data_editor(df_carteira, column_order =("codigo_ativo", "peso"), width = "content")

    fig = px.pie(df_carteira, values='peso', names='codigo_ativo', title='Ativos')
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})