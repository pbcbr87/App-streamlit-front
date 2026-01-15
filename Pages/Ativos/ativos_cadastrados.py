import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from datetime import datetime
from json import dumps, loads
from datetime import date, datetime

def edit_ativo(): 
    dados = st.session_state['ativo_dict']
    ativo_cat = dados.get('ativo_cat', '')

    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.put(f'{API_URL}ativos/edit_ativo/{ativo_cat}', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        st.rerun()

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def insert_ativo(): 
    dados = st.session_state['ativo_dict']

    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.post(f'{API_URL}ativos/criar_ativo', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        st.rerun()

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def excluir():
    dados = st.session_state['ativo_dict']
    ativo_cat = dados.get('ativo_cat', '')

    resp = requests.delete(f'{API_URL}ativos/exclui_ativo/{ativo_cat}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        st.rerun()

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def pesquisa_online(ativo):
    resp = requests.get(f'{API_URL}ativos/pesquisa_ativo/{ativo}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
        st.session_state['ativos_api'] = []
        # --- Tratamento de Sucesso (200 OK) --- 
    if resp.status_code == 200:
        return resposta_json

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def formatar_data(valor):
    """Converte string do banco para objeto date do Python"""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except:
        return None

def carregar_ativos(ativo):
    headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
    resp = requests.get(f'{API_URL}ativos/pesquisar_dados_ativos/{ativo}', headers=headers)
    if resp.status_code == 200:
        st.session_state['ativos_api'] = resp.json()
    else:
        st.session_state['ativos_api'] = []

@st.fragment
def form_ativo(ativo_dict):
    for key in ativo_dict:
        ativo_dict[key] = ativo_dict.get(key) if ativo_dict.get(key) else ""
        
    st.text(ativo_dict.get('setor', "") if ativo_dict.get('setor', "") else "")
    form_1, form_2, form_3, form_4, form_5, form_6, form_7, form_8, form_9, form_10, form_11 = st.columns(11)
    st.session_state['ativo_dict']['ativo_cat'] = form_1.text_input("Ativo Categoria", value=ativo_dict.get('ativo_cat', "")).upper()
    st.session_state['ativo_dict']['categoria'] = form_2.text_input("Categoria", value=ativo_dict.get('categoria', "")).upper()
    st.session_state['ativo_dict']['codigo_ativo'] = form_3.text_input("Codigo do Ativo", value=ativo_dict.get('codigo_ativo', "")).upper()
    st.session_state['ativo_dict']['moeda'] = form_4.text_input("Moeda", value=ativo_dict.get('moeda', "")).upper()
    st.session_state['ativo_dict']['nome'] = form_5.text_input("Nome do Ativo", value=ativo_dict.get('nome', "")).upper()
    st.session_state['ativo_dict']['setor'] = form_6.text_input("Setor", value=ativo_dict.get('setor', "")).upper()
    st.session_state['ativo_dict']['country'] = form_7.text_input("País", value=ativo_dict.get('country', "")).upper()
    st.session_state['ativo_dict']['exchange'] = form_8.text_input("exchange", value=ativo_dict.get('exchange', "")).upper()
    st.session_state['ativo_dict']['symbol'] = form_9.text_input("Símbolo do Ativo", value=ativo_dict.get('symbol', "")).upper()

    data_in = form_10.date_input("data_in", key="data_in", min_value=date(2000, 1, 1), value=None)
    st.session_state['ativo_dict']['data_in'] = data_in.isoformat() if data_in else None
    
    data_off = form_11.date_input("data_off", key="data_off", min_value=date(2000, 1, 1), value=None)
    st.session_state['ativo_dict']['data_off'] = data_off.isoformat() if data_off else None

if 'ativo_dict' not in st.session_state:
   st.session_state['ativo_dict'] = {}

st.set_page_config(layout="wide", page_title="Consulta de Ativos")

st.title("🧐 Ativos Cadastrados")

layout_form_ativo = st.container(border=True)
c1, c2, c3, c4, c5 = layout_form_ativo.columns(5)  

sl_fk_ativo = st.text_input("Filtrar por Ativo Categoria")
if sl_fk_ativo:  
    carregar_ativos(sl_fk_ativo.upper())
else:
    st.session_state.pop('ativos_api', None)

linha_selecionada = {}
if 'ativos_api' not in st.session_state or not st.session_state.ativos_api:
    st.info("💡 Use o campo acima para filtrar ativos cadastrados.")
else:
    #------------------------------------------------------------------
    # Tabela de Ativos Cadastrados
    #------------------------------------------------------------------
    df = pd.DataFrame(st.session_state['ativos_api'])
    st.write("Selecione uma linha para editar ou visualizar detalhes:")

    ativo_sl = st.dataframe(df, width="stretch", height=150, hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row"
                            )
    #------------------------------------------------------------------
    # Capturar a seleção
    #------------------------------------------------------------------
    selecao = ativo_sl.selection.get("rows", [])

    if selecao:        
        idx = selecao[0]
        linha_selecionada = df.iloc[idx].to_dict()    
        
        if c2.button("✏️ Editar Ativo", width="stretch"):
            edit_ativo()

        if c3.button("🗑️ Excluir Ativo", width="stretch"):
            excluir()
    else:
        st.session_state['linha_selecionada_ativo'] = {}
        st.info("💡 Clique em uma linha da tabela acima para habilitar as ações.")

if c1.button("➕ Inserir Ativo", width="stretch"):
    insert_ativo()
    
yahoo_code = c4.text_input('Codigo Yahoo', key='yahoo_code', placeholder='Ex: WEGE3.SA', label_visibility ="collapsed")
if c5.button("🔍 Pesquisa Online 🌍", width="stretch"):
    linha_selecionada = pesquisa_online(yahoo_code.upper())[0]
    

with layout_form_ativo:
    if 'data_in' in st.session_state:
        st.session_state.data_in = formatar_data(linha_selecionada.get('data_in', None))
    if 'data_off' in st.session_state:
        st.session_state.data_off = formatar_data(linha_selecionada.get('data_off', None))

    form_ativo(linha_selecionada)