import streamlit as st
import streamlit as st
from interacao_front import incluir_dados_form
from datetime import datetime
from plotly import graph_objects as go
from .page_patrimonio import tabela_patrimonio

def add_operacao():
    #Formulário para adicionar ativos
    with st.form(key='Adicionar Operação: '):
        st.subheader('Adicionar Operação')
        col1, col2 = st.columns(2)
        with col1:
            input_data = st.date_input('Data: ', format='DD/MM/YYYY',max_value=datetime.today())
            input_Cat = st.selectbox('Tipo:',['Ações', 'FII', 'STOCK', 'REIT', 'ETF-US', 'ETF', 'BDR'])
            input_qt = st.number_input('Quantidade:', format='%f',step=0.000001, min_value=0.000001)
            input_taxa = st.number_input('Taxas (Opcional):', value=0.00, format='%f',step=0.01, min_value=0.00, help='Essa taxa não impacta calculo da planilha, valor já incluso no valot total')
        with col2:
            input_C_V = st.radio('Compra ou Venda: ',['Compra', 'Venda'], horizontal=True)
            if input_C_V == 'Compra':
                input_C_V = 'C'
            else:
                input_C_V = 'V'
            input_Ativo = st.selectbox('Ativo:', ['ABEV3', 'WEGE3',"XXXX"])
            input_Valor = st.number_input('Valor total da operção (Incluso as taxas):', format='%f',step=0.01, min_value=0.01, help='Valor total gasto, incluindo taxas')
            input_Corretora = st.text_input('Corretora:')           
        input_button_enviar = st.form_submit_button('Enviar')
    
    #Resultado de clicar no botão enviar do formuçário
    if input_button_enviar:        
        st.warning('Dados enviados:')
        st.text(f'Operação: {input_C_V} Data: {input_data} Ativo: {input_Ativo} Tipo: {input_Cat}\nQuantidade: {input_qt:.6f} Valor total da operção: R${input_Valor:.2f}\nCorretora: {input_Corretora} Taxa: R${input_taxa}')
        resp = incluir_dados_form({'Data_operacao':input_data, 'Categoria': input_Cat, 'Codigo_Ativo': input_Ativo, 'C_V': input_C_V,'Quant': input_qt, 
                        'Custo_Operacao': input_Valor, 'Taxas': input_taxa, 'Corretora': input_Corretora,  'Comenterio': ''})
        if resp == 'Ativo Cadastrado':            
            st.info(resp)
        else:
            st.error(resp)

def tabela_operacao(df_operacao, mask):
    #Tabela Cateira
    lista_col = list(df_operacao.columns)
    st.dataframe(df_operacao[mask][lista_col],use_container_width=True,hide_index=True)

def grafico_operacao(df, mask):
    #Grafico 
    df = df[mask].sort_values('Data_operacao', ascending=[False])
    fig = go.Figure()
    fig.update_layout()
    y = df['Preco_OP_BRL']
    x = df['Data_operacao']
    fig.add_trace(go.Bar(x=x.values, y=y.values,name='Preco_OP_BRL',
                         marker=dict(color=y.where(y > 0 , 'IndianRed').where(y <= 0 , 'rgb(0, 104, 201)'))))

    fig.update_layout(
        yaxis=dict(
            title=dict(text="Valor em Reais"),
            side="left",
            range=None,
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.5,xanchor='center',x=0.5,bgcolor='rgba(0,0,0,0)')
    )
    st.plotly_chart(fig, use_container_width=True)

def page_operacao_def(df, df_operacao):

    def BT_3_ex():       
        st.session_state['Key_SL_3'] = df_cat
        st.session_state['Key_SL_4'] = df_ativo
    
    def BT_4_ex():       
        st.session_state['Key_SL_3'] = df_cat
        st.session_state['Key_SL_4'] = df_ativo

    def sl_3_ex():
        mask = df_operacao['Categoria'].isin(st.session_state['Key_SL_3'])
        st.session_state['Key_SL_4'] = list(df_operacao[mask]['Codigo_Ativo'].unique())


    df_cat = list(df['Categoria'].unique())
    df_ativo = list(df_operacao['Codigo_Ativo'].unique())
    
    if 'Key_SL_3' not in st.session_state:
        st.session_state['Key_SL_3'] = df_cat
    if 'Key_SL_4' not in st.session_state:
        st.session_state['Key_SL_4'] = df_ativo
    
    
    st.title('Operações')
    
    
    #Filtro 1
    col1, col2 = st.columns([1, 0.1])
    with col1:
        st.multiselect('Categoria', df_cat, placeholder = f'Selecione quais categorias', key='Key_SL_3', on_change=sl_3_ex)
    with col2:
        st.text('')
        st.text('')
        st.button(':heavy_check_mark:', help='Selecionar tudo', key='Key_BT_3', on_click=BT_3_ex)
    
   #Filtro 2
    col1, col2 = st.columns([1, 0.1])
    with col1:
        ativo = st.multiselect('Codigo_Ativo', df_ativo ,key='Key_SL_4', placeholder = f'Selecione quais ativos')
        #Aplicar filtro nos data frame
        mask_op = df_operacao['Codigo_Ativo'].isin(ativo)
        mask_carteira = df['Codigo_Ativo'].isin(ativo)
    with col2:
        st.text('')
        st.text('')
        st.button(':heavy_check_mark:', help='Selecionar tudo', key='Key_BT_4', on_click=BT_4_ex)

    with st.popover("Adiconar Operação"):
        add_operacao()

    #Tabela Cateira
    tabela_operacao(df_operacao,mask_op)
    tabela_patrimonio(df, mask_carteira)
    grafico_operacao(df_operacao,mask_op)