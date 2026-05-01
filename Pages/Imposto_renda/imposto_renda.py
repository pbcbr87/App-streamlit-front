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

def formatar_cnpj(cnpj):
    cnpj = str(cnpj).zfill(14) # Garante que tenha 14 dígitos (preenche com zeros)
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def safe_post_list(url, json_data):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(url, json=json_data, headers=headers)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        st.error(f"Erro ao conectar na API (POST): {e}")
        return []

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
for df_key in ["df_bens", "df_divs", "df_eventos", "df_vendas", "df_base_oficial"]:
    if df_key not in st.session_state:
        st.session_state[df_key] = pd.DataFrame()

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
        
        # Chamadas usando seu padrão safe_get_list
        st.session_state.df_bens = pd.DataFrame(safe_get_list(f"{API_URL}ir/bens_direito/{user_id}", {"ano": ano_calendario}))
        st.session_state.df_divs = pd.DataFrame(safe_get_list(f"{API_URL}ir/ir_dividendos/{user_id}", {"ano": ano_calendario}))
        st.session_state.df_eventos = pd.DataFrame(safe_get_list(f"{API_URL}ir/bonificacoes/{user_id}", {"ano": ano_calendario}))
        st.session_state.df_vendas = pd.DataFrame(safe_get_list(f"{API_URL}ir/resumo_vendas_ativos/{user_id}", {"ano": ano_calendario}))

        # Coleta os IDs para a busca consolidada
        todos_ids = set()
        for dff in [st.session_state.df_bens, st.session_state.df_divs, st.session_state.df_eventos, st.session_state.df_vendas]:
            if not dff.empty and 'ativo_cat' in dff.columns:
                todos_ids.update(dff['ativo_cat'].dropna().unique().tolist())

        # USANDO O PADRÃO SAFE PARA A NOVA ROTA
        if todos_ids:
            dados_base = safe_post_list(f"{API_URL}ativos/lista_ativos_base", list(todos_ids))
            st.session_state.df_base_oficial = pd.DataFrame(dados_base)
        else:
            st.session_state.df_base_oficial = pd.DataFrame()
        
        st.success("Dados carregados com sucesso!")

df_bens = st.session_state.df_bens
df_divs = st.session_state.df_divs
df_eventos = st.session_state.df_eventos
df_vendas = st.session_state.df_vendas
df_base_oficial = st.session_state.df_base_oficial

# --- 4. LÓGICA DE PROCESSAMENTO ---
if not df_base_oficial.empty:
    cadastro_ativos = {}
    for _, row in df_base_oficial.iterrows():
        # Usamos 'codigo_ativo' conforme seu modelo
        tk = str(row.get('codigo_ativo', '')).upper().strip()
           
        cadastro_ativos[tk] = {
            'nome': str(row.get('nome_curto',row.get('razao_social', row.get('nome', '')))).upper().strip()[:40], # Razão Social é melhor para o IR
            'cnpj': formatar_cnpj(row.get('cnpj_ativo', '00000000000000')),     # Campo correto: cnpj_ativo
            'categoria': str(row.get('categoria_fiscal', 'N/A')).upper().strip(),
            'ativo_cat': row.get('ativo_cat'),
            'adm_nome': row.get('nome_adm', 'NÃO INFORMADO')[:40],        # Nomes exatos do seu Ativos class
            'adm_cnpj': formatar_cnpj(row.get('cnpj_adm', '00000000000000'))
        }

    map_codigo_receita = {
        'AÇÕES': 'Grupo 03 - Cod. 01 - Pais. 105',
        'STOCK': 'Grupo 03 - Cod. 01 - Pais. 249',
        'REIT': 'Grupo 03 - Cod. 01 - Pais. 249',
        'ETF-US': 'Grupo 07 - Cod. 99 - Pais. 249',
        'ETF': 'Grupo 07 - Cod. 08 - Pais. 105',
        'FII': 'Grupo 07 - Cod. 03 - Pais. 105',
        'FIAGRO': 'Grupo 07 - Cod. 02 - Pais. 105',
        'BDR': 'Grupo 04 - Cod. 04 - Pais. 105'
    }
    todas_cats = sorted(list(set(info['categoria'] for info in cadastro_ativos.values())))
    filtro_cat = st.pills("Categorias", todas_cats, selection_mode="multi")
    
    # Filtramos e ordenamos os tickers
    todos_tickers = sorted(cadastro_ativos.keys())

    for ticker in todos_tickers:
        dados_base = cadastro_ativos[ticker]
        nome_empresa = dados_base['nome']
        cnpj_final = dados_base['cnpj']
        categoria = dados_base['categoria']
        fk_ativo_atual = dados_base['ativo_cat']
        codigo_receita = map_codigo_receita.get(categoria, "Categoria não mapeada")
        is_exterior = categoria in ['STOCK', 'REIT', 'ETF-US']

        # Filtros de interface
        if (busca_ticker and (busca_ticker not in ticker and busca_ticker not in nome_empresa)):
            continue
        if filtro_cat and categoria not in filtro_cat:
            continue

        # Seleção de dados específicos para este ticker
        ativo_list = df_bens[df_bens['codigo_ativo'] == ticker].to_dict('records') if not df_bens.empty else []
        ativo = ativo_list[0] if ativo_list else {}
        subset_divs = df_divs[df_divs['codigo_ativo'] == ticker] if not df_divs.empty else pd.DataFrame()
        subset_vendas = df_vendas[df_vendas['codigo_ativo'] == ticker] if not df_vendas.empty else pd.DataFrame()
        subset_eventos = df_eventos[df_eventos['fk_ativo'] == fk_ativo_atual] if not df_eventos.empty else pd.DataFrame()

        with st.expander(f"📌 {ticker} - {nome_empresa} - {categoria} - {codigo_receita}"):
            tabela_bens = []
            v_ant_brl, v_atu_brl = fmt_brl(ativo.get('custo_anterior_brl', 0)), fmt_brl(ativo.get('custo_atual_brl', 0))
            # Define os campos básicos comuns a todos
            label_entidade = "FUNDO" if categoria in ['FII', 'FIAGRO', 'ETF'] else "EMPRESA"
            desc_principal = [f"TICKER: {ticker}", f"{label_entidade}: {nome_empresa}"]

            # Adiciona campos específicos por categoria
            if is_exterior or categoria in ['BDR']:
                pass # Stocks/REITs não levam CNPJ
            elif categoria in ['FII', 'FIAGRO', 'ETF']:
                desc_principal.append(f"CNPJ DO FUNDO: {cnpj_final}")
                desc_principal.append(f"ADM. DO FUNDO: {dados_base.get('adm_nome', 'NOME_ADM')} CNPJ: {dados_base.get('adm_cnpj', '00.000.000/0000-00')}")
            else:
                desc_principal.append(f"CNPJ: {cnpj_final}")

            # Adiciona as quantidades (comum a todos)
            desc_principal.extend([
                f"QUANTIDADE EM {ano_calendario-1}: {fmt_qtd(ativo.get('qtd_anterior', 0))}",
                f"QUANTIDADE EM {ano_calendario}: {fmt_qtd(ativo.get('qtd_atual', 0))}"
            ])

            tabela_bens.append({"🔍 Posição": f"📦 Quantidade de {ticker}", f"📅 {ano_calendario-1}": fmt_qtd(ativo.get('qtd_anterior', 0)), f"📅 {ano_calendario}": fmt_qtd(ativo.get('qtd_atual', 0))})
            
            if not is_exterior:
                desc_principal.extend([f"Custo de aquisição em {ano_calendario-1}: {v_ant_brl}", f"Custo de aquisição em {ano_calendario}: {v_atu_brl}"])
                v_ant_tab, v_atu_tab, label_custo = v_ant_brl, v_atu_brl, "💰 Situação / Custo BRL"
            else:
                v_ant_usd, v_atu_usd = fmt_usd(ativo.get('custo_anterior_usd', 0)), fmt_usd(ativo.get('custo_atual_usd', 0))
                desc_principal.extend([f"Custo de aquisição em {ano_calendario-1}: {v_ant_brl} ({v_ant_usd})", f"Custo de aquisição em {ano_calendario}: {v_atu_brl} ({v_atu_usd})"])
                v_ant_tab, v_atu_tab = f"{v_ant_brl} (💵 {v_ant_usd})", f"{v_atu_brl} (💵 {v_atu_usd})"
                label_custo = "🌎 Situação BRL (USD)"

            tabela_bens.append({"🔍 Posição": label_custo, f"📅 {ano_calendario-1}": v_ant_tab.replace("$", r"\$"), f"📅 {ano_calendario}": v_atu_tab.replace("$", r"\$")})

            pm_ant_tab = fmt_brl(ativo.get('pm_anterior_brl', 0)) if not is_exterior else f"{fmt_brl(ativo.get('pm_anterior_brl', 0))} (💵 {fmt_usd(ativo.get('pm_anterior_usd', 0))})"
            pm_atu_tab = fmt_brl(ativo.get('pm_atual_brl', 0)) if not is_exterior else f"{fmt_brl(ativo.get('pm_atual_brl', 0))} (💵 {fmt_usd(ativo.get('pm_atual_usd', 0))})"
            tabela_bens.append({"🔍 Posição": "📊 Preço Médio (PM)", f"📅 {ano_calendario-1}": pm_ant_tab.replace("$", r"\$"), f"📅 {ano_calendario}": pm_atu_tab.replace("$", r"\$")})

            desc_transito_list = []
            if not subset_divs.empty:
                df_tr = subset_divs[(subset_divs['credito_transito_atual_brl'] > 0) | (subset_divs['credito_transito_anterior_brl'] > 0)]
                for _, row_tr in df_tr.iterrows():
                    tipo_label = row_tr['tipo'].upper()
                    v_ant_tr, v_atu_tr = row_tr['credito_transito_anterior_brl'], row_tr['credito_transito_atual_brl']
                    tabela_bens.append({"🔍 Posição": f"⏳ Em Trânsito: {tipo_label}", f"📅 {ano_calendario-1}": f"{fmt_brl(v_ant_tr)}".replace("$", r"\$"), f"📅 {ano_calendario}": f"{fmt_brl(v_atu_tr)}".replace("$", r"\$")})
                    desc_transito_list.append(f"{ticker} // {tipo_label} CREDITADOS E NÃO PAGOS A RECEBER DE {nome_empresa} (CNPJ: {cnpj_final}) // Situação anterior: {fmt_brl(v_ant_tr)} // Situação atual: {fmt_brl(v_atu_tr)}")

            col_tab1, col_tab2 = st.columns(2)
            col_tab1.table(pd.DataFrame(tabela_bens).set_index("🔍 Posição"), border="horizontal", width="stretch")

            with col_tab2:
                v_bruto_ext_brl = subset_divs[subset_divs['tipo'] == "RENDIMENTO EXT"]['total_bruto_brl'].sum() if not subset_divs.empty else 0.0
                v_bruto_ext_usd = subset_divs[subset_divs['tipo'] == "RENDIMENTO EXT"]['total_bruto_usd'].sum() if not subset_divs.empty else 0.0
                v_imp_pago_ext_brl = subset_divs[subset_divs['tipo'] == "RENDIMENTO EXT"]['total_imposto_brl'].sum() if not subset_divs.empty else 0.0
                v_imp_pago_ext_usd = subset_divs[subset_divs['tipo'] == "RENDIMENTO EXT"]['total_imposto_usd'].sum() if not subset_divs.empty else 0.0
                l_venda_ext_brl = subset_vendas['lucro_brl'].sum() if not subset_vendas.empty else 0.0
                l_venda_ext_usd = subset_vendas['lucro_usd'].sum() if not subset_vendas.empty else 0.0

                if not is_exterior:
                    if not subset_divs.empty:
                        tabela_br_rend = []
                        for _, row in subset_divs.iterrows():
                            tipo, v_liq = row['tipo'].upper(), fmt_brl(row['total_liquido_brl'])
                            desc_principal.append(f"{tipo} LÍQUIDO: {v_liq}")
                            tabela_br_rend.append({"💸 Rendimento": tipo, "💰 Valor Líquido": v_liq.replace("$", r"\$"), "🏛️ Imposto Retido": fmt_brl(row.get('total_imposto_brl', 0)).replace("$", r"\$")})
                        st.table(pd.DataFrame(tabela_br_rend).set_index("💸 Rendimento"), border="horizontal", width="stretch")
                    if not subset_vendas.empty:
                        tabela_br_vendas = [{"📊 Operação Vendas": "🟢 LUCRO" if v['lucro_brl'] >= 0 else "🔴 PREJUÍZO", "Resultado BRL": fmt_brl(v['lucro_brl']).replace("$", r"\$")} for _, v in subset_vendas.iterrows()]
                        st.table(pd.DataFrame(tabela_br_vendas).set_index("📊 Operação Vendas"), border="horizontal", width="stretch")
                else:
                    res_cons_brl = v_bruto_ext_brl + l_venda_ext_brl
                    res_cons_usd = v_bruto_ext_usd + l_venda_ext_usd
                    desc_principal.append(f"RENDIMENTOS BRUTOS: {fmt_brl(v_bruto_ext_brl)} ({fmt_usd(v_bruto_ext_usd)}) // OPERAÇÃO VENDAS: {fmt_brl(l_venda_ext_brl)} ({fmt_usd(l_venda_ext_usd)}) // LUCRO OU PREJUÍZO: {fmt_brl(res_cons_brl)} ({fmt_usd(res_cons_usd)}) // IMPOSTO PAGO EXTERIOR: {fmt_brl(v_imp_pago_ext_brl)} ({fmt_usd(v_imp_pago_ext_usd)})")
                    
                    # TABELA CONSOLIDADA EM DUAS LINHAS
                    sinal = "🟢" if l_venda_ext_brl >= 0 else "🔴"
                    label_status = "LUCRO" if l_venda_ext_brl >= 0 else "PREJUÍZO"
                    
                    data_consolidada = [
                        {
                            "Status": sinal,
                            "📊 Op. Vendas": f"{fmt_brl(l_venda_ext_brl)}".replace("$", r"\$"),
                            "💸 Rend. Brutos": f"{fmt_brl(v_bruto_ext_brl)}".replace("$", r"\$"),
                            "🎯 Lucro/Prejuízo": f"{fmt_brl(res_cons_brl)}".replace("$", r"\$"),
                            "🏛️ Imposto Pago": f"{fmt_brl(v_imp_pago_ext_brl)}".replace("$", r"\$")
                        },
                        {
                            "Status": label_status,
                            "📊 Op. Vendas": f"💵 {fmt_usd(l_venda_ext_usd)}".replace("$", r"\$"),
                            "💸 Rend. Brutos": f"💵 {fmt_usd(v_bruto_ext_usd)}".replace("$", r"\$"),
                            "🎯 Lucro/Prejuízo": f"💵 {fmt_usd(res_cons_usd)}".replace("$", r"\$"),
                            "🏛️ Imposto Pago": f"💵 {fmt_usd(v_imp_pago_ext_usd)}".replace("$", r"\$")
                        }
                    ]
                    st.table(pd.DataFrame(data_consolidada).set_index("Status"), border="horizontal", width="stretch")

                subset_eventos = df_eventos[df_eventos['fk_ativo'] == fk_ativo_atual] if not df_eventos.empty else pd.DataFrame()
                if not subset_eventos.empty:
                    tabela_ev = []
                    for _, ev in subset_eventos.iterrows():
                        tipo_ev, at_gerado = ev['tipo'].upper(), ev.get('ativo_gerado', 'N/A')
                        v_brl, v_usd = ev.get('preco_op_brl', 0), ev.get('preco_op_usd', 0)
                        if is_exterior:
                            desc_principal.append(f"{tipo_ev} DE {at_gerado} ALTERADO CUSTO DE AQUISIÇÃO EM {fmt_brl(v_brl)} ({fmt_usd(v_usd)})")
                            val_tabela = f"{fmt_brl(v_brl)} (💵 {fmt_usd(v_usd)})"
                        else:
                            desc_principal.append(f"{tipo_ev} DE {at_gerado} ALTERADO CUSTO DE AQUISIÇÃO EM {fmt_brl(v_brl)}")
                            val_tabela = fmt_brl(v_brl)
                        tabela_ev.append({"📝 Evento": tipo_ev, "📦 Ativo Gerado": at_gerado, "📅 Data": pd.to_datetime(ev['data_op_com']).strftime('%d/%m/%Y'), "💰 Custo Total": val_tabela.replace("$", r"\$")})
                    st.table(pd.DataFrame(tabela_ev).set_index("📝 Evento"), border="horizontal", width="stretch")

            st.caption("📋 **Copiar Discriminação Principal (Bens e Direitos):**")
            # --- CONVERSÃO PARA MAIÚSCULO E LIMPEZA ---
            texto_final = " // ".join(desc_principal).upper()
            texto_limpo = texto_final.replace("💵 ", "").replace("📦 ", "").replace("💰 ", "").replace("🟢 ", "").replace("🔴 ", "")
            st.code(texto_limpo, wrap_lines=True)
            
            if desc_transito_list:
                st.caption("⚠️ **Copiar Item de Créditos em Trânsito - Grupo 99 - Cod. 07 - Pais. 105:**")
                for item_tr in desc_transito_list:
                    st.code(item_tr.upper(), wrap_lines=True)
else:
    st.info("Clique em 'Carregar Dados' para iniciar.")