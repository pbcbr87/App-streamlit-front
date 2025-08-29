import streamlit as st
import pandas as pd
import requests
from json import loads, dumps
from datetime import datetime



# requisição de datos
def get_operacoes():
    try:
        dados_ordens = requests.get(f'https://pythonapi-production-6268.up.railway.app/ordem_input/pegar_ordens', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()    
    except:
        dados_ordens = []
        st.toast(f'Sem dados')
    return dados_ordens

# Enviar dados para o banco de dados
def enviar_tabela(dataframe):
    linhas = dataframe.to_json(orient='records', date_format='iso')
    linhas = loads(linhas)
    ordens_tabela = dumps({"dados": linhas})
    
    resp = requests.post('https://pythonapi-production-6268.up.railway.app/ordem_input/inserir_ordens_table', ordens_tabela, headers={'Authorization':f'Bearer {st.session_state.token}'})
    if resp.status_code == 200:
        st.toast('Dados enviados')
        st.toast(resp.json())
# Enviar dados para o banco de dados
def envia_manual(ordem_manual):
    ordem_manual = dumps(ordem_manual)
    try:
        resp = requests.post('https://pythonapi-production-6268.up.railway.app/ordem_input/inserir_ordem', ordem_manual, headers={'Authorization':f'Bearer {st.session_state.token}'})
        if resp.status_code == 200:
            st.toast('Dados enviados')
            st.toast(resp.json())
            st.toast(loads(ordem_manual))
        else:
            st.error(f'Erro ao enviar, Erro: {resp}')
    except TypeError as e:
        st.error(f'Erro ao enviar: {e}')

# Pegar lista de ativos
def get_ativos():
    st.session_state['lista'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/Ativos/lista_ativos/{st.session_state['sl_cat']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json() 

# Excluir operação
def excluir_op():
    for linha in st.session_state['sl_op_excluir']:
        try:
            resp = requests.delete(f'https://pythonapi-production-6268.up.railway.app/ordem_input/delete_ordem/{linha}', headers={'Authorization':f'Bearer {st.session_state.token}'})
            if resp.status_code == 200:
                st.toast('Dados Excluidos')
            else:
                st.toast(f'Erro ao enviar, Erro: {resp}')
        except:
            st.error(f'Erro ao excluir, operção : {linha}')

#Excluir todas as operações
def excluir_tudo():
    try:
        resp = requests.delete(f'https://pythonapi-production-6268.up.railway.app/ordem_input/delete_ordems/', headers={'Authorization':f'Bearer {st.session_state.token}'})
        if resp.status_code == 200:
            st.toast('Dados Excluidos')
        else:
            st.toast(f'Erro ao enviar, Erro: {resp}')
    except TypeError as e:
        st.error(f'Erro ao excluir, {e}') 
    

#Declarar Variáveis
ordens = get_operacoes()
if len(ordens) == 0:
    st.title('Planilha vazia')
    
df_ordens = pd.DataFrame(ordens)

# Titulo da pagina
st.title('Ordens de Operações')

# Criar abas
tab1, tab2, tab3, tab4 = st.tabs(["Operações", "Inserir via tabela", "Inserir Manualmente", "Excluir"])

#-------------------------------------------------------------------------------------------------------------
#     Lista de operações
#-------------------------------------------------------------------------------------------------------------
with tab1:
    if len(ordens) != 0:    
        st.header("Operações")    
        st.dataframe(df_ordens,hide_index=True)
    else:
        st.write('Nenhum ordem cadastrada')
#-------------------------------------------------------------------------------------------------------------
#     Inserir dados via tabela
#-------------------------------------------------------------------------------------------------------------    
with tab2:
    st.header("Inserir via tabela")
    
    uploaded_file  = st.file_uploader('Excolha o arquico com as operações')
    if uploaded_file  is not None:        
        dataframe = pd.read_excel(uploaded_file)
        st.write(dataframe.keys)
        st.button('Enviar', key='bt_1', on_click=enviar_tabela, kwargs={'dataframe': dataframe})

        with st.expander('Exibir Dados input'):
            st.dataframe(dataframe, use_container_width=True)
#-------------------------------------------------------------------------------------------------------------
#     Inserir dados manual
#-------------------------------------------------------------------------------------------------------------
with tab3:
    with st.container():
        
        if 'sl_cat' not in st.session_state:
            st.session_state['sl_cat'] = 'AÇÕES'
        if 'lista' not in st.session_state:
            lista = requests.get(f'https://pythonapi-production-6268.up.railway.app/Ativos/lista_ativos/{st.session_state['sl_cat']}', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()
        else:
            lista = st.session_state['lista']       
        
        
        st.subheader('Dados da Operação')
        col1, col2 = st.columns(2)
        with col1:
            input_data = st.date_input('Data: ', format='DD/MM/YYYY',max_value=datetime.today())
            input_Cat = st.selectbox('Tipo:',['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], key='sl_cat', on_change=get_ativos)
            input_qt = st.number_input('Quantidade:', format='%f',step=0.000001, min_value=0.000001, value=1.0)
            input_taxa = st.number_input('Taxas (Opcional):', value=0.00, format='%f',step=0.01, min_value=0.00, help='Essa taxa não impacta calculo da planilha, valor já incluso no valot total')
        with col2:
            input_C_V = st.radio('Compra ou Venda: ',['Compra', 'Venda'], horizontal=True)
            if input_C_V == 'Compra':
                input_C_V = 'C'
            else:
                input_C_V = 'V'
            input_Ativo = st.selectbox('Ativo:', lista)
            input_Valor = st.number_input('Valor total da operção (Incluso as taxas):', format='%f',step=0.01, min_value=0.01, help='Valor total gasto, incluindo taxas')
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
        st.button('Enviar', key='bt_2', on_click= envia_manual, kwargs={'ordem_manual': ordem_manual})
#-------------------------------------------------------------------------------------------------------------
#     Excluir operações
#-------------------------------------------------------------------------------------------------------------
with tab4:
    if len(ordens) != 0:  
        st.header("Selecione as operações a ser excluida")
        if 'sl_op_excluir' not in st.session_state:
            st.session_state['sl_op_excluir'] = []
        if 'bt_on' not in st.session_state:
            st.session_state['bt_on'] = True
                
        st.header('Operações existentes')
        sl_df_op_exclui = st.dataframe(df_ordens, hide_index=True, use_container_width=True, on_select="rerun", selection_mode='multi-row')
            
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