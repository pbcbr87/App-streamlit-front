import streamlit as st
import requests
import pandas as pd
from json import dumps, loads
import time
from settings import API_URL

# Configuração da URL da API
# API_URL = 'https://pythonapi-production-6268.up.railway.app/'
# API_URL = 'http://localhost:8000/'
# API_URL = 'python_api.railway.internal'
token = st.session_state.get('token')

if 'lista_criada' not in st.session_state:
    st.session_state['lista_criada'] = None

def simular_evento(evento, operacao_param, posicao):
    resp = requests.get(f'{API_URL}eventos/simular_evento/?ev_json={evento}&posicao={posicao}&operacao_param={operacao_param}', headers={'Authorization':f'Bearer {token}'})   
    try:
        resposta_json = resp.json()
    except:
        st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")

    if resp.status_code == 404:
        st.toast(f'ℹ️ Eventos vazias: {resp.text}.')       
        return []

    if resp.status_code == 422:
        st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')
                            
        detail = resposta_json.get('detail', {})
        linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
        
        if linhas_rejeitadas:
            st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
            st.text(f'{type(linhas_rejeitadas)}, {linhas_rejeitadas}')
            df_erros = pd.DataFrame(linhas_rejeitadas)

            st.dataframe(df_erros, width='content',
                            column_config={"msg": st.column_config.ListColumn(width='large'),
                                        "data_operacao": st.column_config.DateColumn(format="DD.MM.YYYY")})
        else:
            st.text(f"Detalhe de erro da API: {detail}")

        return []
    if resp.status_code != 200:
        st.toast(f"🚨 Erro ao carregar Eventos: Status {resp.status_code}")        
        return []
    
    resp = resp.json()
    if not isinstance(resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.toast(f"🚨 Formato da API inesperado. Recebido tipo: {type(resp)}")
        return []    
    
    return resp

def get_evento(token):
    resp = requests.get(f'{API_URL}eventos/pesquisa/{st.session_state.get("sl_ativo", "")}', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code == 404:       
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
    id_ativo = None
    ativo_gerado = None
    proporcao = None
    valor = None
    dinheiro = None
    grupamento = None
    desdobramento = None
    pro_ativo = None
    pro_gerado = None
    valor_gerado = None
    operacao = None
    str_dinheiro = '(0.56 * qt) - 0.2 * (qt * 8.76 - custo) if  (qt * 8.76 - custo) > 0 else 0.56 * qt'

    tipo_list = ['ATUALIZAÇÃO',
                'BONIFICAÇÃO',
                'CISÃO',
                'DESDOBRAMENTO',
                'FRAÇÃO',
                'GRUPAMENTO',
                'GRUPAMENTO_DESDOBRAMENTO',
                'INCORPORAÇÃO',
                'OPA',
                'REDUÇÃO DE CAPITAL']


    st.header('Valor em carteira para teste')
    with st.container(horizontal=True):
        quant_acum = st.number_input("Quantidade de Cotas (qt)", format="%.5f")
        custo_acum = st.number_input("Valor acumulado (custo)", format="%.5f")

    st.header('Evento')
    with st.container(horizontal=True):
        
        tipo = st.selectbox('Tipo', tipo_list)
        
        data_aprov = st.date_input('Data de aprovação', format='DD/MM/YYYY')
        data_com = st.date_input('Data de com direito', format='DD/MM/YYYY')
        data_pag = st.date_input('Data de pagamento', format='DD/MM/YYYY')
    
    
    if tipo == 'BONIFICAÇÃO':           
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            ativo_gerado = id_ativo
            valor = st.number_input("Valor por cota", format="%.5f")
            proporcao = st.number_input("Proporção", format="%.5f")
    
    if tipo == 'FRAÇÃO':
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            valor = st.number_input("Valor por cota", format="%.5f")

    if tipo == 'DESDOBRAMENTO':        
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            proporcao = st.number_input("Proporção", format="%.5f")

    if tipo == 'GRUPAMENTO':        
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            proporcao = st.number_input("Proporção", format="%.5f")

    if tipo == 'GRUPAMENTO_DESDOBRAMENTO':        
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            grupamento = st.number_input("Proporção Grupamento", format="%.5f")
            desdobramento = st.number_input("Proporção Desdobramento", format="%.5f")

    if tipo == 'ATUALIZAÇÃO':
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            ativo_gerado = st.text_input("id do novo ativo", max_chars=20)
            proporcao = st.number_input("Proporção", format="%.5f")

    if tipo == 'OPA':
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            valor = st.number_input("Valor por cota da venda", format="%.5f")

    if tipo == 'REDUÇÃO DE CAPITAL':
        with st.container(horizontal=True):
            id_ativo = st.text_input("id_ativo", max_chars=20)
            valor = st.number_input("Valor em dinheiro receido por cota", format="%.5f")

    if tipo == 'CISÃO':
        str_dinheiro = "(0.85 * qt) - 0.2 * (qt * 8.59 - 0.0938 * custo) if (qt * 8.59 - 0.0938 * custo) > 0 else 0.85 * qt"
        if st.toggle('Usar formula'):
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                ativo_gerado = st.text_input("id do novo ativo", max_chars=20)                
            operacao = st.text_area('Usar formula pra operação', height=100, value='[{"id_ativo": "MMM_STOCK", "custo": "-custo * 0.1552", "qt": "0"}, {"id_ativo": "SOLV_STOCK", "custo": "custo * 0.1552", "qt": "qt *0.25"}]')
            try:
                operacao = loads(operacao)
            except:
                st.error('Erro na formula')
        else:
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                ativo_gerado = st.text_input("id do novo ativo", max_chars=20)
                proporcao = st.number_input("Proporção de quant novo ativo", format="%.5f")
                pro_ativo = st.number_input("Proporção reduzir ativo original", format="%.5f")
                if st.toggle("Valor"):
                    valor_gerado = st.number_input("Valor por cota novo ativo", format="%.5f")
                else:
                    pro_gerado = st.number_input("Proporção que para o novo ativo", format="%.5f")
    
    if tipo ==  'INCORPORAÇÃO':
        str_dinheiro = "(0.56 * qt) - 0.2 * (qt * 8.76 - custo) if  (qt * 8.76 - custo) > 0 else 0.56 * qt"
        if st.toggle('Usar formula'):
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                ativo_gerado = st.text_input("id do novo ativo", max_chars=20)                
            operacao = st.text_area('Usar formula pra operação', height=100, value='[{"id_ativo": "RENT3_AÇÕES", "custo": "custo", "qt": "qt * 0.43884446"}, {"id_ativo": "LCAM3_AÇÕES", "custo": "custo", "qt": "-qt"}]')
            try:
                operacao = loads(operacao)
            except:
                st.error('Erro na formula')
        else:
            with st.container(horizontal=True):
                id_ativo = st.text_input("id_ativo", max_chars=20)
                ativo_gerado = st.text_input("id do novo ativo", max_chars=20)
                proporcao = st.number_input("Proporção de quant novo ativo", format="%.5f")
                if st.toggle("Valor"):
                    valor_gerado = st.number_input("Valor por cota ativo novo", format="%.5f")
        

    if st.toggle('Dinheiro com formula'):
        dinheiro = st.text_area('Formula dinheiro', height=100, value=str_dinheiro)
    #---------------------------------------------- 
    if quant_acum > 0 and custo_acum > 0:
        submitted_detalhes = st.button("Simular", type="primary")
    
        if submitted_detalhes:
            # Mostrar previa do calculo
            operacao_param_dict = {
                            "id_ativo": id_ativo,
                            "ativo_gerado": ativo_gerado,
                            "proporcao": proporcao,
                            "valor": valor,
                            "grupamento": grupamento,
                            "desdobramento": desdobramento,
                            "pro_ativo": pro_ativo,
                            "pro_gerado": pro_gerado,
                            "valor_gerado": valor_gerado,
                            "operacao": operacao
                            }
            
            evento_dict = {
                    'fk_ativo':  id_ativo,
                    'ativo_gerado': ativo_gerado,
                    'tipo': tipo,
                    'data_aprov': data_aprov.isoformat(),
                    'data_com': data_com.isoformat(),
                    'data_pag': data_pag.isoformat(),
                    'valor_base': valor,
                    'proporcao': proporcao,
                    'dinheiro': dinheiro,
                    'operacao': None
                    }
            
            posicao_dict = {
                        'qt': f"{quant_acum}",
                        'custo': f"{custo_acum}"
                        }
            
            posicao = dumps(posicao_dict, ensure_ascii=False)
            evento = dumps(evento_dict, ensure_ascii=False)
            operacao_param = dumps(operacao_param_dict, ensure_ascii=False)
            with st.spinner('Simulando evento...'):
                resp = simular_evento(evento, operacao_param, posicao)

            if not resp:
                print('stop')
                st.stop()
                
            df_ordem_cal = pd.DataFrame(resp[0])            
            if len(df_ordem_cal)<2:
                st.text('Evento não calculado.')
                st.stop()
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
                df_ordem_cal[col] = pd.to_numeric(df_ordem_cal[col], errors='coerce')

            df_ordem_cal = df_ordem_cal[['tipo', 'seq', 'fk_ativo', 'data_op_com', 
                                        'quant_', 'quant_acum', 
                                        'preco_op_brl', 'custo_acum_brl', 'lucro_brl',
                                        'preco_op_usd', 'custo_acum_usd', 'lucro_usd',
                                        'quant_fracao', 'moeda','dolar_bc']].style.format(formatos)
            
            st.dataframe(df_ordem_cal, hide_index =True, width='content' )
            st.session_state['lista_criada'] = resp[1]

        if st.session_state['lista_criada']:
            df_linha_evento = pd.DataFrame(st.session_state['lista_criada'])
            st.dataframe(df_linha_evento, hide_index =True, width='content')
            if st.button('Confirmar evento'):
                with st.spinner('Enviando dados para API...'):
                    st.text('Falta implementar o envio para API')
                    time.sleep(1)
                # enviar_tabela(df_linha_evento)

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
    st.session_state['evento_api'] = []

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