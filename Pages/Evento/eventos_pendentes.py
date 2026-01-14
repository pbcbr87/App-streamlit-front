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

def get_evento_pendente(token: str, id) -> list:    
    resp = requests.get(
        f'{API_URL}eventos_pendentes/pegar_evento/{id}', 
        headers={'Authorization':f'Bearer {token}'}
    )
    if resp.status_code == 404:
        st.error(f'Nenhum Evento disponivel: {resp.text}.')
        return []
    
    if resp.status_code != 200:
        st.error(f"Erro ao carregar Evetnos: Status {resp.status_code}")
        return []
    
    dict_resp = resp.json()   
    return dict_resp

def get_eventos_pendente(token: str) -> list:    
    resp = requests.get(
        f'{API_URL}eventos_pendentes/pegar_eventos', 
        headers={'Authorization':f'Bearer {token}'}
    )
    if resp.status_code == 404:
        st.error(f'Nenhum Evento disponivel: {resp.text}.')
        return []
    
    if resp.status_code != 200:
        st.error(f"Erro ao carregar Evetnos: Status {resp.status_code}")
        return []
    
    dict_resp = resp.json()   

    return dict_resp

def formatar_data(valor):
    """Converte string do banco para objeto date do Python"""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except:
        return datetime.now().date()

def formulario_edit(linha_selecionada):
    dados_evento = linha_selecionada
    with st.container(border=True):
        with st.container(horizontal=True):
            st.number_input("ID do Registro", value=dados_evento["id"], disabled=True)
            list_opiton = ["PENDENTE", "EM ANDAMENTO", "IMPLEMENTADO"]
            status = st.selectbox("Status", options=list_opiton, 
                                index=list_opiton.index(dados_evento["status"]))
        with st.container(horizontal=True):
            fk_ativo = st.text_input("Ativo Original", value=dados_evento["fk_ativo"])
            # Tratamos NULL como string vazia para o text_input
            ativo_gerado = st.text_input("Ativo Gerado", value=dados_evento["ativo_gerado"] or "")

            tipo_lista = ['BONIFICAÇÃO', 'DESDOBRAMENTO', 'GRUPAMENTO', 'CISÃO', 'INCORPORAÇÃO', 
                    'REDUÇÃO DE CAPITAL', 'FRAÇÃO', 'OPA', 'ATUALIZAÇÃO', 'GRUPAMENTO_DESDOBRAMENTO']
            try:
                idx_tipo = tipo_lista.index(dados_evento["tipo"])
            except:
                idx_tipo = 1 # Fallback para DESDOBRAMENTO
            tipo = st.selectbox("Tipo", options=tipo_lista, index=idx_tipo)

        with st.container(horizontal=True):
            dt_aprov = st.date_input("Data Aprovação", formatar_data(dados_evento["data_aprov"]))
            dt_com = st.date_input("Data Com", formatar_data(dados_evento["data_com"]))
            dt_pag = st.date_input("Data Pagamento", formatar_data(dados_evento["data_pag"]))
            v_base = st.number_input("Valor Base", value=float(dados_evento["valor_base"] or 0.0), format="%.5f")
            prop = st.number_input("Proporção", value=float(dados_evento["proporcao"] or 0.0), format="%.5f")

        st.write("⚙️ Detalhes Extra")
        formula = st.text_input("Fórmula Dinheiro", value=dados_evento["dinheiro"] or "")
        # Operação geralmente é um JSON, exibimos como texto para edição
        operacao = st.text_area("Operação JSON", value=str(dados_evento["operacao"] or "[]"))

def set_status(status, id):
    dados = {
        'status': status
    }
    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.put(f'{API_URL}eventos_pendentes/evento/{id}', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
        # --- Tratamento de Sucesso (200 OK) ---

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def filtro(df):
    with st.container(border=True, horizontal=True):
        sl = st.pills('Slecione',options=["PENDENTE", "EM ANDAMENTO", "IMPLEMENTADO"],  selection_mode="multi")
        df_filtrado = df[df['status'].isin(sl)] if sl else df

        sl_fk_ativo = st.text_input("Filtrar por Ativo Original")
        if sl_fk_ativo:       
            df_filtrado = df_filtrado[df_filtrado['fk_ativo'].str.contains(sl_fk_ativo.upper())]
    return df_filtrado

if 'lista_eventos' not in st.session_state or st.session_state['lista_eventos'] is None:    
    st.session_state.lista_eventos = get_eventos_pendente(st.session_state.token)

if 'evento_pedente_sel' not in st.session_state:    
    st.session_state.evento_pedente_sel = None

st.set_page_config(layout="wide", page_title="Consulta de Eventos")

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
            set_status("EM ANDAMENTO", linha_selecionada['id'])
            st.session_state.lista_eventos = None
            st.session_state.evento_pedente_sel = get_evento_pendente(st.session_state.token, linha_selecionada['id'])[0]
            st.switch_page("Pages/Evento/simular.py")

        if st.button("🎯 Impementado", width="stretch"):
            set_status("IMPLEMENTADO", linha_selecionada['id'])
            st.session_state.lista_eventos = None
            st.rerun()
        
        if st.button("♻️ Em Andamento", width="stretch"):
            set_status("EM ANDAMENTO", linha_selecionada['id'])
            st.session_state.lista_eventos = None
            st.rerun()

        if st.button("🧐 Pendente", width="stretch"):
            set_status("PENDENTE", linha_selecionada['id'])
            st.session_state.lista_eventos = None
            st.rerun()
    st.header("Evento existente")    
    carregar_eventos(linha_selecionada['fk_ativo'])
    if st.session_state['evento_api']:
        df_eventos = pd.DataFrame(st.session_state['evento_api']).sort_values(by='data_aprov', ascending=False)
        st.dataframe(df_eventos, hide_index=True)
    else:
        st.info("💡 Nenhum evento encontrado para o ativo selecionado.")
else:
    st.info("💡 Clique em uma linha da tabela acima para habilitar as ações.")

