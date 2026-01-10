import streamlit as st
import requests
import pandas as pd
import numpy as np
from settings import API_URL
from json import dumps, loads

# --- ESTADOS DA SESSÃO ---
if 'lista_ativos_sugeridos' not in st.session_state:
    st.session_state['lista_ativos_sugeridos'] = []
if 'evento_api' not in st.session_state:
    st.session_state['evento_api'] = []
if 'sl_ativo' not in st.session_state:
    st.session_state['sl_ativo'] = ""
if 'sl_row' not in st.session_state:
    st.session_state['sl_row'] = None
# --- FUNÇÕES DE LÓGICA ---

def get_ativos():
    """Busca ativos baseados na categoria selecionada e no texto digitado"""
    # Evita erro caso o token não esteja presente
    token = st.session_state.get('token')
    if not token:
        st.error("Usuário não autenticado.")
        return

    categoria = st.session_state.get('sl_cat', 'AÇÕES')
    termo = st.session_state.get('sl_ativo', '')

    try:
        url = f'{API_URL}Ativos/lista_ativos/{categoria}?ativo={termo}'
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 200:
            st.session_state['lista_ativos_sugeridos'] = resp.json()
        else:
            st.session_state['lista_ativos_sugeridos'] = []
    except Exception as e:
        st.error(f"Erro ao buscar ativos: {e}")

def carregar_eventos(ativo_selecionado):
    """Busca os eventos detalhados do ativo escolhido no Pills"""
    if ativo_selecionado:
        headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
        resp = requests.get(f'{API_URL}eventos/pesquisa/{ativo_selecionado}', headers=headers)
        if resp.status_code == 200:
            st.session_state['evento_api'] = resp.json()
        else:
            st.session_state['evento_api'] = []

def exluir():
    headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
    evento_id = st.session_state['evento_dict'].get('id')
    resp = requests.delete(f'{API_URL}eventos/delete/{evento_id}', headers=headers)
    if resp.status_code == 200:
        st.success("Evento excluído com sucesso!")
        carregar_eventos(st.session_state.get('pills_selecao'))
        st.session_state['evento_dict'] = {}
        st.rerun()
    else:
        st.error(f"Erro ao excluir evento: Status {resp.status_code}")

# --- LAYOUT INTERFACE ---
st.header("🔍 Pesquisa de Eventos por Ativo")

# Container de Filtros
with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 3])

st.divider()
# --- BOTÕES DE AÇÃO ---
c1, c2, c3, c4 = st.columns(4)   


with col1:
    # Selectbox de Categoria
    st.selectbox('Categoria:', ['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)    
with col2:
    # Input de Texto para o Ticker
    st.text_input("Pesquisar Ticker:", placeholder="Digite o código (ex: PETR4)", key='sl_ativo', on_change=get_ativos)
with col3:
    # Área de Resultados (Pills)
    if st.session_state['lista_ativos_sugeridos']:
        st.write("Selecione o ativo:")
        ativo_escolhido = st.pills("Ativos encontrados:", options=st.session_state['lista_ativos_sugeridos'], label_visibility='collapsed', selection_mode="single", key="pills_selecao")
        # Se mudar a seleção no Pills, carrega os eventos
        if ativo_escolhido:
            carregar_eventos(ativo_escolhido)

# --- TABELA DE EVENTOS ---
if c1.button("➕ Inserir", width='stretch'):    
    st.switch_page('Pages/Evento/insert_evento.py')
if c2.button("🧪 Simular", width='stretch'):
    st.switch_page('Pages/Evento/simular.py')

if st.session_state['evento_api']:
    if st.session_state.get('pills_selecao'):
        st.subheader(f"Eventos de {st.session_state.get('pills_selecao')}")
        df_eventos = pd.DataFrame(st.session_state['evento_api'])
        sl_row = st.dataframe(df_eventos, hide_index=True, on_select="rerun", selection_mode='single-row')
        if sl_row:
            if sl_row.get('selection').get('rows'):
                st.session_state['evento_dict'] = df_eventos.replace({np.nan: None}).iloc[sl_row.get('selection').get('rows')[0]].to_dict()
                if c3.button("📝 Editar", width='stretch'):
                    st.switch_page('Pages/Evento/edit_evento.py')
                if c4.button("🗑️ Excluir", width='stretch'):
                    exluir()
                

elif st.session_state.get('pills_selecao'):
    st.info(f"Nenhum evento cadastrado para {st.session_state.get('pills_selecao')}.")
