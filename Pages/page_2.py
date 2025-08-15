import streamlit as st
import requests
import pandas as pd
from plotly import graph_objects as go


st.title('Carteira')

resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})

carteira = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'})

df_carteira = pd.DataFrame(carteira.json())
df_carteira['%'] = 100 * df_carteira['custo_brl'] / df_carteira['custo_brl'].sum()
df_carteira['%_lucro'] =  (df_carteira['valor_mercado_brl'] - df_carteira['custo_brl']) / df_carteira['custo_brl']


# Criar abas
tab1, tab2 = st.tabs(["Carteira", "Grafico Barra"])

# Ajuste de estilo e ordenação
df_carteira = df_carteira.sort_values('valor_mercado_brl', ascending=[False])
# df_carteira_st = (df_carteira.style.format(precision=2, thousands=".", decimal=",", subset=['quant', 'custo_brl', 'custo_usd'])
#                                 .format(precision=0, thousands=".", decimal=",", subset=['peso', 'nota'])
#                                 .format(precision=2, thousands=".", decimal=",", subset=['%']))
with tab1:    
    st.dataframe(df_carteira, hide_index=True, 
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
        yaxis=dict(
            title=dict(text="Valor em Reais"),
            side="left",
            range=None,
            tickformat=".00f"
        ),
        yaxis2=dict(
            title=dict(text="Lucro %"),
            side="right",
            range=None,
            overlaying="y",
            tickmode="sync",
            tickformat=".0%"  
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.5,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)')
    )
    st.plotly_chart(fig, use_container_width=True)










