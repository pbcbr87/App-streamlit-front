import streamlit as st
from plotly import graph_objects as go


def grafico_planejamento(df, mask):
    df = df[mask].sort_values('Diferença_plan_BRL_%', ascending=[False])
    fig = go.Figure()

    y = df['Custo_BRL']
    x = df['Codigo_Ativo']
    fig.add_trace(go.Bar(x=x.values, y=y.values,name='Custo'))

    y = df['Valor_Mercado_BRL']
    fig.add_trace(go.Bar(x=x.values, y=y.values, name='Valor Atual'))

    y = df['Valor_Planejado_BRL']
    fig.add_trace(go.Bar(x=x.values, y=y.values, name='Valor Planejado'))

    y = df['Diferença_plan_BRL_%']
    fig.add_trace(go.Bar(x=x.values, 
                        y=y.values, 
                        yaxis="y2", 
                        name='dif %', 
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
            title=dict(text="def %"),
            side="right",
            range=[-y.max()-0.1,y.max()+0.1],
            autorange=False,
            overlaying="y",
            tickmode="sync",
            tickformat=".0%"  
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.5,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)')
    )
    st.plotly_chart(fig, use_container_width=True)

def tabela_planejamento(df, mask):
    #Tabela Cateira
    lista_col = ['Codigo_Ativo','Categoria','Nome','Setor','Qt','Custo_BRL','Valor_Mercado_BRL', 'Valor_Planejado_BRL','%_Lucro','Peso','Nota', 'Diferença_plan_BRL', 'Diferença_plan_BRL_%']
    st.dataframe(df[mask][lista_col],use_container_width=True,hide_index=True)

def page_planejamento_def(df):

    def sl_tudo_ex():       
        st.session_state['Key_SL_2'] = df_cat
        
    df_cat = list(df['Categoria'].unique())
    
    if 'Key_SL_2' not in st.session_state:
        st.session_state['Key_SL_2'] = df_cat
    
    
    st.title('Planejamento')
    #Filtro
    col1, col2 = st.columns([1, 0.1])
    with col1:
        Categoria = st.multiselect('Categoria', df_cat, placeholder = f'Selecione quals categorias', key='Key_SL_2')
    with col2:
        st.text('')
        st.text('')
        st.button(':heavy_check_mark:', help='Selecionar tudo', key='Key_BT_2', on_click=sl_tudo_ex)
    
    mask = df['Categoria'].isin(Categoria)

    grafico_planejamento(df, mask)
    tabela_planejamento(df, mask)