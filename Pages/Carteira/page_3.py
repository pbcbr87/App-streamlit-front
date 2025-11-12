import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
from json import loads, dumps
from decimal import Decimal


#------------------------------------------------
API_URL = 'https://pythonapi-production-6268.up.railway.app/'
#------------------------------------------------

# ==============================================================================
# 🗃️ 1. FUNÇÕES DE API (LÓGICA DE NEGÓCIO)
# ==============================================================================

def get_ativos():
    """Busca a lista de ativos disponíveis na API com base no filtro atual."""
    cat = st.session_state.get('sl_cat', 'AÇÕES')
    ativo = st.session_state.get('sl_ativo', '')
    token = st.session_state.get('token')
    
    try:
        url = f'{API_URL}Ativos/lista_ativos/{cat}?ativo={ativo}'
        resp = requests.get(url, headers={'Authorization': f'Bearer {token}'})
        
        if resp.status_code == 200:
            st.session_state['lista'] = resp.json()
        else:
            st.session_state['lista'] = []
            st.error(f'Erro ao buscar ativos: {resp.status_code}')

    except requests.exceptions.RequestException as e:
        st.error(f'Erro de conexão ao buscar ativos: {e}')
        st.session_state['lista'] = []

def envia_peso(dados: pd.DataFrame):
    """Atualiza o peso e nota dos ativos existentes na carteira."""
    token = st.session_state.get('token')
    lista_dados = []
    for _, linha in dados.iterrows():
        dado = {
            "fk_ativo": f'{linha["codigo_ativo"]}_{linha["categoria"]}',
            "peso": linha['peso'],
            "nota": linha['nota']
        }
        
        lista_dados.append(dado)


    try:
        resp = requests.put(
            f'{API_URL}carteira/update_peso_nota/{st.session_state.get("id", 0)}',
            dumps(lista_dados),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        if resp.status_code == 200:
            st.toast(f'Dados atualizado com sucesso!', icon="✅")
        else:
            st.error(f'Erro ao atualizar, Erro: {resp.text}')
    except requests.exceptions.RequestException as e:
        st.error(f'Erro de conexão ao enviar peso: {e}')
    except TypeError as e:
        st.error(f'Erro de tipo ao enviar peso: {e}')

    # Recarrega os dados da carteira após o loop
    st.session_state['carteira_api'] = requests.get(f'{API_URL}pegar_carteira/{st.session_state.get("id", 0)}', 
                                                    headers={'Authorization': f'Bearer {token}'}).json()

def envia_manual(dados: dict):
    """Insere um novo ativo manualmente na carteira."""
    token = st.session_state.get('token')
    
    try:
        resp = requests.post(
            f'{API_URL}carteira/inserir_ativo/{st.session_state.get("id", 0)}',
            dumps(dados),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        if resp.status_code == 201:
            st.toast('Ativo adicionado com sucesso!', icon="✨")
            # Recarrega a carteira
            st.session_state['carteira_api'] = requests.get(
                f'{API_URL}carteira/pegar_carteira/{st.session_state.get("id", 0)}', 
                headers={'Authorization': f'Bearer {token}'}
            ).json()
        else:
            st.error(f'Erro ao inserir ativo, Erro: {resp.status_code} - {resp.text}')
    except requests.exceptions.RequestException as e:
        st.error(f'Erro de conexão ao enviar ativo: {e}')
    except TypeError as e:
        st.error(f'Erro de tipo ao enviar ativo: {e}')

# ==============================================================================
# ⚙️ 2. FUNÇÕES DE CALLBACKS E AUXILIARES
# ==============================================================================

def sl_tudo_ex():
    """Seleciona todas as categorias no multiselect (Pills)."""
    if 'carteira_api' in st.session_state and st.session_state['carteira_api']:
        df_cat = list(pd.DataFrame(st.session_state['carteira_api'])['categoria'].unique())
        st.session_state['Key_SL_2'] = df_cat

def sl_nada_ex():
    """Desmarca todas as categorias no multiselect (Pills)."""
    st.session_state['Key_SL_2'] = []

def check_envio_manual():
    """Verifica se os campos de peso e nota estão preenchidos para liberar o botão."""
    input_peso = st.session_state.get('input_peso_manual')
    input_nota = st.session_state.get('input_nota_manual')
    
    # Verifica se ambos não são None
    if input_peso is not None and input_nota is not None:
        st.session_state['block_envio'] = False
    else:
        st.session_state['block_envio'] = True

# ==============================================================================
# 🎨 3. FUNÇÕES DE CRIAÇÃO DE GRÁFICOS
# ==============================================================================

def create_sunburst_chart(df: pd.DataFrame):
    """Cria o gráfico Sunburst com margens mínimas."""
    fig = px.sunburst(df, path=["categoria", "setor", "codigo_ativo"], values='peso', color="categoria")
    fig.update_traces(textinfo='label+percent entry')
    fig.update_layout(
        margin=dict(b=0, t=0, l=0, r=0),
        # Adiciona um pequeno padding visual no fundo (opcional)
        plot_bgcolor='rgba(0,0,0,0)' 
    )
    return fig

def create_pie_chart(df: pd.DataFrame, names_col: str, title: str):
    """Cria um gráfico Pie genérico, agrupando valores."""
    # Agrupa por coluna para consolidar as fatias
    df_grouped = df.groupby(names_col)['peso'].sum().reset_index()
    
    fig = px.pie(df_grouped, values='peso', names=names_col, title=title)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

# ==============================================================================
# 🚀 4. INICIALIZAÇÃO E LAYOUT PRINCIPAL
# ==============================================================================

# --- DECLARAÇÃO DE MEMÓRIA (st.session_state) ---
# Simulação de segurança (ajuste conforme seu app real)
if 'token' not in st.session_state or 'id' not in st.session_state:
    # Apenas para evitar crash em ambiente de teste sem login
    st.session_state['token'] = 'dummy_token' 
    st.session_state['id'] = 1 
    # st.warning("Token ou ID de usuário não encontrado na sessão. Certifique-se de estar logado.")
    # st.stop() 

# Inicializa variáveis de estado
if 'sl_cat' not in st.session_state:
    st.session_state['sl_cat'] = 'AÇÕES'
if 'sl_ativo' not in st.session_state:
    st.session_state['sl_ativo'] = ''
if 'lista' not in st.session_state:
    get_ativos()
if 'block_envio' not in st.session_state:
    st.session_state['block_envio'] = True


# --- LAYOUT DE ADIÇÃO MANUAL E FILTROS ---

cont_top_bar = st.container() # Container para a barra de botões e multiselect

with cont_top_bar:
    col_popover, col_bt_envio, col_spacer, col_pills, col_bt_tudo, col_bt_nada = st.columns([3, 1.5, 7, 4, 0.5, 0.5])

    # Popover de Adição Manual
    with col_popover.popover("➕ Adicionar Novo Ativo",width='stretch'):
        
        input_Cat = st.selectbox(
            'Tipo:', 
            ['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'], 
            key='sl_cat', 
            on_change=get_ativos, 
            index=['AÇÕES', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'].index(st.session_state['sl_cat'])
        )
        
        with st.container(border=True, height=130):
            st.text_input( "Pesquisa Ativo", label_visibility='collapsed', placeholder="Pesquisar...", key='sl_ativo', on_change=get_ativos)
            input_Ativo = st.pills('Ativo:', options=st.session_state['lista'], label_visibility='collapsed', selection_mode="single")

        if input_Ativo:
            st.divider()
            st.write(f"**Ativo selecionado:** `{input_Ativo}`")
            col_peso, col_nota = st.columns(2)
            
            with col_peso:
                input_peso = st.number_input('Peso (em %):',format='%f', step=0.01, min_value=0.01, value=None, key='input_peso_manual', on_change=check_envio_manual)
            with col_nota:
                input_nota = st.number_input( 'Nota (0 a 10):', step=1, min_value=0, max_value=10, value=None, key='input_nota_manual', on_change=check_envio_manual)
            
            dados_manual = {
                "fk_usuario": st.session_state.id,
                "fk_ativo": f'{input_Ativo}_{input_Cat}',
                "peso": input_peso,
                "nota": input_nota
            }
            
            if not st.session_state.get('block_envio', True):
                st.button('Enviar Ativo para Carteira', on_click=envia_manual, kwargs={'dados': dados_manual})

# --- LAYOUT TABELA E GRÁFICOS ---

if not st.session_state['carteira_api']:
    st.info('Carteira vazia ou não calculada. Adicione um ativo para começar.')
    st.stop()

df_carteira = pd.DataFrame(st.session_state['carteira_api'])
df_cat_unique = list(df_carteira['categoria'].unique())

if 'Key_SL_2' not in st.session_state:
    st.session_state['Key_SL_2'] = df_cat_unique # Seleciona tudo por padrão

# Filtros e botões de ação na barra superior (cont_top_bar)
with cont_top_bar:
    with col_pills:
        mult_sl_cat = st.pills('Categoria:', df_cat_unique, key='Key_SL_2', selection_mode="multi")

    with col_bt_tudo:
        st.button("", icon=':material/checklist_rtl:', type='tertiary', help='Selecionar todas as categorias', on_click=sl_tudo_ex, width='stretch')
        
    with col_bt_nada:
        st.button("", icon=':material/cancel:', type='tertiary', help='Desmarcar todas as categorias', on_click=sl_nada_ex, width='stretch')

# Aplica a máscara de filtro
mask = df_carteira['categoria'].isin(st.session_state['Key_SL_2'])
df_filtered = df_carteira[mask].copy()

# Verifica se há dados filtrados para exibir
if df_filtered.empty:
    st.warning('Nenhum dado para exibir. Selecione uma ou mais categorias acima.')
    with cont_top_bar:
            col_bt_envio.button('Enviar Pesos', disabled=True, width='stretch')
    st.stop() 


# ----------------------------------------------------
# 🌟 LAYOUT: TABELA AO LADO DO SUNBURST
# ----------------------------------------------------

col_tabela, col_sunburst = st.columns([1, 1.5])

# 1. TABELA DE EDIÇÃO (na primeira coluna)
with col_tabela:
    st.subheader("📝 Edição da Carteira")
    
    # O data_editor vai preencher a largura da coluna
    df_resp = st.data_editor(
        df_filtered, 
        column_order =("codigo_ativo", "setor", "categoria", "peso", "nota"), 
        column_config={
            "codigo_ativo": st.column_config.Column("Ativo", disabled=True),
            "setor": st.column_config.Column("Setor", disabled=True),
            "categoria": st.column_config.Column("Categoria", disabled=True),
            "peso": st.column_config.NumberColumn("Peso", format="%.2f", min_value=0.00),
            "nota": st.column_config.NumberColumn("Nota (0-10)", format="%d", min_value=0, max_value=10)
        },
        hide_index=True,
        width='stretch', 
        height=600 # Altura fixa para melhor alinhamento visual
    )

# 2. SUNBURST CHART (na segunda coluna)
with col_sunburst:
    st.subheader("Distribuição")
    fig_sunburst = create_sunburst_chart(df_resp)
    st.plotly_chart(fig_sunburst, width='stretch')

# Botão de envio dos pesos (na barra superior)
with cont_top_bar:
    # Pega as colunas modificadas (apenas peso e nota)
    df_envio = df_resp[['codigo_ativo', 'categoria', 'peso', 'nota']]
    col_bt_envio.button('Enviar Pesos', on_click=envia_peso, kwargs={'dados': df_envio}, width='stretch')

st.divider()

# ----------------------------------------------------
# GRÁFICOS PIE (abaixo das colunas principais)
# ----------------------------------------------------
st.subheader("📊 Análise Detalhada (Porcentagem de Peso)")       

st.write("##### Por Ativo")
fig_ativo = create_pie_chart(df_resp, 'codigo_ativo', '')
st.plotly_chart(fig_ativo, width='stretch')

st.write("##### Por Setor")
fig_setor = create_pie_chart(df_resp, 'setor', '')
st.plotly_chart(fig_setor, width='stretch')

st.write("##### Por Categoria")
fig_categoria = create_pie_chart(df_resp, 'categoria', '')
st.plotly_chart(fig_categoria, width='stretch')