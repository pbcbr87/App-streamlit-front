import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px
from decimal import Decimal, DivisionByZero


#------------------------------------------------
API_URL = 'https://pythonapi-production-6268.up.railway.app/'
#------------------------------------------------

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

def ajustar_tamanho_metricas(escala=0.8, gap_rem="0.5rem"):
    """
    Injeta CSS para reduzir o tamanho do VALOR e AUMENTAR o tamanho do LABEL.
    O valor 'escala' controla o tamanho geral.
    """
    st.markdown(
        f"""
        <style>
         /* Reduz o gap (espaço) entre as colunas dentro de st.columns */
        div[data-testid="stHorizontalBlock"] {{
            gap: {gap_rem} !important;
        }}
        
        /* Estilo para o valor principal (Reduzido!) */
        [data-testid="stMetricValue"] {{
            /* 1.8 é menor que o 2.5 original -> reduz o número */
            font-size: {escala * 1.8}rem; 
        }}
        
        /* Estilo para o label (Aumentado!) */
        [data-testid="stMetricLabel"] p {{
            /* 1.3 é maior que o 1.0 original -> aumenta o label */
            font-size: {escala * 1.3}rem; 
        }}

        /* Estilo para o delta (mantido na proporção) */
        [data-testid="stMetricDelta"] {{
            font-size: {escala * 1.25}rem; 
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def create_sunburst_chart(df: pd.DataFrame):
    """Cria o gráfico Sunburst com margens mínimas."""
    fig = px.sunburst(df, path=["Categoria", "Setor", "Código ativo"], values='Valor de mercado', color="Categoria")
    fig.update_traces(textinfo='label+percent entry')
    fig.update_layout(
        margin=dict(b=0, t=0, l=0, r=0),
        # Adiciona um pequeno padding visual no fundo (opcional)
        plot_bgcolor='rgba(0,0,0,0)' 
    )
    return fig

def numero_padrao(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Função de busca e conversão de dados da carteira
def get_carteira_data(token: str) -> list:
    """Busca a carteira da API e converte strings numéricas para Decimal."""
    
    resp = requests.get(
        f'{API_URL}carteira/pegar_carteira/{st.session_state.get("id", 0)}', 
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

#------------------------------------------------
# Delcarar sessions
#------------------------------------------------
if 'carteira_api' not in st.session_state or st.session_state['carteira_api'] is None:     
    st.session_state['carteira_api'] = get_carteira_data(st.session_state.token)
#-----------------------------------------------
# Layout
#-----------------------------------------------

st.title('Carteira')

# Trantando dados recebidos
if not st.session_state['carteira_api']:
   st.info('Carteira vazia ou não calculada. Adicione um ativo para começar.')
   st.stop()

df_carteira = pd.DataFrame(st.session_state['carteira_api'])
# for i in df_carteira['valor_plan_brl']:
#     print(type(i))
df_carteira['pais'] = np.where((df_carteira['categoria'] == "AÇÕES") | (df_carteira['categoria'] == "FII"), 'BRL', 'USD')
df_carteira['%_lucro'] =  df_carteira.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='lucro_brl', coluna_denominador='custo_brl'), axis=1)

#-----------------------------------------------------------
#Containers layout
#-----------------------------------------------------------
col1, col2 = st.columns([4,3])
sl_cat_container = col1.container(border=True, horizontal=True, vertical_alignment='center')
metrica_total_container = col2.container(border=True, horizontal=True, horizontal_alignment='left', vertical_alignment='center')
tabs_container = st.container()
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
    # ck_box_plan = st.checkbox('Filtro no Planejamento', help='O filtro será aplicado para recalcular os valores de planejamento')
    # valor_aporte = st.number_input('Valor de aporte:',value=None, format="%.2f", min_value=0.01)
    # qt_ativo_aporte = st.number_input('Quantos ativos', value=1, format='%i', min_value=1)

    op_ordem = {
                'Valor de mercado': "Valor de mercado",
                'Custo': "Custo",
                'Lucro': "Lucro",
                'Percentual do lucro': "Lucro %",
                'Valor Planejado': 'Valor Planejado',
                'Aporte': 'Aporte',
                'Percentual do aporte': 'Aporte %'
                }
    option = st.selectbox("Ordendar por", list(op_ordem.keys()))

mask = df_carteira['categoria'].isin(mult_sl_cat)
df_carteira = df_carteira[mask]


#-----------------------------------------------------------
#Dataframe que vai utilizar
#-----------------------------------------------------------
df_carteira_front = pd.DataFrame()
df_carteira_front['Código ativo'] = df_carteira['codigo_ativo']
df_carteira_front['Categoria'] = df_carteira['categoria']
df_carteira_front['País'] = df_carteira['pais']
df_carteira_front['Nome'] = df_carteira['nome']
df_carteira_front['Setor'] = df_carteira['setor']
df_carteira_front['Qt'] = df_carteira['quant']
df_carteira_front['Custo'] = df_carteira['custo_brl']
df_carteira_front['Valor de mercado'] = df_carteira['valor_mercado_brl']
df_carteira_front['Lucro'] = df_carteira['lucro_brl']
df_carteira_front['Lucro %'] = df_carteira['%_lucro']
df_carteira_front['Peso'] = df_carteira['peso']
df_carteira_front['Nota'] = df_carteira['nota']
df_carteira_front['Valor Planejado'] = df_carteira['valor_plan_brl']
df_carteira_front['Aporte'] = df_carteira['valor_plan_brl'] - df_carteira['valor_mercado_brl']
df_carteira_front['Aporte %'] = df_carteira_front.apply(lambda row: divisao_percentual_segura(row, coluna_numerador='Aporte', coluna_denominador='Valor Planejado'), axis=1)


# ordenação
df_carteira_front = df_carteira_front.sort_values(op_ordem[option], ascending=[False])
#-----------------------------------------------------------
# Metricas
#-----------------------------------------------------------
with metrica_total_container:
    valor_total = df_carteira_front['Valor de mercado'].sum()
    custo_total = df_carteira_front['Custo'].sum()
    lucro_total = valor_total - custo_total
    lucro_total_perc = 100*(valor_total - custo_total) / custo_total if custo_total != 0 else Decimal('0')

    ajustar_tamanho_metricas(0.7, "0.5rem")
    st.metric(label="Custo", value=f'{numero_padrao(custo_total)} R$', width ='stretch')
    st.metric(label="Valor de mercado", value=f'{numero_padrao(valor_total)} R$', width ='stretch')
    st.metric(label="Lucro", value=f"{numero_padrao(lucro_total)} R$", delta=f'{numero_padrao(lucro_total_perc)} %', width ='stretch')
#-----------------------------------------------------------
# Criar abas
#-----------------------------------------------------------
if df_carteira.empty:
    st.info("Selecione alguma categoria.")
    
tab1, tab2, tab3 = tabs_container.tabs(["Carteira", "Grafico barra", "Grafico pizza"])
with tab1:
    if not df_carteira_front.empty:
        df_carteira_st = (df_carteira_front.style.format(precision=2, thousands=".", decimal=",", subset=['Qt',
                                                                                                    'Custo',
                                                                                                    'Valor de mercado',
                                                                                                    'Lucro',
                                                                                                    'Valor Planejado',
                                                                                                    'Aporte'])
                                            .format(precision=0, thousands=".", decimal=",", subset=['Peso', 'Nota'])
                                            .format(precision=2, thousands=".", decimal=",", subset=['Lucro %', 'Aporte %'])
                                            )

        st.dataframe(df_carteira_st, hide_index=True, width='content',
                    column_config={
                        "Lucro %": st.column_config.NumberColumn("Lucro %", format="percent"),
                        "Aporte %": st.column_config.NumberColumn("Aporte %", format="percent")
                        })

with tab2:
    df = df_carteira_front
    if not df.empty:
        fig = go.Figure()
        fig.update_layout()

        x = df['Código ativo']
        
        y = df['Custo']
        fig.add_trace(go.Bar(x=x.values, y=y.values,name='Custo'))

        y = df['Valor de mercado']
        fig.add_trace(go.Bar(x=x.values, y=y.values, name='Valor Atual'))

        y = df['Valor Planejado']
        fig.add_trace(go.Bar(x=x.values, 
                            y=y.values, 
                            name='Valor Planejado',
                            marker=dict(color='green', line=dict(color='black'))
                            ))

        y = df['Lucro %']
        fig.add_trace(go.Bar(x=x.values, 
                            y=y.values, 
                            yaxis="y2", 
                            name='Lucro %', 
                            textposition='auto',
                            texttemplate = "%{value:.2%}",
                            textfont = dict(color='black'),
                            marker=dict(color=y.where(y > 0 , 'IndianRed').where(y <= 0 , 'gray'),
                                        opacity=0.5,
                                        line=dict(color='black',width=1))))



        y = df['Aporte %']
        fig.add_trace(go.Bar(x=x.values, 
                            y=y.values, 
                            yaxis="y2", 
                            name='Aporte %', 
                            textposition='auto',
                            texttemplate = "%{value:.2%}",
                            textfont = dict(color='black'),
                            marker=dict(color=y.where(y > 0 , 'darkseagreen').where(y <= 0 , 'darkcyan'),
                                        opacity=0.5,
                                        line=dict(color='black',width=1))))

        fig.update_layout(
            separators= ",.",
            yaxis=dict(
                title=dict(text="Valor em Reais"),
                side="left",
                range=None,
                tickformat=",.2f"   
            ),
            yaxis2=dict(
                title=dict(text="%"),
                side="right",
                range=None,
                overlaying="y",
                tickmode="sync",
                tickformat=".2%"  
            ),
            legend=dict(orientation='h', yanchor='top', y=-0.2,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)'),
            margin=dict(b=10,t=40) 
            )
        st.plotly_chart(fig, width='stretch')

with tab3:
    df = df_carteira_front
    if not df.empty:
        op_valor = {
            'Valor de Mercado': "Valor de mercado",
            'Custo': 'Custo'
        }
        option_valor = st.selectbox("Valor:", list(op_valor.keys()))

        fig_sunburst = create_sunburst_chart(df)
        st.plotly_chart(fig_sunburst, width='stretch')

        #Pizza tipos
        fig = px.pie(df, values=op_valor[option_valor], names='Categoria', title='Tipo de ativos',
                hover_data=['Qt'], labels={'Qt':'Quantidade de ativos'})
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})

        #Pizza Ativos
        fig2 = px.pie(df, values=op_valor[option_valor], names='Código ativo', title='Ativos',
                hover_data=['Qt'], labels={'Qt':'Quantidade de ativos'})
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        fig2.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})

        #Pizza Setor
        fig3 = px.pie(df, values=op_valor[option_valor], names='Setor', title='Setores',
                hover_data=['Qt'], labels={'Qt':'Quantidade de ativos'})
        fig3.update_traces(textposition='inside', textinfo='percent+label')
        fig3.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})

        #Pizza país
        fig4 = px.pie(df, values=op_valor[option_valor], names='País', title='País',
                hover_data=['Qt'], labels={'Qt':'Quantidade de ativos'})
        fig4.update_traces(textposition='inside', textinfo='percent+label')
        fig4.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})

        #Plotar valores
        with st.container(horizontal=True, horizontal_alignment='left'):        
            st.plotly_chart(fig2)
            st.plotly_chart(fig3)
        with st.container(horizontal=True, horizontal_alignment='left'):
            st.plotly_chart(fig)
            st.plotly_chart(fig4)

   










