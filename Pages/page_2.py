import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px

if 'carteira_api' not in st.session_state:
    st.session_state['carteira_api'] = False

st.header('Carteira')
#-----------------------------------------------------------
# Buscando dados na API
#-----------------------------------------------------------
if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

# Trantando dados recebidos
df_carteira = pd.DataFrame(st.session_state['carteira_api'])

df_carteira['pais'] = np.where((df_carteira['categoria'] == "AÇÕES") | (df_carteira['categoria'] == "FII"), 'BRL', 'USD')
df_carteira['%_lucro'] =  df_carteira['lucro_brl'] / df_carteira['custo_brl']

#-----------------------------------------------------------
#Containers layout
#-----------------------------------------------------------
sl_cat_container = st.container(border=True, horizontal=True, vertical_alignment='center')
metrica_total_container = st.container(border=True, horizontal=True, horizontal_alignment='left', vertical_alignment='center')
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
    ck_box_plan = st.checkbox('Filtro no Planejamento', help='O filtro será aplicado para recalcular os valores de planejamento')
    st.number_input('Valor de aporte:',value=None, format="%.2f", min_value=0.01)

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

if ck_box_plan:
    df_carteira_front['Valor Planejado'] = df_carteira['valor_mercado_brl'].sum() * (df_carteira['peso']/df_carteira['peso'].sum())   
else:
    df_carteira_front['Valor Planejado'] = df_carteira['valor_plan_brl']
df_carteira_front['Aporte'] = df_carteira_front['Valor Planejado'] - df_carteira_front['Valor de mercado']
df_carteira_front['Aporte %'] = df_carteira_front['Aporte']/df_carteira_front['Valor Planejado']

# ordenação
df_carteira_front = df_carteira_front.sort_values(op_ordem[option], ascending=[False])
#-----------------------------------------------------------
# Metricas
#-----------------------------------------------------------
def numero_padrao(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

with metrica_total_container:
    valor_total = df_carteira_front['Valor de mercado'].sum()
    custo_total = df_carteira_front['Custo'].sum()
    lucro_total = valor_total - custo_total
    lucro_total_perc = 100*(valor_total - custo_total) / custo_total

    st.metric(label="Custo", value=f'{numero_padrao(custo_total)} R$')
    st.metric(label="Valor de mercado", value=f'{numero_padrao(valor_total)} R$')
    st.metric(label="Lucro", value=f"{numero_padrao(lucro_total)} R$", delta=f'{numero_padrao(lucro_total_perc)} %')
#-----------------------------------------------------------
# Criar abas
#-----------------------------------------------------------
tab1, tab2, tab3 = tabs_container.tabs(["Carteira", "Grafico barra", "Grafico pizza"])
with tab1:  
    df_carteira_st = (df_carteira_front.style.format(precision=2, thousands=".", decimal=",", subset=['Qt',
                                                                                                'Custo',
                                                                                                'Valor de mercado',
                                                                                                'Lucro',
                                                                                                'Valor Planejado',
                                                                                                'Aporte'])
                                        .format(precision=0, thousands=".", decimal=",", subset=['Peso', 'Nota'])
                                        .format(precision=2, thousands=".", decimal=",", subset=['Lucro %', 'Aporte %'])
                                        )

    st.dataframe(df_carteira_st, hide_index=True, use_container_width=True,
                column_config={
                    "Lucro %": st.column_config.NumberColumn("Lucro %", format="percent"),
                    "Aporte %": st.column_config.NumberColumn("Aporte %", format="percent")
                    })

with tab2:
    df = df_carteira_front
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
        legend=dict(orientation='h', yanchor='top', y=-0.5,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)'),
         plot_bgcolor='cyan'
    )
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    df = df_carteira_front
    op_valor = {
        'Valor de Mercado': "Valor de mercado",
        'Custo': 'Custo'
    }
    option_valor = st.selectbox("Valor:", list(op_valor.keys()))

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










