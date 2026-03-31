import streamlit as st
import requests
import pandas as pd
from settings import API_URL

# --- Configurações da Página ---
st.set_page_config(page_title="Legacynvest - Auxiliar IR", layout="wide")

# --- Funções de Formatação ---
def fmt_brl(valor):
    if valor is None: return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_usd(valor):
    if valor is None: return "US$ 0,00"
    return f"US$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_qtd(valor):
    """
    Exibe a quantidade exata sem arredondar.
    Ex: 2602.123456 -> 2.602,123456
    Ex: 3102.0 -> 3.102
    """
    if valor is None or valor == 0: return "0"
    
    # Converte para string com alta precisão para evitar notação científica
    # Usamos 10 casas decimais apenas como base para a string, depois limpamos os zeros inúteis
    s = "{:,.10f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Remove zeros à direita e a vírgula caso o número termine em ,000
    if "," in s:
        s = s.rstrip('0').rstrip(',')
    return s

def safe_get_list(url, params):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, params=params, headers=headers)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        st.error(f"Erro ao conectar na API: {e}")
        return []

# --- 1. ESTADO DA SESSÃO (Cache de Dados) ---
if "df_bens" not in st.session_state:
    st.session_state.df_bens = pd.DataFrame()
if "df_divs" not in st.session_state:
    st.session_state.df_divs = pd.DataFrame()

# --- 2. MENU SUPERIOR ---
st.title("📂 Auxiliar de Declaração IRPF")

col_ano, col_btn, col_filtro = st.columns([2, 2, 6])

with col_ano:
    ano_calendario = st.selectbox("Ano", [2024, 2025, 2026], index=1, label_visibility="collapsed")

with col_btn:
    btn_carregar = st.button("🔄 Carregar Dados", width='stretch')

with col_filtro:
    busca_ticker = st.text_input("🔍 Buscar Ticket", placeholder="🔍 Buscar Ticket", label_visibility="collapsed").upper()

# --- 3. LÓGICA DE CARGA (Apenas quando clica no botão) ---
if btn_carregar:
    with st.spinner("Buscando dados na API..."):
        user_id = st.session_state.get("id", 0)
        
        bens_raw = safe_get_list(f"{API_URL}bens_direito/{user_id}", {"ano": ano_calendario})
        divs_raw = safe_get_list(f"{API_URL}ir_dividendos/{user_id}", {"ano": ano_calendario})
        
        st.session_state.df_bens = pd.DataFrame(bens_raw)
        st.session_state.df_divs = pd.DataFrame(divs_raw)
        st.success("Dados carregados com sucesso!")

# --- 4. LÓGICA DE FILTRAGEM E UNIÃO (Fora do bloco do botão) ---
df_bens = st.session_state.df_bens
df_divs = st.session_state.df_divs

if not df_bens.empty or not df_divs.empty:
    
    # Criamos a lista de categorias dinâmicas baseada nos ativos carregados
    categorias_unicas = sorted(df_bens['categoria'].unique().tolist()) if not df_bens.empty else []
    filtro_cat = st.pills("Categorias", categorias_unicas, selection_mode="multi")

    # Identificamos todos os tickers únicos (Bens + Dividendos) para não esquecer ativos zerados
    todos_tickers = pd.concat([
        df_bens['codigo_ativo'] if not df_bens.empty else pd.Series(dtype=str),
        df_divs['codigo_ativo'] if not df_divs.empty else pd.Series(dtype=str)
    ]).unique()

    todos_tickers = sorted(todos_tickers)

    # --- 5. LOOP DE EXIBIÇÃO ---
    for ticker in todos_tickers:
       # Dados de Bens
        ativo_list = df_bens[df_bens['codigo_ativo'] == ticker].to_dict('records') if not df_bens.empty else []
        ativo = ativo_list[0] if ativo_list else {}
        
        # Dados de Dividendos
        subset_divs = df_divs[df_divs['codigo_ativo'] == ticker] if not df_divs.empty else pd.DataFrame()

        # Lógica de Nome e CNPJ (Prioriza Bens, Fallback para Dividendos)
        nome_empresa = ativo.get('nome')
        if not nome_empresa and not subset_divs.empty and 'nome' in subset_divs.columns:
            nome_empresa = subset_divs['nome'].iloc[0]
        nome_empresa = (nome_empresa or "ATIVO VENDIDO / VER EXTRATO").upper()

        # Lógica de CNPJ (Fallback para Dividendos + Placeholder se vazio)
        cnpj_raw = ativo.get('cnpj')
        if not cnpj_raw and not subset_divs.empty and 'cnpj' in subset_divs.columns:
            cnpj_raw = subset_divs['cnpj'].iloc[0]
        
        # Garante que sempre terá um formato de CNPJ para copiar, mesmo que genérico
        cnpj_final = cnpj_raw if cnpj_raw else "00.000.000/0000-00"

        # Filtros
        if busca_ticker and (busca_ticker not in ticker.upper() and busca_ticker not in nome_empresa):
            continue
        
        categoria = ativo.get('categoria', 'N/A').upper()
        if filtro_cat and categoria not in filtro_cat:
            continue

        # Configurações de exibição
        is_exterior = categoria in ['STOCK', 'REIT', 'ETF-US']
        qt_ant = fmt_qtd(ativo.get('qtd_anterior', 0))
        qt_atu = fmt_qtd(ativo.get('qtd_atual', 0))

        # Construção da Discriminação
        desc = [
            f"TICKER: {ticker}",
            f"EMPRESA: {nome_empresa}",
            f"CNPJ: {cnpj_final}",
            f"Qtd anterior: {qt_ant}",
            f"Qtd atual: {qt_atu}"
        ]
        # Lógica Financeira (Brasil vs Exterior)
        if not is_exterior:
            desc.append(f"Situação anterior: {fmt_brl(ativo.get('custo_anterior_brl', 0))}")
            desc.append(f"Situação atual: {fmt_brl(ativo.get('custo_atual_brl', 0))}")
        else:
            sit_ant = f"{fmt_usd(ativo.get('custo_anterior_usd', 0))} / {fmt_brl(ativo.get('custo_anterior_brl', 0))}"
            sit_atu = f"{fmt_usd(ativo.get('custo_atual_usd', 0))} / {fmt_brl(ativo.get('custo_atual_brl', 0))}"
            desc.append(f"Situação anterior: ({sit_ant})")
            desc.append(f"Situação atual: ({sit_atu})")

        # Adiciona Dividendos na descrição
        for _, row in subset_divs.iterrows():
            tipo = row['tipo']
            if not is_exterior:
                desc.append(f"{tipo} liquido: {fmt_brl(row['total_liquido_brl'])}")
                if row.get('total_imposto_brl', 0) > 0:
                    desc.append(f"Imposto {tipo}: {fmt_brl(row['total_imposto_brl'])}")
            else:
                v_prov = f"({fmt_usd(row['total_bruto_usd'])} / {fmt_brl(row['total_bruto_brl'])})"
                v_imp = f"({fmt_usd(row['total_imposto_usd'])} / {fmt_brl(row['total_imposto_brl'])})"
                desc.append(f"{tipo} Bruto: {v_prov}")
                if row.get('total_imposto_brl', 0) > 0:
                    desc.append(f"Imposto {tipo}: {v_imp}")

        # --- INTERFACE ---
        with st.expander(f"📌 {ticker} - {nome_empresa} - {categoria} {'- EXTERIOR' if is_exterior else ''}"):
            st.text("📑 Discriminação do Bens e direitos")
            c1, c2, c3 = st.columns([3, 1.2, 1.2])
            with c1:
                st.code(" // ".join(desc), wrap_lines=True)
            with c2:
                st.write(f"**{ano_calendario-1}:**")
                st.write(fmt_brl(ativo.get('custo_anterior_brl', 0)))
            with c3:
                st.write(f"**{ano_calendario}:**")
                st.write(fmt_brl(ativo.get('custo_atual_brl', 0)))
            
            if not subset_divs.empty:
                # st.divider()
                st.text("💰 Rendimentos e Impostos")

                # 1. Aplicando o Estilo (Pandas Styler)
                # Formata os valores monetários com R$ e separadores BR
                df_divs_styled = subset_divs[['tipo', 'total_bruto_brl', 'total_liquido_brl', 'total_imposto_brl']].style.format({
                                                'total_bruto_brl': lambda x: fmt_brl(x),
                                                'total_liquido_brl': lambda x: fmt_brl(x),
                                                'total_imposto_brl': lambda x: fmt_brl(x)
                                            })

                # 2. Renderizando com Column Config (Streamlit)
                st.dataframe(
                    df_divs_styled, 
                    hide_index=True, 
                    width='content', # Ajusta à largura do expander
                    column_config={
                        "tipo": st.column_config.TextColumn(
                            "Tipo de Provento",
                            help="Categoria do rendimento (Dividendo, JCP, Rendimento, etc.)"
                        ),
                        "total_bruto_brl": st.column_config.NumberColumn(
                            "Valor Bruto",
                            help="Valor total recebido antes dos impostos"
                        ),
                        "total_liquido_brl": st.column_config.NumberColumn(
                            "Valor Líquido",
                            help="Valor total recebido após os impostos"
                        ),
                        "total_imposto_brl": st.column_config.NumberColumn(
                            "Imposto Retido",
                            help="Imposto de renda retido na fonte, se aplicável"
                        )
                    }
                )
                # --- SEÇÃO: CRÉDITOS EM TRÂNSITO (Saldos a Receber) ---

                # Filtra apenas se houver valor em trânsito no ano atual ou anterior
                df_transito = subset_divs[(subset_divs['credito_transito_atual_brl'] > 0) | 
                                          (subset_divs['credito_transito_anterior_brl'] > 0)]
                
                if not df_transito.empty:
                    # st.divider()
                    st.warning("⚠️ **Créditos em Trânsito (Bens e Direitos)**")
                    st.caption("Valores declarados pela empresa, mas ainda não depositados na sua conta até 31/12.")
                    
                    for _, row_tr in df_transito.iterrows():
                        tipo_label = "DIVIDENDOS" if row_tr['tipo'].lower() == "dividendo" else "JSCP"
                        texto_item = f"{ticker} // {tipo_label} CREDITADOS E NÃO PAGOS A RECEBER DE {nome_empresa} (CNPJ: {cnpj_final}) // Situação anterior: {fmt_brl(row_tr['credito_transito_anterior_brl'])} // Situação atual: {fmt_brl(row_tr['credito_transito_atual_brl'])}"
                        # Layout para facilitar a cópia dos dois anos
                        c1, c2, c3 = st.columns([3, 1.2, 1.2])
                        with c1:
                            st.code(texto_item , wrap_lines=True)
                        with c2:
                            st.write(f"**{ano_calendario-1}:**")
                            st.write(fmt_brl(row_tr['credito_transito_anterior_brl']))
                        with c3:
                            st.write(f"**{ano_calendario}:**")
                            st.write(fmt_brl(row_tr['credito_transito_atual_brl']))

else:
    st.info("Clique em 'Carregar Dados' para iniciar.")