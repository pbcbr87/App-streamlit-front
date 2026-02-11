import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from json import loads, dumps
from decimal import Decimal, DivisionByZero
from settings import API_URL

#------------------------------------------------
# API_URL = 'https://pythonapi-production-6268.up.railway.app/'
# API_URL = 'python_api.railway.internal'
#------------------------------------------------

def get_carteira_data(token: str) -> list:
    """Busca a carteira da API e converte strings numéricas para Decimal."""
    
    resp = requests.get(
        f'{API_URL}carteira/aporte_carteira/{st.session_state.get("id", 0)}', 
        headers={'Authorization':f'Bearer {token}'}
    )
    if resp.status_code == 404:
        st.error(f'Carteira vazias: {resp.text}.')
        return []
    
    if resp.status_code != 200:
        st.error(f"Erro ao carregar carteira: Status {resp.status_code}")
        return []
    
    dict_resp = resp.json()
    
    if not isinstance(dict_resp, list):
         # Lida com o erro de formato de API (visto em conversas anteriores)
         st.error(f"Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
         return []

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

    return dict_resp

def divisao_percentual_segura(row: pd.Series, coluna_numerador: str, coluna_denominador: str) -> Decimal:     
    # 1. Tenta extrair os valores (eles devem ser objetos Decimal)
    numerador = row.get(coluna_numerador)
    denominador = row.get(coluna_denominador)
    
    # Se algum valor estiver faltando ou for None, retorna 0
    if numerador is None or denominador is None:
        return Decimal('0')
    # 2. Verifica e trata a divisão por zero
    try:
        if denominador == Decimal('0'):
            return Decimal('0')
    except Exception:
        # Se o denominador não for um Decimal válido (ex: 'abc'), tratamos como 0
        return Decimal('0')
    # 3. Tenta a divisão real
    try:
        return numerador / denominador
    except DivisionByZero:
        # Linha de defesa contra o erro Decimal.
        return Decimal('0')
    except Exception:
        # Captura qualquer outro erro de operação, como tipos misturados
        return Decimal('0')


if 'carteira_api_aporte' not in st.session_state or st.session_state['carteira_api_aporte'] is None:     
    st.session_state['carteira_api_aporte'] = get_carteira_data(st.session_state.token)


st.header("Aportes")

if not st.session_state['carteira_api_aporte']:
   st.info('Carteira vazia ou não calculada. Adicione um ativo para começar.')
   st.stop()

df_carteira = pd.DataFrame(st.session_state['carteira_api_aporte'])
#-----------------------------------------------------------
#Containers layout
#-----------------------------------------------------------
sl_cat_container = st.container(border=True, horizontal=True, vertical_alignment='center')
#-----------------------------------------------------------
#Seletor
#-----------------------------------------------------------
def sl_tudo_ex():       
    st.session_state['Key_SL_2'] = df_cat
def sl_nada_ex():       
    st.session_state['Key_SL_2'] = []
        
df_cat = list(df_carteira['categoria'].unique())    
if 'Key_SL_2' not in st.session_state:
    st.session_state['Key_SL_2'] = df_cat

#multiselect
with sl_cat_container:
    mult_sl_cat = st.pills('categoria', df_cat, key='Key_SL_2', selection_mode="multi")

    st.button("",icon=':material/cancel:', type='tertiary', help='Desmarcar tudo', key='Key_BT_3', on_click=sl_nada_ex)
    st.button("",icon=':material/checklist_rtl:', type='tertiary', help='Selecionar tudo', key='Key_BT_2', on_click=sl_tudo_ex)

    op_ordem = {
                'Valor Aporte': 'dif',
                '% Dif Plan/Atual': 'dif_perc'
                }
    option = st.selectbox("Ordendar por", list(op_ordem.keys()))
    
mask = df_carteira['categoria'].isin(mult_sl_cat)
df_carteira = df_carteira[mask]
#----------------------------------------------------------------------
# Aporte
#---------------------------------------------------------------------
# Valor a ser aportado
if not df_carteira.empty:
    valor_aporte = sl_cat_container.number_input('Valor de aporte:',value=None, format="%.2f", min_value=0.00)
    if not valor_aporte:
        valor_aporte = Decimal('0')
    else:
        valor_aporte = Decimal(str(valor_aporte))
    moeda_aporte = sl_cat_container.radio('Moeda:',['BRL', 'USD'])
    # Calculo
    if moeda_aporte == "BRL":
        valor_total = df_carteira['valor_mercado_brl'].sum() + valor_aporte
    else:
        valor_total = df_carteira['valor_mercado_usd'].sum() + valor_aporte

    peso_total =  df_carteira['peso'].sum()
    if peso_total != 0:
        if moeda_aporte == "BRL":
            df_carteira['valor_plan_brl'] = df_carteira['peso']*valor_total/peso_total
        else:
            df_carteira['valor_plan_usd'] = df_carteira['peso']*valor_total/peso_total

        if moeda_aporte == "BRL":
            df_carteira['%_lucro'] =  df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='lucro_brl', coluna_denominador='custo_brl'), axis=1)
            df_carteira['dif'] =  df_carteira['valor_plan_brl'] - df_carteira['valor_mercado_brl']
            df_carteira['dif_perc'] = df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='dif', coluna_denominador='valor_mercado_brl'), axis=1)
        else:
            df_carteira['%_lucro'] =  df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='lucro_usd', coluna_denominador='custo_usd'), axis=1)
            df_carteira['dif'] =  df_carteira['valor_plan_usd'] - df_carteira['valor_mercado_usd']
            df_carteira['dif_perc'] = df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='dif', coluna_denominador='valor_mercado_usd'), axis=1)

        # quantidade de ativos
        qt_ativo_aporte = sl_cat_container.number_input('Quantos ativos', value=len(df_carteira[df_carteira['dif'] > 0]), format='%i', min_value=0, max_value=len(df_carteira))
        df_carteira = df_carteira.sort_values(op_ordem[option], ascending=[False]).head(qt_ativo_aporte)
        # df_carteira = df_carteira[df_carteira['dif'] > 0]
        soma_dif = df_carteira[df_carteira['dif'] > 0]['dif'].sum()
        if soma_dif != 0:
            df_carteira['aporte'] = np.where(df_carteira['dif']>0, df_carteira['dif'] * valor_aporte/soma_dif, 0)
        else:
            df_carteira['aporte'] = Decimal("0")

        if moeda_aporte == "BRL":
            df_carteira['aporte_per'] = df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='aporte', coluna_denominador='valor_mercado_brl'), axis=1)
        else:
            df_carteira['aporte_per'] = df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='aporte', coluna_denominador='valor_mercado_usd'), axis=1)
        # df_carteira = df_carteira[df_carteira['aporte'] > 0]

if not df_carteira.empty and peso_total != 0:
    
    if moeda_aporte == "BRL":
        colunas = ['codigo_ativo', 'aporte', 'aporte_per','soma_aporte_brl_12m', 'preco_brl', 'posicao_preco','preco_12m_min_brl', 'preco_12m_max_brl', 'PM_brl', 'min_aporte_preco_unit_brl_12m', 'max_aporte_preco_unit_brl_12m', '%_lucro', 'dif_perc', 'dy']
        df_carteira['posicao_preco'] = (df_carteira['preco_brl'] - df_carteira['preco_12m_min_brl']) / (df_carteira['preco_12m_max_brl'] - df_carteira['preco_12m_min_brl'])
        df_carteira['posicao_preco'] = df_carteira['posicao_preco'].clip(0, 1)
    else:
        colunas = ['codigo_ativo', 'aporte', 'aporte_per','soma_aporte_usd_12m', 'preco_usd', 'posicao_preco', 'preco_12m_min_usd', 'preco_12m_max_usd','PM_usd', 'min_aporte_preco_unit_usd_12m', 'max_aporte_preco_unit_usd_12m', '%_lucro', 'dif_perc', 'dy']
        df_carteira['posicao_preco'] = (df_carteira['preco_usd'] - df_carteira['preco_12m_min_usd']) / (df_carteira['preco_12m_max_usd'] - df_carteira['preco_12m_min_usd'])
        df_carteira['posicao_preco'] = df_carteira['posicao_preco'].clip(0, 1)

    if moeda_aporte == "BRL":
        df_carteira = df_carteira[colunas].style.format({
            'aporte': 'R$ {:,.2f}',
            'aporte_per': '{:,.2%}',
            '%_lucro':'{:,.2%}',
            'dif_perc': '{:,.2%}',
            'dy': '{:,.2%}',
            'soma_aporte_brl_12m': 'R$ {:,.2f}',
            'PM_brl': 'R$ {:,.2f}',
            'min_aporte_preco_unit_brl_12m': 'R$ {:,.2f}',
            'max_aporte_preco_unit_brl_12m': 'R$ {:,.2f}',
            'preco_brl': 'R$ {:,.2f}',
            'preco_12m_min_brl': 'R$ {:,.2f}',
            'preco_12m_max_brl': 'R$ {:,.2f}'
        })
    else:
        df_carteira = df_carteira[colunas].style.format({
            'aporte': 'US$ {:,.2f}',
            'aporte_per': '{:,.2%}',
            '%_lucro':'{:,.2%}',
            'dif_perc': '{:,.2%}',
            'dy': '{:,.2%}',
            'soma_aporte_usd_12m': 'US$ {:,.2f}',
            'PM_usd': 'US$ {:,.2f}',
            'min_aporte_preco_unit_usd_12m': 'US$ {:,.2f}',
            'max_aporte_preco_unit_usd_12m': 'US$ {:,.2f}',
            'preco_usd': 'US$ {:,.2f}',
            'preco_12m_min_usd': 'US$ {:,.2f}',
            'preco_12m_max_usd': 'US$ {:,.2f}'
        })

    

    st.dataframe(df_carteira, hide_index=True, width='content',
                column_config={
                                'codigo_ativo': 'Ativo',
                                "aporte": "Aporte",
                                'aporte_per': '% Aporte/Atual',
                                'soma_aporte_brl_12m': 'Aportes 12m',
                                'soma_aporte_usd_12m': 'Aportes 12m',
                                'preco_brl': 'Preço Atual',
                                'preco_usd': 'Preço Atual',
                                'posicao_preco': st.column_config.ProgressColumn(
                                                                                'Posição Preço (Min/Max)',
                                                                                help='Onde o preço atual está em relação à mínima e máxima de 12 meses',
                                                                                format='percent',
                                                                                min_value=0,
                                                                                max_value=1
                                                                                ),
                                'preco_12m_max_brl': 'Max Preço 12m',
                                'preco_12m_max_usd': 'Max Preço 12m',
                                'preco_12m_min_brl': 'Min Preço 12m',
                                'preco_12m_min_usd': 'Min Preço 12m',
                                'PM_brl': 'PM',
                                'PM_usd': 'PM',
                                'min_aporte_preco_unit_brl_12m': 'Min Aporte 12m',
                                'min_aporte_preco_unit_usd_12m': 'Min Aporte 12m',
                                'max_aporte_preco_unit_brl_12m': 'Max Aporte 12m',
                                'max_aporte_preco_unit_usd_12m': 'Max Aporte 12m',
                                '%_lucro': '% Lucro',
                                'dif_perc': '% Dif Plan/Atual',
                                'dy': 'DY'
                    })
else:
    st.info("Insira o valor de porte e selecione a categoria")
