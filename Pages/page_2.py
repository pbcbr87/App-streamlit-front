import streamlit as st
import requests
import pandas as pd
from plotly import graph_objects as go

if 'carteira_api' not in st.session_state:
    st.session_state['carteira_api'] = False

st.title('Carteira')


# Buscando dados na API
if st.session_state['carteira_api'] == False:
    resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

# Trantando dados recebidos
df_carteira = pd.DataFrame(st.session_state['carteira_api'])
df_carteira['%'] = 100 * df_carteira['custo_brl'] / df_carteira['custo_brl'].sum()
df_carteira['%_lucro'] =  (df_carteira['valor_mercado_brl'] - df_carteira['custo_brl']) / df_carteira['custo_brl']

#-----------------------------------------------------------
#Containers
#-----------------------------------------------------------
sl_cat_container = st.container(border=True)
metrica_total_container = st.container(border=True, horizontal=True, horizontal_alignment='left')
tabs_container = st.container()

#-----------------------------------------------------------
#Seletor
#-----------------------------------------------------------
def sl_tudo_ex():       
        st.session_state['Key_SL_2'] = df_cat
        
df_cat = list(df_carteira['categoria'].unique())
    
if 'Key_SL_2' not in st.session_state:
    st.session_state['Key_SL_2'] = df_cat

#multiselect
col1, col2 = sl_cat_container.columns([1, 0.1])
with col1:
        Categoria = st.multiselect('categoria', df_cat, placeholder = f'Selecione quals categorias', key='Key_SL_2')
with col2:
    st.text('')
    st.text('')
    st.button(':heavy_check_mark:', help='Selecionar tudo', key='Key_BT_2', on_click=sl_tudo_ex)

mask = df_carteira['categoria'].isin(Categoria)
df_carteira = df_carteira[mask]
# ordenação
df_carteira = df_carteira.sort_values('valor_mercado_brl', ascending=[False])

#-----------------------------------------------------------
# Metricas
#-----------------------------------------------------------
def numero_padrao(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with metrica_total_container:
    valor_total = round(df_carteira['valor_mercado_brl'].sum(), 2)
    custo_total = round(df_carteira['custo_brl'].sum(), 2)
    lucro_total = round(valor_total - custo_total,2)
    lucro_total_perc = round(100*(valor_total - custo_total) / custo_total,2)

    st.metric(label="Valor de mercado", value=f'{numero_padrao(valor_total)} R$')
    st.metric(label="Lucro", value=f"{numero_padrao(lucro_total)} R$", delta=f'{numero_padrao(lucro_total_perc)} %')

#-----------------------------------------------------------
# Criar abas
#-----------------------------------------------------------
tab1, tab2, tab3 = tabs_container.tabs(["Carteira", "Grafico barra", "Grafico pizza"])
with tab1:  
    df_carteira_st = (df_carteira.style.format(precision=2, thousands=".", decimal=",", subset=['quant',
                                                                                                'custo_brl',
                                                                                                'custo_usd',
                                                                                                'valor_mercado_brl',
                                                                                                'valor_mercado_usd',
                                                                                                'lucro_brl',
                                                                                                'lucro_usd',
                                                                                                'valor_plan_brl',
                                                                                                'valor_plan_usd'])
                                .format(precision=0, thousands=".", decimal=",", subset=['peso', 'nota'])
                                .format(precision=2, thousands=".", decimal=",", subset=['%']))

    st.dataframe(df_carteira_st, hide_index=True, 
                    column_config={
                        "%": st.column_config.NumberColumn(
                            "% (BRL)",
                            help="Proporcação do ativo na carteira em BRL"
                            )
                        })

with tab2:
    df = df_carteira
    fig = go.Figure()
    fig.update_layout()

    y = df['custo_brl']
    x = df['codigo_ativo']
    fig.add_trace(go.Bar(x=x.values, y=y.values,name='Custo'))

    y = df['valor_mercado_brl']
    fig.add_trace(go.Bar(x=x.values, y=y.values, name='Valor Atual'))

    y = df['valor_plan_brl']
    fig.add_trace(go.Bar(x=x.values, 
                        y=y.values, 
                        name='Valor Planejado',
                        marker=dict(color='green', line=dict(color='black'))
                        ))

    y = df['%_lucro']
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
    fig.update_layout(
        separators= ",.",
        yaxis=dict(
            title=dict(text="Valor em Reais"),
            side="left",
            range=None,
            tickformat=",.2f"   
        ),
        yaxis2=dict(
            title=dict(text="Lucro %"),
            side="right",
            range=None,
            overlaying="y",
            tickmode="sync",
            tickformat=".2%"  
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.5,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)')
    )
    st.plotly_chart(fig, use_container_width=True)

with tab3:

    df = df_carteira

    # Plotly Express

    import plotly.express as px
    
    fig = px.pie(df, values='valor_mercado_brl', names='categoria', title='Tipo de ativos',
            hover_data=['valor_mercado_usd'], labels={'valor_mercado_usd':'Valor Mercado em Dolar'})
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})


    fig2 = px.pie(df, values='valor_mercado_brl', names='codigo_ativo', title='Ativos',
            hover_data=['valor_mercado_usd'], labels={'valor_mercado_usd':'Valor Mercado em Dolar'})
    fig2.update_traces(textposition='inside', textinfo='percent+label')
    fig2.update_layout(title={'y':0.9, 'x':0.5, 'xanchor':'center', 'yanchor':'top'})

    with st.container(horizontal=True, horizontal_alignment='left'):
        st.plotly_chart(fig)
        st.plotly_chart(fig2)








