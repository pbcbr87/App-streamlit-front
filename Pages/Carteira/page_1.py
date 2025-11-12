import streamlit as st
import pandas as pd
import requests
from json import loads, dumps
from datetime import datetime, date
from decimal import Decimal


API_URL = 'https://pythonapi-production-6268.up.railway.app/'

def get_operacoes(token):
    resp = requests.get(f'{API_URL}/ordem_input/pegar_ordens', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code == 404:
        st.toast(f'ℹ️ Operações vazias: {resp.text}.')
        st.session_state['operacao_api'] = []
        return

    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar carteira: Status {resp.status_code}")
        st.session_state['operacao_api'] = []
        return
    
    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        st.session_state['operacao_api'] = []
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
    st.session_state['operacao_api'] = dict_resp
    return dict_resp

# Enviar dados para o banco de dados
@st.dialog("Enviando Dados", on_dismiss='rerun')
def enviar_tabela(dataframe):
    st.session_state['carteira_api'] = None
    st.session_state['operacao_api'] = None

    linhas = dataframe.to_json(orient='records', date_format='iso')
    linhas = loads(linhas)
    ordens_tabela = dumps({"dados": linhas})
    
    resp = requests.post(f'{API_URL}ordem_input/inserir_ordens_table', ordens_tabela, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")

        # --- Tratamento de Sucesso (200 OK) ---
    if resp.status_code == 200:
        st.success('✅ Dados enviados com sucesso!')
        with st.spinner("Aguardando...", show_time=True):
            resp = requests.get(f'{API_URL}comandos_api/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
            if resp.status_code == 200:
                st.success("Carteira atualizada com sucesso!")
                # Recarregar dados da carteira    
            else:
                st.error(f"Erro ao atualizar carteira: Status {resp.status_code}")                    
                                
    # --- Tratamento de Erro de Validação (422 Unprocessable Entity) ---
    elif resp.status_code == 422:
        st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')
                            
        detail = resposta_json.get('detail', {})
        linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
        
        if linhas_rejeitadas:
            st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
            df_erros = pd.DataFrame(linhas_rejeitadas)

            st.dataframe(df_erros, width='content',
                            column_config={"msg": st.column_config.ListColumn(width='large'),
                                        "data_operacao": st.column_config.DateColumn(format="DD.MM.YYYY")})
        else:
            st.text(f"Detalhe de erro da API: {detail}")

    else:
        st.error(f"⚠️ Erro HTTP inesperado: Status {resp.status_code}")

# Enviar dados para o banco de dados
@st.dialog("Enviando Dados", on_dismiss='rerun')
def envia_manual(ordem_manual):
    if st.session_state.get('is_disabled', True):
        st.warning('Está faltando dados')
    else:
        st.session_state['carteira_api'] = None
        st.session_state['operacao_api'] = None

        ordem_manual = dumps(ordem_manual)
        resp = requests.post(f'{API_URL}ordem_input/inserir_ordem', ordem_manual, headers={'Authorization':f'Bearer {st.session_state.token}'})
        try:
            resposta_json = resp.json()
        except:
            st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
        if resp.status_code == 200:
            st.success('Dados enviados')
            with st.spinner("Aguardando...", show_time=True):
                resp = requests.get(f'{API_URL}comandos_api/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
                if resp.status_code == 200:
                    st.success("Carteira atualizada com sucesso!")
                    # Recarregar dados da carteira
                else:
                    st.error(f"Erro ao atualizar carteira: Status {resp.status_code}")  
        # --- Tratamento de Erro de Validação (422 Unprocessable Entity) ---
        elif resp.status_code == 422:
            st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')
                                
            detail = resposta_json.get('detail', {})
            linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
            
            if linhas_rejeitadas:
                st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
                df_erros = pd.DataFrame(linhas_rejeitadas)

                st.dataframe(df_erros, width='content',
                                column_config={"msg": st.column_config.ListColumn(width='large'),
                                            "data_operacao": st.column_config.DateColumn(format="DD.MM.YYYY")})
            else:
                st.text(f"Detalhe de erro da API: {detail}")

# Pegar lista de ativos
def get_ativos():
    st.session_state['lista'] = requests.get(f'{API_URL}Ativos/lista_ativos/{st.session_state['sl_cat']}?ativo={st.session_state['sl_ativo']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

# Excluir operação
@st.dialog("Enviando Dados", on_dismiss='rerun')
def excluir_op():
    st.session_state['carteira_api'] = None
    st.session_state['operacao_api'] = None

    try:
        lista_excluir = dumps(st.session_state['sl_op_excluir'])
        resp = requests.delete(f'{API_URL}ordem_input/delete_ordem/', data=lista_excluir, headers={'Authorization':f'Bearer {st.session_state.token}'})
        if resp.status_code == 200:
            st.success('Dados Excluidos')
            with st.spinner("Aguardando...", show_time=True):
                resp = requests.get(f'{API_URL}comandos_api/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
                if resp.status_code == 200:
                    st.success("Carteira atualizada com sucesso!")
                else:
                    st.error(f"Erro ao atualizar carteira: Status {resp.status_code}") 
        else:
            st.error(f'Erro ao enviar, Erro: {resp.jons()}')
    except:
            st.error(f'Erro ao excluir, operção : {lista_excluir}')

#Excluir todas as operações
@st.dialog("Enviando Dados", on_dismiss='rerun')
def excluir_tudo():
    st.session_state['carteira_api'] = None
    st.session_state['operacao_api'] = None

    try:
        resp = requests.delete(f'{API_URL}ordem_input/delete_all/', headers={'Authorization':f'Bearer {st.session_state.token}'})
        if resp.status_code == 200:
            st.success('Dados Excluidos')
            with st.spinner("Aguardando...", show_time=True):
                resp = requests.get(f'{API_URL}comandos_api/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
                if resp.status_code == 200:
                    st.success("Carteira atualizada com sucesso!")
                else:
                    st.error(f"Erro ao atualizar carteira: Status {resp.status_code}") 
        else:
            st.success(f'Erro ao enviar, Erro: {resp}')
    except TypeError as e:
        st.error(f'Erro ao excluir, {e}') 


#------------------------------
# Iniciar session
#-------------------------------
if 'operacao_api' not in st.session_state or st.session_state['operacao_api'] is None:    
    get_operacoes(st.session_state.token) 
#----------------------------------
# Layout
#----------------------------------
# Titulo da pagina
st.title('Ordens de Operações')

# Criar abas
tab1, tab2, tab3, tab4 = st.tabs(["Operações", "Inserir via tabela", "Inserir Manualmente", "Excluir"])

#-------------------------------------------------------------------------------------------------------------
#     Lista de operações
#-------------------------------------------------------------------------------------------------------------
with tab1:
    #Declarar Variáveis
    ordens = st.session_state.get('operacao_api', [])
    if not ordens:
        st.info('Nenhum ordem cadastrada')
    else:  
        df_ordens = pd.DataFrame(ordens)
 
        st.header("Operações")    
        st.dataframe(df_ordens,hide_index=True)
#-------------------------------------------------------------------------------------------------------------
#     Inserir dados via tabela
#-------------------------------------------------------------------------------------------------------------    
with tab2:
    st.header("Inserir via tabela")
    with open("Operacao.xlsx", "rb") as file:
        st.download_button( label="Download .xlsx tabelas padrão",
                            data=file,
                            file_name="Operacao.xlsx",
                            icon=":material/download:",
                            )
    uploaded_file  = st.file_uploader('Excolha o arquico com as operações')
    if uploaded_file  is not None:        
        dataframe = pd.read_excel(uploaded_file)
        
        titulo_padrao = ['data_operacao', 'categoria', 'codigo_ativo', 'c_v', 'quant', 'custo_operacao', 'corretora', 'taxas']
        titulo = dataframe.columns.tolist()

        if not titulo_padrao == titulo:
            st.warning('Colunas fora do padrão')
        else:
            with st.expander('Exibir Dados input'):
                st.dataframe(dataframe, width='content')

            st.button('Enviar', key='bt_1', kwargs={'dataframe': dataframe}, on_click=enviar_tabela)            
#-------------------------------------------------------------------------------------------------------------
#     Inserir dados manual
#-------------------------------------------------------------------------------------------------------------
with tab3:
    with st.container():
        
        if 'sl_cat' not in st.session_state:
            st.session_state['sl_cat'] = 'AÇÕES'
        if 'sl_ativo' not in st.session_state:
            st.session_state['sl_ativo'] = ""
        if 'lista' not in st.session_state:
            st.session_state['lista'] = requests.get(f'{API_URL}Ativos/lista_ativos/{st.session_state['sl_cat']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
    
                
        st.subheader('Dados da Operação')
        col1, col2 = st.columns(2)
        with col1:
            input_data = st.date_input('Data: ', format='DD/MM/YYYY', min_value=date(2000, 1, 1), max_value=datetime.today())
            input_qt = st.number_input('Quantidade:', format='%f',step=0.000001, min_value=0.000001, value=None)
            input_Valor = st.number_input('Valor total da operação (Incluso as taxas):', format='%f',step=0.01, min_value=0.01, value=None, help='Valor total gasto, incluindo taxas')
            input_taxa = st.number_input('Taxas (Opcional):', value=0.00, format='%f',step=0.01, min_value=0.00, help='Essa taxa não impacta calculo da planilha, valor já incluso no valot total')
        with col2:            
            input_Cat = st.selectbox('Tipo:',['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)
            st.text_input("Pesquisa ativo", label_visibility='collapsed', placeholder="Pesquisa ativo", key='sl_ativo', on_change=get_ativos)
            input_Ativo = st.pills('Ativo:', options=st.session_state['lista'], label_visibility='collapsed', selection_mode="single")
            input_C_V = st.radio('Compra ou Venda:',['Compra', 'Venda'],label_visibility='collapsed', horizontal=True)
            if input_C_V == 'Compra':
                input_C_V = 'C'
            else:
                input_C_V = 'V'
            input_Corretora = st.text_input('Corretora:')           
        
        #Datos a serem enviado
        ordem_manual = {
            "data_operacao": f'{input_data}',
            "categoria": input_Cat,
            "codigo_ativo": input_Ativo,
            "c_v": input_C_V,
            "quant": input_qt,
            "custo_operacao": input_Valor,
            "taxas": input_taxa,
            "corretora": input_Corretora
            }
        is_valid_input = bool(input_data and input_Cat and input_Ativo and input_C_V and input_qt and input_Valor)
        st.session_state['is_disabled'] = not is_valid_input
        if is_valid_input: # Se os dados necessários estão presentes, o botão deve ser visível            
            st.button('Enviar', on_click=envia_manual, kwargs={'ordem_manual': ordem_manual}, disabled=st.session_state.get('is_disabled', True))
#-------------------------------------------------------------------------------------------------------------
#     Excluir operações
#-------------------------------------------------------------------------------------------------------------
with tab4:
    if ordens:  
        st.header("Selecione as operações a ser excluida")
        if 'sl_op_excluir' not in st.session_state:
            st.session_state['sl_op_excluir'] = []
        if 'bt_on' not in st.session_state:
            st.session_state['bt_on'] = True
                
        st.header('Operações existentes')
        sl_df_op_exclui = st.dataframe(df_ordens, hide_index=True, width='content', on_select="rerun", selection_mode='multi-row')
            
        st.header('Lista para excluir')
        df_select = df_ordens.iloc[sl_df_op_exclui.get('selection').get('rows')] # type: ignore
        st.dataframe(df_select, hide_index=True) 
        st.session_state['sl_op_excluir'] = df_ordens.iloc[sl_df_op_exclui.get('selection').get('rows')]['id'].values.tolist()

        if len(df_select) != 0:
            st.session_state['bt_on'] = False
        else:
            st.session_state['bt_on'] = True
            
        col1, col2 = st.columns([1, 0.3])
        with col1:
            st.button('Excluir', key='bt_3', disabled=st.session_state['bt_on'], on_click=excluir_op)
        with col2:
            st.button('Excluir tudo', key='bt_4', on_click=excluir_tudo)
    else:
        st.write('Nenhum ordem cadastrada')
















