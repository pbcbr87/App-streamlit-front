import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from datetime import datetime
from json import dumps, loads
from datetime import date, datetime


def st_number_input_custom(label, value=None, key=None, placeholder="0,00"):
    def converter_valor_br(texto):
        if not texto:
            return 0.0
        try:
            # Remove pontos de milhar e troca a vírgula decimal por ponto
            limpo = texto.replace(".", "").replace(",", ".")
            return float(limpo)
        except ValueError:
            return None
    
    entrada = st.text_input(label, value=value, placeholder=placeholder, key=key)
    valor_numerico = converter_valor_br(entrada)
    if entrada and valor_numerico is None:
        st.warning("Use o formato 0,00")
        return None
    return valor_numerico

def carregar_dividendos():
    headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
    resp = requests.get(f'{API_URL}dividendos_usuarios/pegar_dividendos', headers=headers)
    if resp.status_code == 200:
        st.session_state['dividendos_usuarios_api'] = resp.json()
    else:
        st.session_state['dividendos_usuarios_api'] = []

@st.dialog("Edit Dividendos", width='medium', on_dismiss=carregar_dividendos)
def set_aceito(status, id):
    dados = {
        'aceito': status
    }
    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.put(f'{API_URL}dividendos_usuarios/edit_campo/{id}', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
        st.success('✅ Status atualizado com sucesso!')
    except:
        st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
        # --- Tratamento de Sucesso (200 OK) ---

    if resp.status_code != 200:
        st.error(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

@st.dialog("Edit Dividendos", width='medium', on_dismiss=carregar_dividendos)
def edit_dividendo(dados): 
    # dados = st.session_state['dividendos_usuarios_dict']
    id_div = dados.get('id', None)

    st.dataframe([dados], width='content' )
    dados_json = dumps(dados, ensure_ascii=False)
    if st.button('Enviar Edição'):

        resp = requests.put(f'{API_URL}dividendos_usuarios/edit_dividendo/{id_div}', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
        try:
            resposta_json = resp.json()
        except:
            st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
    
            # --- Tratamento de Sucesso (200 OK) ---
        if resp.status_code == 200:
            st.success('✅ Dados enviados com sucesso!')          
        # --- Tratamento de Erro de Validação (422 Unprocessable Entity) ---
        elif resp.status_code == 422:
            st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')  
            detail = resposta_json.get('detail', {})
            if type(detail) is list:
                st.warning(f"Validação de dados schemas: {resposta_json}")
            else:
                linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
                
                if linhas_rejeitadas:
                    st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
                    df_erros = pd.DataFrame(linhas_rejeitadas)
                    st.dataframe(df_erros)
                else:
                    st.text(f"Detalhe de erro da API: {detail}")
        else:
            st.error(f"⚠️ Erro HTTP inesperado: Status {resp.status_code}")

def excluir(selecao):
    dados = selecao

    id_div = dados.get('id', '')
    resp = requests.delete(f'{API_URL}dividendos_usuarios/delete/{id_div}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        pass

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def formatar_data(valor):
    """Converte string do banco para objeto date do Python"""
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except:
        return None

@st.dialog("Inserir Dividendos", width='medium',on_dismiss=carregar_dividendos)
def inserir_dividendo(dados_dict):
    st.header("Novo Dividendo")
    # dados_dict = st.session_state['dividendos_usuarios_dict']
    if 'id' in dados_dict.keys():
        dados_dict.pop("id")
    dados = pd.DataFrame([dados_dict])
    st.dataframe(dados, width='content', hide_index=True)
    if st.button('Enviar'):
        with st.spinner(text="In progress..."):
            enviar_tabela(dados)

def enviar_tabela(dataframe):
    linhas = dataframe.to_json(orient='records', date_format='iso')
    linhas = loads(linhas)
    tabela = dumps({"dados": linhas})
    resp = requests.post(f'{API_URL}dividendos_usuarios/inserir_dividendos_tabela', tabela, headers={'Authorization':f'Bearer {st.session_state.token}'})
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

@st.dialog("Inserir Excel", width='medium',on_dismiss=carregar_dividendos)        
def carregar_tabela():
    uploaded_file  = st.file_uploader('Excolha o arquico com as operações')
    if uploaded_file  is not None:        
        dataframe = pd.read_excel(uploaded_file)
        
        titulo_padrao = ['fk_ativo', 'tipo', 'valor_bruto', 'valor_liq', 'data_aprov', 'data_com', 'data_pag']
        titulo = dataframe.columns.tolist()

        if not titulo_padrao == titulo:
            st.warning('Colunas fora do padrão')
        else:
            with st.expander('Exibir Dados input'):
                st.dataframe(dataframe, width='content')

            if st.button('Enviar'):
                with st.spinner(text="In progress..."):
                    enviar_tabela(dataframe)

def filtro(df):
    with st.container(border=True, horizontal=True):
        sl_fk_ativo = st.text_input("Filtrar por Ativo Original", width=200)
        
        sl = st.pills('Slecione',options=['DIVIDENDO', 'JCP', 'REND. TRIBUTADO', 'RENDIMENTO', 'RENDIMENTO EXT', 'AMORTIZAÇÃO', 'AGENCY PROC. FEE'],  selection_mode="multi", width='stretch')
        df_filtrado = df[df['tipo'].isin(sl)] if sl else df

        if sl_fk_ativo:       
            df_filtrado = df_filtrado[df_filtrado['fk_ativo'].str.contains(sl_fk_ativo.upper())]
    return df_filtrado

@st.fragment
def form_dividendo(dividendo_dict):
    for key in dividendo_dict:
        dividendo_dict[key] = dividendo_dict.get(key) if dividendo_dict.get(key) else ""
    
    st.session_state['dividendos_usuarios_dict'] = {}
    st.session_state['dividendos_usuarios_dict']['id'] = dividendo_dict.get('id', None)

    form_1, form_2, form_3, form_4, form_5, form_6, form_7 = st.columns(7)
    st.session_state['dividendos_usuarios_dict']['fk_ativo'] = form_1.text_input("Ativo Categoria", value=dividendo_dict.get('fk_ativo', "")).upper()
    # Validação do index do selectbox
    tipo_list = ['DIVIDENDO', 'JCP', 'REND. TRIBUTADO', 'RENDIMENTO', 'RENDIMENTO EXT', 'AMORTIZAÇÃO','AGENCY PROC. FEE']
    try:
        idx_tipo = tipo_list.index(dividendo_dict.get('tipo'))
    except:
        idx_tipo = 0
        
    st.session_state['dividendos_usuarios_dict']['tipo'] = form_2.selectbox("Tipo", options=tipo_list, index=idx_tipo).upper() 
    
    with form_3:
        st.session_state['dividendos_usuarios_dict'][valor_bruto_col] = st_number_input_custom(f"Valor Bruto {moeda_simbolo}", 
                                                                                               value=dividendo_dict.get(valor_bruto_col, None))     
    with form_4:
        st.session_state['dividendos_usuarios_dict'][imposto_col] = st_number_input_custom(f"Imposto {moeda_simbolo}", 
                                                                                               value=dividendo_dict.get(imposto_col, None))
    # entrada = form_3.text_input(f"Valor Bruto {moeda_simbolo}", value=dividendo_dict.get(valor_bruto_col, None), placeholder="0,00")
    # valor_numerico = converter_valor_br(entrada)
    # if entrada and valor_numerico == None:
    #     st.session_state['dividendos_usuarios_dict'][valor_bruto_col] = None         
    #     form_3.warning("Inválido (0,00)")
    # else:
    #     st.session_state['dividendos_usuarios_dict'][valor_bruto_col] = valor_numerico
    
    # entrada = form_4.text_input(f"Imposto {moeda_simbolo}", value=dividendo_dict.get(imposto_col, None), placeholder="0,00")
    # valor_numerico = converter_valor_br(entrada)
    # if entrada and valor_numerico == None:
    #     st.session_state['dividendos_usuarios_dict'][imposto_col] = None         
    #     form_4.warning("Inválido (0,00)")
    # else:
    #     st.session_state['dividendos_usuarios_dict'][imposto_col] = valor_numerico

    data_aprov = form_5.date_input("data_aprov", key="data_aprov", min_value=date(2000, 1, 1), value=None)
    st.session_state['dividendos_usuarios_dict']['data_aprov'] = data_aprov.isoformat() if data_aprov else None
    
    data_com = form_6.date_input("data_com", key="data_com", min_value=date(2000, 1, 1), value=None)
    st.session_state['dividendos_usuarios_dict']['data_com'] = data_com.isoformat() if data_com else None

    data_pag = form_7.date_input("data_pag", key="data_pag", min_value=date(2000, 1, 1), value=None)
    st.session_state['dividendos_usuarios_dict']['data_pag'] = data_pag.isoformat() if data_pag else None

#--------------------------------------------------------
if 'dividendos_usuarios_api' not in st.session_state or st.session_state['dividendos_usuarios_api'] is None:
   carregar_dividendos()

if 'dividendos_usuarios_dict' not in st.session_state:
   st.session_state['dividendos_usuarios_dict'] = {}

#--------------------------------------------------------
c1_t, _, c2_t = st.columns([6,4,2])
c1_t.title("💰 Dividendos Cadastrados")
moeda = c2_t.radio('Moeda dos valores', ['BRL', 'USD'], key='moeda_valores', horizontal=True, on_change=lambda: st.session_state['dividendos_usuarios_dict'].update({}))
layout_form_dividendo = st.container(border=True)
c1, c2, c3, c4, c5 = layout_form_dividendo.columns(5)  

if c1.button("➕ Inserir Dividendo", width="stretch"):
    inserir_dividendo(st.session_state['dividendos_usuarios_dict'])

if c5.button("📥 Inserir tabela", width="stretch"):
    carregar_tabela()


linha_selecionada = {}
if 'dividendos_usuarios_api' not in st.session_state or not st.session_state.dividendos_usuarios_api:
    st.info("💡 Nenhum Dividendos Encontrado no Banco de dados.")
else:
    #------------------------------------------------------------------
    # Tabela de Dividendos Cadastrados
    #------------------------------------------------------------------
    colunas = ['id', 'fk_usuario', 'fk_dividendo', 'fk_evento_usuario', 'fk_ativo', 'tipo', 
               'valor_bruto_brl','imposto_brl', 'valor_liq_usd', 'valor_bruto_usd','imposto_usd', 'valor_liq_brl',
               'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert', 'aceito']
    if moeda == 'BRL':
        colunas_view = ['aceito', 'fk_ativo', 'tipo', 'valor_bruto_brl','imposto_brl', 'valor_liq_brl', 'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert']
        valor_bruto_col = 'valor_bruto_brl'
        valor_liq_col = 'valor_liq_brl'
        imposto_col = 'imposto_brl'
        moeda_simbolo = 'R$'
    else:
        colunas_view = ['aceito', 'fk_ativo', 'tipo', 'valor_bruto_usd','imposto_usd', 'valor_liq_usd', 'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert']
        valor_bruto_col = 'valor_bruto_usd'
        valor_liq_col = 'valor_liq_usd'
        imposto_col = 'imposto_usd'
        moeda_simbolo = 'US$'

    df = pd.DataFrame(st.session_state.dividendos_usuarios_api).sort_values(by='data_aprov', ascending=False)
    df = filtro(df)
    st.write("Selecione uma linha para editar ou visualizar detalhes:")
    
    df_display = df[colunas].copy()
    df_display['aceito'] = df_display['aceito'].apply(lambda x: "✔️" if x else "⚪")

    dividendo_sl = st.dataframe(
                            df_display, width="stretch", height=200, hide_index=True,
                                on_select="rerun",
                                selection_mode="single-row",                            
                                column_order=colunas_view,
                                column_config={
                                    'aceito': st.column_config.Column("On/Off", width="small"),
                                    valor_bruto_col: st.column_config.NumberColumn(f"Valor Bruto {moeda_simbolo}", help='Moeda do ativo', format="%.2f"),
                                    imposto_col: st.column_config.NumberColumn(f"Imposto {moeda_simbolo}", help='Moeda do ativo', format="%.2f"),
                                    valor_liq_col: st.column_config.NumberColumn(f"Valor Liquido {moeda_simbolo}", help='Moeda do ativo', format="%.2f"),
                                    'data_aprov': st.column_config.DateColumn("Data de Aprovação"),
                                    'data_com': st.column_config.DateColumn("Data Com"),
                                    'data_pag': st.column_config.DateColumn("Data Pagamento")
                                    }
                                )

    #------------------------------------------------------------------
    # Capturar a seleção
    #------------------------------------------------------------------
    selecao = dividendo_sl.selection.get("rows", [])

    if selecao:
        idx = selecao[0]
        linha_selecionada = df.iloc[idx].to_dict()    
        
        if c2.button("✏️ Editar Dividendo", width="stretch"):
            edit_dividendo(st.session_state['dividendos_usuarios_dict'])

        if c3.button("🗑️ Excluir Dividendo", width="stretch"):
            excluir(linha_selecionada)
            st.session_state.dividendos_usuarios_api = None
            st.rerun()

        if linha_selecionada['aceito']:
            if c4.button("[OFF⚪] Desligar", width="stretch"):
                set_aceito(False, linha_selecionada['id'])                
        else:
            if c4.button("[✔️ON] Ligar", width="stretch"):
                set_aceito(True, linha_selecionada['id'])                

    else:
        st.info("💡 Clique em uma linha da tabela acima para habilitar as ações.")

    with layout_form_dividendo:
        if 'data_aprov' in st.session_state:
            st.session_state.data_aprov = formatar_data(linha_selecionada.get('data_aprov', None))
        if 'data_com' in st.session_state:
            st.session_state.data_com = formatar_data(linha_selecionada.get('data_com', None))
        if 'data_pag' in st.session_state:
            st.session_state.data_pag = formatar_data(linha_selecionada.get('data_pag', None))
        if valor_bruto_col in linha_selecionada:
            linha_selecionada[valor_bruto_col] = "{:,.2f}".format(float(linha_selecionada.get(valor_bruto_col))).replace(',', 'v').replace('.', ',').replace('v', '.')
        if imposto_col in linha_selecionada:
            linha_selecionada[imposto_col] = "{:,.2f}".format(float(linha_selecionada.get(imposto_col))).replace(',', 'v').replace('.', ',').replace('v', '.')
        # if valor_liq_col in linha_selecionada:
        #     linha_selecionada[valor_liq_col] =  "{:,.2f}".format(float(linha_selecionada.get(valor_liq_col))).replace(',', 'v').replace('.', ',').replace('v', '.')

        form_dividendo(linha_selecionada)

