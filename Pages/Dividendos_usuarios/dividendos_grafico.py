import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from datetime import datetime
from json import dumps, loads
from datetime import date, datetime
import plotly.express as px

def numero_padrao(numero):
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carregar_dividendos():
    headers = {'Authorization': f"Bearer {st.session_state.get('token')}"}
    resp = requests.get(f'{API_URL}dividendos_usuarios/pegar_dividendos', headers=headers)
    if resp.status_code == 200:
        st.session_state['dividendos_usuarios_api'] = resp.json()
    else:
        st.session_state['dividendos_usuarios_api'] = []

if 'dividendos_usuarios_api' not in st.session_state or st.session_state['dividendos_usuarios_api'] is None:
   carregar_dividendos()

c1_t, _, c2_t = st.columns([6,4,2])
c1_t.title('🤑 Gráfico de Dividendos Recebidos')
moeda = c2_t.radio('Moeda dos valores', ['BRL', 'USD'], key='moeda_valores', horizontal=True, on_change=lambda: carregar_dividendos)

if 'dividendos_usuarios_api' not in st.session_state or not st.session_state.dividendos_usuarios_api:
    st.info("💡 Nenhum Dividendos Encontrado.")
else:
    col1_1, col1_2 = st.columns([11,2])
    list_ref_date = {
                "Data Com": "data_com",
                "Data Pag.": "data_pag"
                }
    ref_date_veiw = col1_2.radio(
                                "Data de referência:",
                                list(list_ref_date.keys()),
                                help="Escolha se quer ver o gráfico pela data em que caiu o dinheiro ou pela data que deu o direito."
                                )
    ref_date = list_ref_date[ref_date_veiw]
    visao = col1_2.selectbox("Agrupamento:", ("Mensal", "Anual")) 


    colunas = ['id', 'fk_usuario', 'fk_dividendo', 'fk_evento_usuario', 'fk_ativo', 'tipo',
               'valor_bruto_brl','imposto_brl', 'valor_liq_usd', 'valor_bruto_usd','imposto_usd', 'valor_liq_brl',
               'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert', 'aceito']
    if moeda == 'BRL':        
        colunas_view = ['fk_ativo', 'tipo', 'valor_bruto_brl','imposto_brl', 'valor_liq_brl', 'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert']
        valor_bruto_col = 'valor_bruto_brl'
        valor_liq_col = 'valor_liq_brl'
        imposto_col = 'imposto_brl'
        moeda_simbolo = 'R$'
    else:
        colunas_view = ['fk_ativo', 'tipo', 'valor_bruto_usd','imposto_usd', 'valor_liq_usd', 'data_aprov', 'data_com', 'data_pag', 'data_insert', 'modo_insert']
        valor_bruto_col = 'valor_bruto_usd'
        valor_liq_col = 'valor_liq_usd'
        imposto_col = 'imposto_usd'
        moeda_simbolo = 'US$'

    df_base = pd.DataFrame(st.session_state.dividendos_usuarios_api, columns=colunas)
    df_base = df_base[(df_base['aceito'] == True) & (df_base['data_pag'].notnull())].sort_values(by=ref_date, ascending=False) # Considera apenas os dividendos aceitos para o gráfico

    df_base['data_pag'] = pd.to_datetime(df_base['data_pag'])
    df_base['data_com'] = pd.to_datetime(df_base['data_com'])
    for col in ['valor_bruto_brl','imposto_brl', 'valor_liq_usd', 'valor_bruto_usd','imposto_usd', 'valor_liq_brl']:
        df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0)
    

    with col1_1.container(horizontal=True, vertical_alignment='center'):
        tickers = st.multiselect("Filtrar Ativos:", key='multi_sl_Ativos', options=df_base['fk_ativo'].unique(), default=list(df_base['fk_ativo'].unique()))
        def sl_tudo_ex():       
            st.session_state['multi_sl_Ativos'] = list(df_base['fk_ativo'].unique())
        st.button("",icon=':material/checklist_rtl:', type='tertiary', help='Selecionar tudo', on_click=sl_tudo_ex)

    if not tickers:
        st.warning("Selecione ao menos um ativo para visualizar o gráfico.")
        st.stop()
        
    df_filtered = df_base[colunas_view][df_base['fk_ativo'].isin(tickers)].copy()
    
    if visao == "Anual":
        df_filtered['periodo'] = df_filtered[ref_date].dt.year
    else:
        # Cria formato '2024-03' para ordenação correta
        df_filtered['periodo'] = df_filtered[ref_date].dt.to_period('M').astype(str)

    df_grouped = df_filtered.groupby('periodo')[valor_liq_col].sum().reset_index()
    # --- EXIBIÇÃO ---
    periodos = sorted(df_grouped['periodo'].tolist())
    periodo_sl_start , periodo_sl_end = st.select_slider('Periodo de Referência', options=periodos, value=(periodos[0], periodos[-1]))
    df_periodo = df_filtered[(df_filtered['periodo'] >= periodo_sl_start) & (df_filtered['periodo'] <= periodo_sl_end)]
    
    df_grouped = df_grouped[(df_grouped['periodo'] >= periodo_sl_start) & (df_grouped['periodo'] <= periodo_sl_end)]

    resumo_ativo = df_periodo.groupby('fk_ativo')[valor_liq_col].sum()
    resumo_ativo = resumo_ativo.reset_index()

    col1, col2 = st.columns([5, 1])

    with col1:
        # Gráfico com Plotly
        fig = px.bar(
            df_grouped, 
            x='periodo', 
            y=valor_liq_col,
            title=f"Dividendos Líquidos por Período ({ref_date_veiw})",
            labels={'periodo': 'Período', valor_liq_col: f'Valor Líquido ({moeda_simbolo})'},
            text_auto='.2f',
            color_discrete_sequence=['#00CC96'],
            height=550
        )
        fig.update_layout(separators=',.',  yaxis_tickformat=',.2f', xaxis_type='category') # Garante que anos/meses sejam tratados como nomes
        
        st.plotly_chart(fig, width="stretch")

    with col2:  
        total_dividendos = numero_padrao(round(df_periodo[valor_liq_col].sum(),2))
        st.metric("Total no Período", f"{moeda_simbolo} {total_dividendos}")
        st.write("Detalhamento por Ativo:")
        
        st.dataframe( resumo_ativo.style.format({valor_liq_col: f"{moeda_simbolo} "+"{:,.2f}"}, decimal=',', thousands='.'),
                      hide_index=True, 
                      column_config={
                                    valor_liq_col: f"Valor Liquido {moeda_simbolo}"
                                    })

    st.divider()
    st.subheader("Dados brutos selecionados")
    st.dataframe(df_periodo.style.format({
                                          valor_bruto_col: f"{moeda_simbolo} "+"{:,.2f}",
                                          imposto_col: f"{moeda_simbolo} "+"{:,.2f}",
                                          valor_liq_col: f"{moeda_simbolo} "+"{:,.2f}",
                                          'periodo': "{}"
                                          },
                                          decimal=',', thousands='.'), 
                width="stretch", height='auto', 
                hide_index=True,                    
                column_config={
                    valor_bruto_col: st.column_config.NumberColumn(f"Valor Bruto {moeda_simbolo}"),
                    imposto_col: st.column_config.NumberColumn(f"Imposto {moeda_simbolo}"),
                    valor_liq_col: st.column_config.NumberColumn(f"Valor Liquido {moeda_simbolo}"),
                    'periodo': st.column_config.TextColumn(visao),
                    'data_aprov': st.column_config.DateColumn("Data de Aprovação", format='DD/MM/YYYY'),
                    'data_com': st.column_config.DateColumn("Data Com", format='DD/MM/YYYY'),
                    'data_pag': st.column_config.DateColumn("Data Pagamento", format='DD/MM/YYYY')
                    }
                )