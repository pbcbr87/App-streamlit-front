import streamlit as st
from plotly import graph_objects as go
import plotly.express as px


def metricas_patrimonio(df, mask):
    #Totais:
    Valor_Total = round(df[mask]['Valor_Mercado_BRL'].sum(),2)
    Lucro_Total = round(Valor_Total - df[mask]['Custo_BRL'].sum(),2)
    Lucro_p_Total = round(100*Lucro_Total/Valor_Total,2)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('Valor Total: ', f'R$ {Valor_Total}')
    with col2:
        st.metric('Lucro Total: ',f'R$ {Lucro_Total}')
    with col3:
        st.metric('Lucro %: ',f'{Lucro_p_Total}%')

def tabela_patrimonio(df, mask):
    #Tabela Cateira
    lista_col = ['Codigo_Ativo','Categoria','Nome','Setor','Qt','Custo_BRL','Valor_Mercado_BRL', 'Valor_Planejado_BRL','%_Lucro','Peso','Nota', 'Diferença_plan_BRL', 'Diferença_plan_BRL_%']
    st.dataframe(df[mask][lista_col],width='content',hide_index=True)

def grafico_patrimonio(df, mask):
    #Grafico 
    df = df[mask].sort_values('Valor_Mercado_BRL', ascending=[False])
    fig = go.Figure()
    fig.update_layout()
    y = df['Custo_BRL']
    x = df['Codigo_Ativo']
    fig.add_trace(go.Bar(x=x.values, y=y.values,name='Custo'))

    y = df['Valor_Mercado_BRL']
    fig.add_trace(go.Bar(x=x.values, y=y.values, name='Valor Atual'))

    y = df['%_Lucro']
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
    st.plotly_chart(fig, width='content')

def pizza_patrimonio(df, mask):
    fig = px.pie(df[mask], values='Valor_Mercado_BRL', names='Codigo_Ativo')
    fig.update_traces(textposition='inside',textinfo='percent+label')
    fig.update(layout_showlegend=False)
    st.plotly_chart(fig, width='content')
    
def page_patrimonio_def(df):
    
    def sl_tudo_ex():       
        st.session_state['Key_SL_1'] = df_cat
        
    df_cat = list(df['Categoria'].unique())
    if 'Key_SL_1' not in st.session_state:
        st.session_state['Key_SL_1'] = df_cat


    st.title('Patrimônio')
    #Filtro
    col1, col2 = st.columns([1, 0.1])
    with col1:
        Categoria = st.multiselect('Categoria',  df_cat, placeholder = f'Selecione quais categorias', key='Key_SL_1')
        mask = df['Categoria'].isin(Categoria)
    with col2:
        st.text('')
        st.text('')
        st.button(':heavy_check_mark:', help='Selecionar tudo', key='Key_BT_1', on_click=sl_tudo_ex)
    
    metricas_patrimonio(df, mask)
    #col1, col2 = st.columns([2,0.1])
   # with col1:
    with st.expander("Ver pizza"):
        pizza_patrimonio(df, mask)
    grafico_patrimonio(df, mask)
   # with col2:
        
    tabela_patrimonio(df, mask)