import streamlit as st
import requests
import pandas as pd
from json import dumps, loads


# Configuração da URL da API
API_URL = 'https://pythonapi-production-6268.up.railway.app/'
# API_URL = 'http://localhost:8000/'
token = st.session_state.get('token')


def processar_evento(evento):
    resp = requests.get(f'{API_URL}eventos/processar_evento/?ev_json={evento}', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code == 404:
        st.toast(f'ℹ️ Eventos vazias: {resp.text}.')       
        return []

    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar Eventos: Status {resp.status_code}")        
        return []
    
    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        return []    
    
    return dict_resp

def get_evento(token):
    resp = requests.get(f'{API_URL}eventos/pesquisa/{st.session_state.get("sl_ativo", "")}', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code == 404:
        st.toast(f'ℹ️ Eventos vazias: {resp.text}.')       
        return []

    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar Eventos: Status {resp.status_code}")        
        return []
    
    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        return []    
    
    return dict_resp

@st.dialog("Escolha qual ativo")
def proc_ativo():
    ativo = st.text_input("Pesquisa ativo", placeholder="Pesquisa ativo", key='sl_ativo')
    if ativo:        
        st.session_state['evento_api'] = get_evento(st.session_state.token)
        st.rerun()

@st.dialog("Criar Evento", width='large')
def criar_evento():
    proporcao = None
    dinheiro = None
    ativo_gerado = None
    valor = None

    with st.container(horizontal=True):
        tipo = st.selectbox('Tipo', ['BONIFICAÇÃO', 'FRAÇÃO', 'DESDOBRAMENTO', 'GRUPAMENTO'])
        
        data_aprov = st.date_input('Data de aprovação', format='DD/MM/YYYY')
        data_com = st.date_input('Data de com direito', format='DD/MM/YYYY')
        data_pag = st.date_input('Data de pagamento', format='DD/MM/YYYY')
    
    cadastrar = st.checkbox('Salvar no Banco')
    
    if tipo == 'BONIFICAÇÃO':
        with st.form("Bonificação", clear_on_submit=False):    
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                ativo_gerado = id_ativo
                valor = st.number_input("Valor por cota")
                proporcao = st.number_input("Proporção")

            submitted_detalhes = st.form_submit_button("Simular", type="primary")

            if submitted_detalhes:
                operacao = [{"id_ativo": id_ativo, "custo": f"{valor}*qt*{proporcao}", "qt": f"qt*{proporcao}"}]
    
    if tipo == 'FRAÇÃO':
        with st.form("Bonificação", clear_on_submit=False):    
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                valor = st.number_input("Valor por cota")

            submitted_detalhes = st.form_submit_button("Simular", type="primary")

            if submitted_detalhes:
                operacao = [{"id_ativo": id_ativo, "custo": f"{valor}*qt", "qt": "-qt"}]

    if tipo == 'DESDOBRAMENTO':
        with st.form("Bonificação", clear_on_submit=False):    
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                proporcao = st.number_input("Proporção")

            submitted_detalhes = st.form_submit_button("Simular", type="primary")

            if submitted_detalhes:
                st.text(f'De 1 para {proporcao/100 + 1}')
                operacao = [{"id_ativo": id_ativo, "custo": "0", "qt": f"qt*{proporcao/100}"}]

    if tipo == 'GRUPAMENTO':
        with st.form("Grupamento", clear_on_submit=False):    
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                proporcao = st.number_input("Proporção")

            submitted_detalhes = st.form_submit_button("Simular", type="primary")

            if submitted_detalhes:
                st.text(f'De {1/proporcao} para 1')
                operacao = [{"id_ativo": id_ativo, "custo": "0", "qt": f"qt*{proporcao}"}]

    if submitted_detalhes:
        if cadastrar:
            #inserir rota para cadastrar no banco de dados evento.
            st.stop()
            pass

        # Mostrar previa do calculo
        evento_dict = {
                'id': 0,
                'fk_ativo':  id_ativo,
                'ativo_gerado': ativo_gerado,
                'tipo': tipo,
                'data_aprov': data_aprov.isoformat(),
                'data_com': data_com.isoformat(),
                'data_pag': data_pag.isoformat(),
                'valor_base': valor,
                'proporcao': proporcao,
                'dinheiro': dinheiro,
                'operacao': operacao}
        
        evento = dumps(evento_dict, ensure_ascii=False)
        dict_resp = processar_evento(evento)
        
        df_resp = pd.DataFrame(dict_resp)

        colunas_brl = ['preco_op_brl', 'custo_acum_brl', 'lucro_brl', 'dolar_bc'] 
        colunas_usd = ['preco_op_usd', 'custo_acum_usd', 'lucro_usd']
        culunas_numero = ['quant_', 'quant_acum', 'quant_fracao']
        
        formatos = {col: 'R$ {:,.2f}' for col in colunas_brl}
        formatos.update({col: 'US$ {:,.2f}' for col in colunas_usd})
        formatos.update({col: '{:,.2f}' for col in culunas_numero})
        
        colunas_numericas = [
            'quant_', 'quant_acum', 'preco_op_brl', 'custo_acum_brl', 'lucro_brl', 
            'preco_op_usd', 'custo_acum_usd', 'lucro_usd', 'quant_fracao', 'dolar_bc'
        ]

        for col in colunas_numericas:
            # Converte forçando para float, e transforma erros em NaN
            df_resp[col] = pd.to_numeric(df_resp[col], errors='coerce')


        df_resp = df_resp[['tipo','seq', 'fk_ativo', 'data_op_com', 
                                    'quant_', 'quant_acum', 
                                    'preco_op_brl', 'custo_acum_brl', 'lucro_brl',
                                    'preco_op_usd', 'custo_acum_usd', 'lucro_usd',
                                    'quant_fracao', 'moeda','dolar_bc']].style.format(formatos)
        
        st.dataframe(df_resp)

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
#------------------------------------------------
#Delcarar sessions
#------------------------------------------------
if 'evento_api' not in st.session_state or st.session_state['evento_api'] is None:    
    st.session_state['evento_api'] = get_evento(st.session_state.token)

#-----------------------------------------------
# Layout
#-----------------------------------------------
with st.container(horizontal=True, horizontal_alignment='right'):
    st.header(f"Eventos")
    st.button(f'Criar Evento', on_click=criar_evento)
    st.button(f'Inserir tabela', on_click=carregar_tabela)
    st.button(f'Pesquisa eventos', on_click=proc_ativo)

if not st.session_state['evento_api']:
   st.info('Ativo selecionado não evetnos.')
   st.stop()

df_eventos = pd.DataFrame(st.session_state['evento_api'])
st.dataframe(df_eventos, hide_index=True, width='content')