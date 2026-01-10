import streamlit as st
import pandas as pd
from datetime import datetime
from json import dumps, loads
import requests
import time
from settings import API_URL

# --- FUNÇÕES DE APOIO ---

def sanitizar_evento(dict_evento):
    """Converte valores incompatíveis (NaN, NumPy tipos) para tipos nativos Python."""
    import numpy as np
    novo_dict = {}
    for k, v in dict_evento.items():
        if pd.isna(v) or v is np.nan:
            novo_dict[k] = None
        elif isinstance(v, (np.float64, np.float32)):
            novo_dict[k] = float(v)
        elif isinstance(v, (np.int64, np.int32)):
            novo_dict[k] = int(v)
        else:
            novo_dict[k] = v
    return novo_dict

def enviar_tabela(dataframe):
    linhas = dataframe.to_json(orient='records', date_format='iso')
    linhas = loads(linhas)
    tabela = dumps({"dados": linhas})
    
    resp = requests.post(f'{API_URL}eventos/inserir_eventos_tabela', tabela, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")

        # --- Tratamento de Sucesso (200 OK) ---
    if resp.status_code == 200:
        st.success('✅ Dados enviados com sucesso!')          
    # --- Tratamento de Erro de Validação (422 Unprocessable Entity) ---
    elif resp.status_code == 422:
        st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')
                            
        detail = resposta_json.get('detail', {})
        linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
        
        if linhas_rejeitadas:
            st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
            df_erros = pd.DataFrame(linhas_rejeitadas)
            st.dataframe(df_erros)
        else:
            st.text(f"Detalhe de erro da API: {detail}")
    else:
        st.error(f"⚠️ Erro HTTP inesperado: Status {resp.status_code}")

@st.dialog("Inserir excell", width='large')        
def carregar_tabela():
    uploaded_file  = st.file_uploader('Excolha o arquico com as operações')
    if uploaded_file  is not None:        
        dataframe = pd.read_excel(uploaded_file)
        
        titulo_padrao = ['fk_ativo', 'ativo_gerado', 'tipo', 'data_aprov', 'data_com', 'data_pag', 'valor_base', 'proporcao', 'dinheiro', 'operacao']
        titulo = dataframe.columns.tolist()

        if not titulo_padrao == titulo:
            st.warning('Colunas fora do padrão')
        else:
            with st.expander('Exibir Dados input'):
                st.dataframe(dataframe, width='content')

            if st.button('Enviar'):
                enviar_tabela(dataframe)

# --- CONFIGURAÇÃO E ESTADO ---
st.set_page_config(layout="wide", page_title="Cadastro de Eventos")

if 'evento_dict' not in st.session_state or st.session_state['evento_dict'] is None:
    # Inicializa com valores padrão seguros
    st.session_state['evento_dict'] = {
        'fk_ativo': '', 'ativo_gerado': '', 'tipo': 'DESDOBRAMENTO',
        'data_aprov': datetime.now(), 'data_com': datetime.now(), 'data_pag': datetime.now(),
        'valor_base': 0.0, 'proporcao': 0.0, 'dinheiro': None, 'operacao': None
    }

# --- BARRA SUPERIOR E NAVEGAÇÃO ---
col_t, col_e, col_l, col_b = st.columns([3, 1, 1, 1])

col_t.title("📝 Cadastro de Evento")
col_e.button("📥 Inserir tabela", width="stretch", on_click=carregar_tabela)
# Botão Limpar
if col_l.button("🗑️ Limpar Campos", width="stretch"):
    st.session_state['evento_dict'] = None # Atribui None para resetar
    st.rerun()

# Botão Voltar
if col_b.button("⬅️ Voltar", width="stretch"):
    st.switch_page("Pages/Evento/main.py")

st.divider()

# --- FORMULÁRIO ---
ev = st.session_state['evento_dict']

with st.form("form_evento"):
    # Seção 1: Identificação
    col1, col2, col3 = st.columns(3)
    id_ativo = col1.text_input("ID Ativo Original", value=ev.get('fk_ativo', ''))
    ativo_gerado = col2.text_input("ID Ativo Gerado", value=ev.get('ativo_gerado', ''))
    
    tipo_lista = ['BONIFICAÇÃO', 'DESDOBRAMENTO', 'GRUPAMENTO', 'CISÃO', 'INCORPORAÇÃO', 
                  'REDUÇÃO DE CAPITAL', 'FRAÇÃO', 'OPA', 'ATUALIZAÇÃO', 'GRUPAMENTO_DESDOBRAMENTO']
    
    # Validação do index do selectbox
    try:
        idx_tipo = tipo_lista.index(ev.get('tipo'))
    except:
        idx_tipo = 1 # Fallback para DESDOBRAMENTO
        
    tipo = col3.selectbox("Tipo de Evento", options=tipo_lista, index=idx_tipo)

    # Seção 2: Datas
    st.subheader('📅 Período do Evento')
    d1, d2, d3 = st.columns(3)
    data_aprov = d1.date_input("Aprovação", ev.get('data_aprov'))
    data_com = d2.date_input("Data Com", ev.get('data_com'))
    data_pag = d3.date_input("Pagamento", ev.get('data_pag'))

    st.divider()
    
    # Seção 3: Financeiro
    v1, v2, v3 = st.columns(3)
    valor_base = v1.number_input("Valor Base", format="%.5f", value=float(ev.get('valor_base') or 0.0))
    proporcao = v2.number_input("Proporção (%)", format="%.5f", value=float(ev.get('proporcao') or 0.0))
    dinheiro = v3.text_input("Fórmula Dinheiro", value=str(ev.get('dinheiro') or ""))

    # Seção 4: JSON
    op_val = ev.get('operacao')
    default_op = dumps(op_val) if isinstance(op_val, (list, dict)) else str(op_val or '[{"id_ativo": "WEGE3_AÇÕES", "custo": "0", "qt": "qt*1.0"}]')
    operacao_raw = st.text_area("JSON da Operação", value=default_op, height=80)

    submitted = st.form_submit_button("💾 Inserir Evento", type="primary", width='stretch')

# --- LOGICA DE ENVIO ---
if submitted:
    try:
        op_json = loads(operacao_raw)
    except:
        st.error("JSON de Operação inválido.")
        st.stop()

    novo_evento = {
        'fk_ativo': id_ativo,
        'ativo_gerado': ativo_gerado,
        'tipo': tipo,
        'data_aprov': data_aprov.isoformat(),
        'data_com': data_com.isoformat(),
        'data_pag': data_pag.isoformat(),
        'valor_base': valor_base,
        'proporcao': proporcao,
        'dinheiro': dinheiro if dinheiro else None,
        'operacao': op_json
    }
    
    # Sanitização final para evitar erros de tipos do JS/Streamlit
    evento_final = sanitizar_evento(novo_evento)
    
    df_envio = pd.DataFrame([evento_final])
    enviar_tabela(df_envio)