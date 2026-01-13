import streamlit as st
import pandas as pd
from datetime import datetime, date
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

def formatar_data_segura(valor):
    """Garante que o valor retornado seja um objeto date puro."""
    if isinstance(valor, (datetime, date)):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.split('T')[0]).date()
        except:
            return date.today()
    return date.today()

def enviar(dict_evento):
    # Serializa o dicionário para JSON string
    corpo_json = dumps(dict_evento, ensure_ascii=False)
    headers = {'Authorization': f'Bearer {st.session_state.token}', 'Content-Type': 'application/json'}
    
    try:
        # CORREÇÃO: Usar PUT e corrigir a interpolação do ID
        url = f"{API_URL}eventos/edit_evento/{dict_evento['id']}"
        resp = requests.put(url, data=corpo_json, headers=headers)
        
        if resp.status_code == 200:
            st.success('✅ Evento atualizado com sucesso!')
            time.sleep(1.5)
            st.switch_page("Pages/Evento/main.py") # Redireciona após sucesso
            return True
        elif resp.status_code == 422:
            st.error('❌ Erro de Validação (422). Verifique os campos.')
            st.json(resp.json())
        else:
            st.error(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"🚨 Erro de conexão: {e}")
    return False

# --- CONFIGURAÇÃO E ESTADO ---
st.set_page_config(layout="wide", page_title="Editar Evento")
if 'evento_dict' not in st.session_state or st.session_state['evento_dict'] is None:
    st.session_state['evento_dict'] = {}

ev = st.session_state['evento_dict']

# --- BARRA SUPERIOR ---
col_t, col_l, col_b = st.columns([3, 1, 1])
col_t.title(f"📝 Editar Evento: {ev.get('fk_ativo', '')}")

if col_l.button("🗑️ Limpar Campos",  width="stretch"):
    st.session_state['evento_dict'] = {}
    st.rerun()

if col_b.button("⬅️ Voltar", width="stretch"):
    st.switch_page("Pages/Evento/main.py")

st.divider()
if st.session_state['evento_dict'].get('id', 0) == 0:
    st.error("Nenhum evento selecionado para edição. Por favor, selecione um evento na página principal.")
    st.stop()
    
# --- FORMULÁRIO ---
with st.form("form_evento"):
    # Campo ID (Geralmente desabilitado na edição para evitar erros)
    id_evento = st.number_input("ID do Evento", value=int(ev.get('id', 0)), disabled=True)
    
    col1, col2, col3 = st.columns(3)
    id_ativo = col1.text_input("ID Ativo Original", value=ev.get('fk_ativo', ''))
    ativo_gerado = col2.text_input("ID Ativo Gerado", value=ev.get('ativo_gerado', ''))
    
    tipo_lista = ['BONIFICAÇÃO', 'DESDOBRAMENTO', 'GRUPAMENTO', 'CISÃO', 'INCORPORAÇÃO', 
                  'REDUÇÃO DE CAPITAL', 'FRAÇÃO', 'OPA', 'ATUALIZAÇÃO', 'GRUPAMENTO_DESDOBRAMENTO']
    
    try:
        idx_tipo = tipo_lista.index(ev.get('tipo'))
    except:
        idx_tipo = 0
        
    tipo = col3.selectbox("Tipo de Evento", options=tipo_lista, index=idx_tipo)
    st.subheader('📅 Período do Evento')
    d1, d2, d3 = st.columns(3)
    data_aprov = d1.date_input("Aprovação", formatar_data_segura(ev.get('data_aprov')), min_value=date(2000, 1, 1))
    data_com = d2.date_input("Data Com", formatar_data_segura(ev.get('data_com')), min_value=date(2000, 1, 1))
    data_pag = d3.date_input("Pagamento", formatar_data_segura(ev.get('data_pag')), min_value=date(2000, 1, 1))

    st.divider()
    
    v1, v2, v3 = st.columns(3)
    valor_base = v1.number_input("Valor Base", format="%.5f", value=float(ev.get('valor_base') or 0.0))
    proporcao = v2.number_input("Proporção (%)", format="%.5f", value=float(ev.get('proporcao') or 0.0))
    dinheiro = v3.text_input("Fórmula Dinheiro", value=str(ev.get('dinheiro') or ""))

    op_val = ev.get('operacao')
    # Tratamento para exibir o JSON corretamente no text_area
    if isinstance(op_val, str):
        default_op = op_val
    else:
        default_op = dumps(op_val, ensure_ascii=False) if op_val else '[]'
        
    operacao_raw = st.text_area("Estrutura da Operação", value=default_op, height=100)

    submitted = st.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True)

# --- LOGICA DE ENVIO ---
if submitted:
    try:
        op_json = loads(operacao_raw)
    except Exception as e:
        st.error(f"❌ JSON de Operação inválido: {e}")
        st.stop()

    dados_atualizados = {
        'id': id_evento,
        'fk_ativo': id_ativo,
        'ativo_gerado': ativo_gerado,
        'tipo': tipo,
        'data_aprov': data_aprov.isoformat(),
        'data_com': data_com.isoformat(),
        'data_pag': data_pag.isoformat(),
        'valor_base': valor_base,
        'proporcao': proporcao,
        'dinheiro': dinheiro if (dinheiro and dinheiro.strip()) else "",
        'operacao': op_json
    }
    
    # Sanitização e Envio
    evento_final = sanitizar_evento(dados_atualizados)
    enviar(evento_final)