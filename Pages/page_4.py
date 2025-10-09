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
if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

