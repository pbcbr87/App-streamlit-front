import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from datetime import datetime
from json import dumps, loads
from datetime import date, datetime
from decimal import Decimal


# Funções
def get_eventos():
    resp = requests.get(f'{API_URL}eventos_pessoal/pegar_eventos/{st.session_state.get("id", 0)}', headers={'Authorization':f'Bearer {st.session_state.token}'})   
    
    if resp.status_code == 404:
        st.session_state['evento_pessoal_dict'] = []
        return

    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar movimentação: Status {resp.status_code}")
        st.session_state['evento_pessoal_dict'] = []
        return
    
    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        st.session_state['evento_pessoal_dict'] = []
        return

    for item in dict_resp:
        for item_key, valor in item.items():
            if isinstance(valor, str):
                valor_limpo = valor.strip()
                if not valor_limpo:
                    continue
                try:
                    # A conversão de str para Decimal
                    item[item_key] = Decimal(valor_limpo)
                except Exception:
                    pass # Deixa como string se não for um número
    st.session_state['evento_pessoal_dict'] = dict_resp
    return

def set_aceito(status, id):
    dados = {
        'aceito': status
    }
    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.put(f'{API_URL}eventos_pessoal/evento/{id}', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
        # --- Tratamento de Sucesso (200 OK) ---

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def excluir(id):
    resp = requests.delete(f'{API_URL}eventos_pessoal/evento/{id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        st.toast("Excluido com sucesso")

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def formatar_data(valor):
    """Converte string do banco para objeto date do Python"""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except:
        return None
#-------------------------------------------------------------------------------------------
# --- Inicialização ---       
if 'evento_pessoal_dict' not in st.session_state:
    get_eventos()
#-------------------------------------------------------------------------------------------
tipo_lista = ['BONIFICAÇÃO', 'DESDOBRAMENTO', 'GRUPAMENTO', 'CISÃO', 'INCORPORAÇÃO', 
                    'REDUÇÃO DE CAPITAL', 'FRAÇÃO', 'OPA', 'ATUALIZAÇÃO', 'GRUPAMENTO_DESDOBRAMENTO']

#-------------------------------------------------------------------------------------------
st.title("🧐 Eventos Coorporativos na carteira")

#layout da paigina
layout_superior = st.container(border=True)
c1, c2, c3, c4, c5 = layout_superior.columns(5)  

layout_inferior = st.container(border=True, horizontal=True, vertical_alignment='center')

#------------------------------------------------------------------------------------------
with layout_inferior:
    sl_fk_ativo = st.text_input("Filtrar Eventos por ativo", on_change=get_eventos)    
    
    sl_tipo = st.pills("Tipo do Evento:", options=tipo_lista, selection_mode='multi', key='sl_tipo_eventos')

    st.button("",icon=':material/cancel:', type='tertiary', help='Desmarcar tudo', key='Key_BT_3', on_click=lambda: st.session_state.update(sl_tipo_eventos=[]))
    st.button("",icon=':material/checklist_rtl:', type='tertiary', help='Selecionar tudo', key='Key_BT_2', on_click=lambda: st.session_state.update(sl_tipo_eventos=tipo_lista))

#-----------------------------------------------------------------------------------
# Gerar Data frame
#----------------------------------------------------------------------------------
if c1.button("➕ Inserir Evento", width="stretch"):
    st.switch_page('Pages/Evento_pessoal/insert_evento_coorp.py')

if 'evento_pessoal_dict' not in st.session_state or not st.session_state.evento_pessoal_dict:
    st.info("💡 Não tem Eventos Coorporativos cadastrados.")
else:
    #------------------------------------------------------------------
    # Tabela de Ativos Cadastrados
    #------------------------------------------------------------------
    colunas = ['id','fk_evento','aceito','foi_aplicado','modo_insert','tipo','fk_ativo', 'ativo_gerado','data_aprov', 'data_com','data_pag', 'proporcao', 'valor', 'data_insert']
    colunas_view = ['aceito','foi_aplicado','modo_insert','tipo','fk_ativo', 'ativo_gerado','data_aprov', 'data_com','data_pag', 'proporcao', 'valor', 'data_insert']
    df = pd.DataFrame(st.session_state['evento_pessoal_dict'], columns=colunas)
        

    if sl_tipo:
        df = df[df['tipo'].isin(sl_tipo)]
    if sl_fk_ativo: 
        df = df[df['fk_ativo'].str.contains(sl_fk_ativo.upper())]
    

    df_display = df.copy()
    df_display['foi_aplicado'] = df_display['foi_aplicado'].apply(lambda x: "🙋‍♂️" if x else "🛌")
    df_display['aceito'] = df_display['aceito'].apply(lambda x: "✔️" if x else "⚪")

    st.write("Selecione uma linha para editar ou visualizar detalhes:")
    ativo_sl = st.dataframe(
        df_display, 
        width="stretch", 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_order=colunas_view,
        column_config={
            'foi_aplicado': st.column_config.Column(
                "Integrado",
                help="Indica se o evento já foi processado no cálculo da carteira, 🙋‍♂️ Integrado ao saldo | 🛌 Não aplicado",
                width="small",
                
            ),
            'aceito': st.column_config.Column(
                "On/Off",
                width="small"
            ),
            'proporcao': st.column_config.NumberColumn("Proporção", format="%.4f"),
            'valor': st.column_config.NumberColumn("Valor", format="R$ %.2f"),
        }
    )
    #------------------------------------------------------------------
    # Capturar a seleção
    #------------------------------------------------------------------      
    selecao = ativo_sl.selection.get("rows", [])

    if selecao:        
        idx = selecao[0]
        linha_selecionada = df.iloc[idx].to_dict()    
        if linha_selecionada['aceito']:
            if c2.button("[OFF⚪] Desligar", width="stretch"):
                set_aceito(False, linha_selecionada['id'])
                get_eventos()
                st.rerun()
        else:
            if c2.button("[✔️ON] Ligar", width="stretch"):
                set_aceito(True, linha_selecionada['id'])
                get_eventos()
                st.rerun()

        if c3.button("🗑️ Excluir Ativo", width="stretch"):
            excluir(linha_selecionada['id'])
            get_eventos()
            st.rerun()
    else:
        st.session_state['linha_selecionada_ativo'] = {}
        st.info("💡 Clique em uma linha da tabela acima para habilitar as ações.")


