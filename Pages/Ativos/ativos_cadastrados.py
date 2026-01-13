import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from datetime import datetime
from json import dumps, loads

def carregar_eventos(ativo_selecionado):
    """Busca os eventos detalhados do ativo escolhido no Pills"""
    if ativo_selecionado:
        headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
        resp = requests.get(f'{API_URL}eventos/pesquisa/{ativo_selecionado}', headers=headers)
        if resp.status_code == 200:
            st.session_state['evento_api'] = resp.json()
        else:
            st.session_state['evento_api'] = []

def filtro(df):
    with st.container(border=True, horizontal=True):
        sl = st.pills('Slecione',options=["PENDENTE", "EM ANDAMENTO", "IMPLEMENTADO"],  selection_mode="multi")
        df_filtrado = df[df['status'].isin(sl)] if sl else df

        sl_fk_ativo = st.text_input("Filtrar por Ativo Original")
        if sl_fk_ativo:       
            df_filtrado = df_filtrado[df_filtrado['fk_ativo'].str.contains(sl_fk_ativo.upper())]
    return df_filtrado

st.set_page_config(layout="wide", page_title="Consulta de Ativos")

st.title("🧐 Eventos Pendentes de Implementação")
df = pd.DataFrame(st.session_state.lista_eventos).sort_values(by='data_aprov', ascending=False)
df = filtro(df)
st.write("Selecione uma linha para editar ou visualizar detalhes:")

event = st.dataframe(
    df,
    width="stretch",
    height=300,
    hide_index=True,
    on_select="rerun",  # Faz a página recarregar ao clicar na linha
    selection_mode="single-row"
)

# 3. Capturar a seleção
# event.selection['rows'] retorna o índice da linha selecionada no DataFrame
selecao = event.selection.get("rows", [])

if selecao:
    idx = selecao[0]
    linha_selecionada = df.iloc[idx].to_dict()
    
    with st.container(horizontal=True):        
        # Botão para Editar: Salva no session_state e muda de página
        if st.button("🧪 Simular", width="stretch"):
            pass
            # set_status("EM ANDAMENTO", linha_selecionada['id'])
            # st.session_state.lista_eventos = None
            # st.session_state.evento_pedente_sel = get_evento_pendente(st.session_state.token, linha_selecionada['id'])[0]
            # st.switch_page("Pages/Evento/simular.py")

        if st.button("🎯 Impementado", width="stretch"):
            pass
            # set_status("IMPLEMENTADO", linha_selecionada['id'])
            # st.session_state.lista_eventos = None
            # st.rerun()
        
        if st.button("♻️ Em Andamento", width="stretch"):
            pass
            # et_status("EM ANDAMENTO", linha_selecionada['id'])
            # st.session_state.lista_eventos = None
            # st.rerun()

        if st.button("🧐 Pendente", width="stretch"):
            pass
            # set_status("PENDENTE", linha_selecionada['id'])
            # st.session_state.lista_eventos = None
            # st.rerun()
    st.header("Evento existente")    
    carregar_eventos(linha_selecionada['fk_ativo'])
    if st.session_state['evento_api']:
        df_eventos = pd.DataFrame(st.session_state['evento_api']).sort_values(by='data_aprov', ascending=False)
        st.dataframe(df_eventos, hide_index=True)
    else:
        st.info("💡 Nenhum evento encontrado para o ativo selecionado.")
else:
    st.info("💡 Clique em uma linha da tabela acima para habilitar as ações.")
