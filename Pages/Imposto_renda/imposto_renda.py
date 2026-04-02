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
    if valor is None or valor == 0: return "0"
    s = "{:,.10f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")
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

# --- 1. ESTADO DA SESSÃO ---
if "df_bens" not in st.session_state:
    st.session_state.df_bens = pd.DataFrame()
if "df_divs" not in st.session_state:
    st.session_state.df_divs = pd.DataFrame()
if "df_eventos" not in st.session_state:
    st.session_state.df_eventos = pd.DataFrame()

# --- 2. MENU SUPERIOR ---
st.title("📂 Auxiliar de Declaração IRPF")

col_ano, col_btn, col_filtro = st.columns([2, 2, 6])

with col_ano:
    ano_calendario = st.selectbox("Ano", [2024, 2025, 2026], index=1, label_visibility="collapsed")

with col_btn:
    btn_carregar = st.button("🔄 Carregar Dados", width='stretch')

with col_filtro:
    busca_ticker = st.text_input("🔍 Buscar Ticket", placeholder="🔍 Buscar Ticket", label_visibility="collapsed").upper()

# --- 3. LÓGICA DE CARGA ---
if btn_carregar:
    with st.spinner("Buscando dados na API..."):
        user_id = st.session_state.get("id", 0)
        bens_raw = safe_get_list(f"{API_URL}ir/bens_direito/{user_id}", {"ano": ano_calendario})
        divs_raw = safe_get_list(f"{API_URL}ir/ir_dividendos/{user_id}", {"ano": ano_calendario})
        eventos_raw = safe_get_list(f"{API_URL}ir/bonificacoes/{user_id}", {"ano": ano_calendario})
        st.session_state.df_bens = pd.DataFrame(bens_raw)
        st.session_state.df_divs = pd.DataFrame(divs_raw)
        st.session_state.df_eventos = pd.DataFrame(eventos_raw)
        st.success("Dados carregados com sucesso!")

df_bens = st.session_state.df_bens
df_divs = st.session_state.df_divs
df_eventos = st.session_state.df_eventos

if not df_bens.empty or not df_divs.empty:
    categorias_unicas = sorted(df_bens['categoria'].unique().tolist()) if not df_bens.empty else []
    filtro_cat = st.pills("Categorias", categorias_unicas, selection_mode="multi")

    todos_tickers = pd.concat([
        df_bens['codigo_ativo'] if not df_bens.empty else pd.Series(dtype=str),
        df_divs['codigo_ativo'] if not df_divs.empty else pd.Series(dtype=str)
    ]).unique()
    todos_tickers = sorted(todos_tickers)

    for ticker in todos_tickers:
        ativo_list = df_bens[df_bens['codigo_ativo'] == ticker].to_dict('records') if not df_bens.empty else []
        ativo = ativo_list[0] if ativo_list else {}
        subset_divs = df_divs[df_divs['codigo_ativo'] == ticker] if not df_divs.empty else pd.DataFrame()

        nome_empresa = ativo.get('nome', '').upper()
        if not nome_empresa and not subset_divs.empty:
            nome_empresa = subset_divs['nome'].iloc[0].upper()
        nome_empresa = nome_empresa or "ATIVO VENDIDO / VER EXTRATO"

        cnpj_final = ativo.get('cnpj', "00.000.000/0000-00")

        if busca_ticker and (busca_ticker not in ticker.upper() and busca_ticker not in nome_empresa):
            continue
        
        categoria = ativo.get('categoria', 'N/A').upper()
        if filtro_cat and categoria not in filtro_cat:
            continue

        is_exterior = categoria in ['STOCK', 'REIT', 'ETF-US']
        
        fk_ativo_atual = ativo.get('ativo_cat') 
        subset_eventos = df_eventos[df_eventos['fk_ativo'] == fk_ativo_atual] if not df_eventos.empty else pd.DataFrame()

        with st.expander(f"📌 {ticker} - {nome_empresa} - {categoria}"):
            # --- TABELA 1: BENS E DIREITOS ---
            tabela_bens = []
            desc_principal = [
                f"TICKER: {ticker}", f"EMPRESA: {nome_empresa}", f"CNPJ: {cnpj_final}",
                f"Qtd anterior: {fmt_qtd(ativo.get('qtd_anterior', 0))}",
                f"Qtd atual: {fmt_qtd(ativo.get('qtd_atual', 0))}"
            ]

            tabela_bens.append({
                "🔍 Item": f"📦 Quantidade de {ticker}",
                f"📅 {ano_calendario-1}": fmt_qtd(ativo.get('qtd_anterior', 0)),
                f"📅 {ano_calendario}": fmt_qtd(ativo.get('qtd_atual', 0)),
            })
            
            v_ant_brl, v_atu_brl = fmt_brl(ativo.get('custo_anterior_brl', 0)), fmt_brl(ativo.get('custo_atual_brl', 0))

            if not is_exterior:
                desc_principal.extend([f"Situação anterior: {v_ant_brl}", f"Situação atual: {v_atu_brl}"])
                v_ant_tab, v_atu_tab, label_custo = v_ant_brl, v_atu_brl, "💰 Situação / Custo BRL"
            else:
                v_ant_usd, v_atu_usd = fmt_usd(ativo.get('custo_anterior_usd', 0)), fmt_usd(ativo.get('custo_atual_usd', 0))
                desc_principal.extend([f"Situação anterior: ({v_ant_usd} / {v_ant_brl})", f"Situação atual: ({v_atu_usd} / {v_atu_brl})"])
                v_ant_tab, v_atu_tab = f"{v_ant_brl} (💵 {v_ant_usd})", f"{v_atu_brl} (💵 {v_atu_usd})"
                label_custo = "🌎 Situação BRL (USD)"

            tabela_bens.append({
                "🔍 Item": label_custo,
                f"📅 {ano_calendario-1}": v_ant_tab.replace("$", r"\$"),
                f"📅 {ano_calendario}": v_atu_tab.replace("$", r"\$"),
            })

            # Preço Médio
            pm_val_ant_brl = fmt_brl(ativo.get('pm_anterior_brl', 0))
            pm_ant_tab = pm_val_ant_brl if not is_exterior else f"{pm_val_ant_brl} (💵 {fmt_usd(ativo.get('pm_anterior_usd', 0))})"

            pm_val_atu_brl = fmt_brl(ativo.get('pm_atual_brl', 0))
            pm_atu_tab = pm_val_atu_brl if not is_exterior else f"{pm_val_atu_brl} (💵 {fmt_usd(ativo.get('pm_atual_usd', 0))})"

            tabela_bens.append({
                "🔍 Item": "📊 Preço Médio (PM)",
                f"📅 {ano_calendario-1}": pm_ant_tab.replace("$", r"\$"),
                f"📅 {ano_calendario}": pm_atu_tab.replace("$", r"\$"),
            })

            # Créditos em Trânsito
            desc_transito_list = []
            if not subset_divs.empty:
                df_tr = subset_divs[(subset_divs['credito_transito_atual_brl'] > 0) | (subset_divs['credito_transito_anterior_brl'] > 0)]
                for _, row_tr in df_tr.iterrows():
                    tipo_label = row_tr['tipo'].upper()
                    v_ant_tr, v_atu_tr = row_tr['credito_transito_anterior_brl'], row_tr['credito_transito_atual_brl']
                    tabela_bens.append({
                        "🔍 Item": f"⏳ Em Trânsito: {tipo_label}",
                        f"📅 {ano_calendario-1}": fmt_brl(v_ant_tr).replace("$", r"\$"),
                        f"📅 {ano_calendario}": fmt_brl(v_atu_tr).replace("$", r"\$"),
                    })
                    desc_transito_list.append(f"{ticker} // {tipo_label} CREDITADOS E NÃO PAGOS A RECEBER DE {nome_empresa} (CNPJ: {cnpj_final}) // Situação anterior: {fmt_brl(v_ant_tr)} // Situação atual: {fmt_brl(v_atu_tr)}")
 
            # EXIBIÇÃO TABELA 1 (USANDO INDEX PARA REMOVER NÚMEROS)
            col_tab1, col_tab2 = st.columns(2)
            col_tab1.table(pd.DataFrame(tabela_bens).set_index("🔍 Item"), border="horizontal", width="stretch")

 # --- TABELA 2: RENDIMENTOS E EVENTOS ---
            with col_tab2:
                # 2.1 RENDIMENTOS (DIVIDENDOS/JCP)
                if not subset_divs.empty:
                    tabela_rendimentos = []
                    col_valor_header = "💰 Valor Bruto (Exterior)" if is_exterior else "💰 Valor Líquido (Nacional)"
                    
                    for _, row in subset_divs.iterrows():
                        tipo = row['tipo'].upper()
                        if not is_exterior:
                            valor_final = fmt_brl(row['total_liquido_brl'])
                            imposto = fmt_brl(row.get('total_imposto_brl', 0))
                            desc_principal.append(f"{tipo} liquido: {valor_final}")
                        else:
                            v_bruto_usd, v_bruto_brl = fmt_usd(row['total_bruto_usd']), fmt_brl(row['total_bruto_brl'])
                            imp_usd, imp_brl = fmt_usd(row.get('total_imposto_usd', 0)), fmt_brl(row.get('total_imposto_brl', 0))
                            imposto = f"{imp_brl} (💵 {imp_usd})"
                            valor_final = f"{v_bruto_brl} (💵 {v_bruto_usd})"
                            desc_principal.extend([f"{tipo} Bruto: ({v_bruto_usd} / {v_bruto_brl})", f"{tipo} Imposto Retido: ({imp_usd} / {imp_brl})"])

                        tabela_rendimentos.append({
                            "💸 Rendimento": f"{tipo}",
                            "🏛️ Imposto Retido": imposto.replace("$", r"\$"),
                            col_valor_header: valor_final.replace("$", r"\$")
                        })
                    st.table(pd.DataFrame(tabela_rendimentos).set_index("💸 Rendimento"), border="horizontal", width="stretch")

                # 2.2 EVENTOS CORPORATIVOS (BONIFICAÇÕES/DESDOBROS)
                if not subset_eventos.empty:
                    tabela_ev = []
                    for _, ev in subset_eventos.iterrows():
                        tipo_ev = ev['tipo'].upper()
                        data_ev = pd.to_datetime(ev['data_op_com']).strftime('%d/%m/%Y')
                        
                        # Ajuste de Moeda e Cálculo de Custo Total
                        v_total_brl = ev.get('preco_op_brl', 0)
                        v_total_usd = ev.get('preco_op_usd', 0)
                        
                        if not is_exterior:
                            valor_exibicao = fmt_brl(v_total_brl)
                            txt_moeda = valor_exibicao
                        else:
                            valor_exibicao = f"{fmt_brl(v_total_brl)} (💵 {fmt_usd(v_total_usd)})"
                            txt_moeda = f"({fmt_usd(v_total_usd)} / {fmt_brl(v_total_brl)})"

                        # Adicionando na descrição para copiar/colar (usando Custo Total)
                        info_txt = f"{tipo_ev} alterando o custo de aquisição em {txt_moeda}"
                        desc_principal.append(info_txt)

                        tabela_ev.append({
                            "📝 Evento": tipo_ev,
                            "📦 Ativo Gerado": f"{ev.get('ativo_gerado', 'N/A')}",
                            "📅 Data": data_ev,
                            "💰 Custo Total": valor_exibicao.replace("$", r"\$")
                        })
                    
                    # Exibe a tabela logo abaixo dos rendimentos, sem markdown extra
                    st.table(pd.DataFrame(tabela_ev).set_index("📝 Evento"), border="horizontal", width="stretch")
            # --- EXIBIÇÃO CÓDIGOS ---
            st.caption("📋 **Copiar Discriminação Principal (Bens e Direitos):**")
            st.code(" // ".join(desc_principal), wrap_lines=True)
            
            if desc_transito_list:
                st.caption("⚠️ **Copiar Item de Créditos em Trânsito:**")
                for item_tr in desc_transito_list:
                    st.code(item_tr, wrap_lines=True)
else:
    st.info("Clique em 'Carregar Dados' para iniciar.")