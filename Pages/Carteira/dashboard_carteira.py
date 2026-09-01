import streamlit as st
import pandas as pd
from plotly import graph_objects as go
import plotly.express as px
from Pages.utils.request_api import buscar_carteira_api, ApiRequestError
from Pages.utils.components import componente_seletor_categorias, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_ativo_visual, tratar_dados_carteira_raw, formatar_numero_para_br_str


# ==============================================================================
# 🎯 1. CONTROLE DE ESTADOS E NAVEGAÇÃO DA SESSÃO
# ==============================================================================
if 'go_to_movimentacao' not in st.session_state:
    st.session_state['go_to_movimentacao'] = False

if 'page_movimentacao' not in st.session_state:
    st.session_state['page_movimentacao'] = {}

# Processador da navegação no fluxo principal (evita erro de switch_page dentro do callback)
if st.session_state['go_to_movimentacao']:
    st.session_state['go_to_movimentacao'] = False
    st.switch_page("Pages/Carteira/movimentacao.py")

# ==============================================================================
# 📊 3. COMPONENTES DE VISUALIZAÇÃO (KPIS, GRÁFICOS, TABELA)
# ==============================================================================
def renderizar_kpis(dados: list, moeda: str):
    """Exibe as métricas de topo em cards flexíveis e 100% responsivos."""
    sufixo = "_brl" if moeda == "BRL" else "_usd"
    simbolo = "R$" if moeda == "BRL" else "$"

    if not dados:
        return

    # 1. Cálculos
    patrimonio = sum(float(item.get(f"valor_mercado{sufixo}", 0.0) or 0.0) for item in dados)
    custo_total = sum(float(item.get(f"custo{sufixo}", 0.0) or 0.0) for item in dados)
    lucro_capital = sum(float(item.get(f"lucro{sufixo}", 0.0) or 0.0) for item in dados)
    renda_mensal_est = sum(float(item.get(f"renda{sufixo}", 0.0) or 0.0) for item in dados)
    retorno_total = sum(float(item.get(f"lucro_div{sufixo}", 0.0) or 0.0) for item in dados)

    pct_lucro = ((lucro_capital / custo_total) * 100) if custo_total > 0 else 0.0
    pct_retorno_total = ((retorno_total / custo_total) * 100) if custo_total > 0 else 0.0
    pct_renda_mensal_est = ((renda_mensal_est / custo_total) * 100) if custo_total > 0 else 0.0

    ativos_unicos = set()
    for item in dados:
        # Tenta extrair o ticker usando as chaves mais comuns
        ticker = item.get("ativo") or item.get("codigo_ativo") or item.get("ticker") or item.get("codigo")
        if ticker:
            ativos_unicos.add(str(ticker).strip().upper())
    
    # Se não encontrar a chave do ticker, assume o tamanho da lista como fallback
    qtde_ativos = len(ativos_unicos) if ativos_unicos else len(dados)
    # 2. Cores e Sinais
    cor_lucro = "#2e7d32" if pct_lucro >= 0 else "#d32f2f"
    sinal_lucro = "+" if pct_lucro >= 0 else ""

    cor_retorno = "#2e7d32" if pct_retorno_total >= 0 else "#d32f2f"
    sinal_retorno = "+" if pct_retorno_total >= 0 else ""

    # 3. HTML com Flexbox Responsivo
    html_kpis = f"""
    <style>
        .kpi-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            width: 100%;
            box-sizing: border-box;
            margin-top: 0px; 
            margin-bottom: 0px;
        }}
        .kpi-card {{
            flex: 1 1 140px; /* Cresce, encolhe e tem largura mínima flexível */
            background: rgba(128, 128, 128, 0.05);
            border: 1px solid rgba(128, 128, 128, 0.15);
            border-radius: 8px;
            padding: 8px 10px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-sizing: border-box;
            min-width: 0; /* Previne overflow de texto */
        }}
        .kpi-label {{
            font-size: 0.68rem;
            font-weight: 600;
            text-transform: uppercase;
            color: gray;
            letter-spacing: 0.3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 6px;
        }}
        .kpi-value-container {{
            display: flex;
            flex-direction: column; /* Força os elementos a ficarem empilhados */
            align-items: flex-start; /* Alinha o valor e a porcentagem à esquerda */
            gap: 4px; /* Espaçamento vertical entre o valor e o badge */
        }}
        .kpi-value {{
            font-size: 0.88rem;
            font-weight: 700;
            white-space: nowrap;
        }}
        .kpi-badge {{
            font-size: 0.68rem;
            font-weight: 600;
            padding: 1px 6px;
            border-radius: 4px;
            white-space: nowrap;
            width: fit-content; /* Garante que a tag fique do tamanho exato do texto */
        }}
    </style>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Patrimônio Total</div>
            <div class="kpi-value">{simbolo} {formatar_numero_para_br_str(round(patrimonio, 2))}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Custo Investido</div>
            <div class="kpi-value">{simbolo} {formatar_numero_para_br_str(round(custo_total, 2))}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Ganho de Capital</div>
            <div class="kpi-value-container">
                <span class="kpi-value">{simbolo} {formatar_numero_para_br_str(round(lucro_capital, 2))}</span>
                <span class="kpi-badge" style="color: {cor_lucro}; background: {cor_lucro}18;">
                    {sinal_lucro}{formatar_numero_para_br_str(round(pct_lucro, 2))}%
                </span>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Renda Mensal Est.</div>
            <div class="kpi-value-container">
                <span class="kpi-value">{simbolo} {formatar_numero_para_br_str(round(renda_mensal_est, 2))}</span>
                <span class="kpi-badge" style="color: #0288d1; background: #0288d118;">
                    {formatar_numero_para_br_str(round(pct_renda_mensal_est, 2))}%
                </span>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Retorno Total</div>
            <div class="kpi-value-container">
                <span class="kpi-value">{simbolo} {formatar_numero_para_br_str(round(retorno_total, 2))}</span>
                <span class="kpi-badge" style="color: {cor_retorno}; background: {cor_retorno}18;">
                    {sinal_retorno}{formatar_numero_para_br_str(round(pct_retorno_total, 2))}%
                </span>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Qtd. de Ativos</div>
            <div class="kpi-value">{qtde_ativos}</div>
        </div>
    </div>
    """

    st.markdown(html_kpis, unsafe_allow_html=True)

def create_sankey_chart(df: pd.DataFrame, coluna_metrica: str = "%"):
    """Cria o gráfico de Sankey com ordenação hierárquica (em cascata) para evitar linhas trançadas.

    Garante uso do fk_ativo para nós únicos.
    """
    if df is None or df.empty:
        return None

    df_chart = df.copy()

    # 🛠️ [ALTERAÇÃO] Mapeamento de colunas incluindo suporte a fk_ativo
    col_map = {
        "Grupo": "grupo",
        "Subgrupo": "subgrupo",
        "Ativo": "codigo_ativo",
        "Ativos": "codigo_ativo",
        "Ticker": "codigo_ativo",
        "ticker": "codigo_ativo",
    }
    df_chart.rename(
        columns={k: v for k, v in col_map.items() if k in df_chart.columns},
        inplace=True,
    )

    # 🛠️ [ALTERAÇÃO CRÍTICA] Fallback dinâmico para a coluna métrica
    if coluna_metrica not in df_chart.columns:
        candidatos = ["%", "Peso", "sugestao_aporte", "val_num", "Nota"]
        encontrado = next((c for c in candidatos if c in df_chart.columns), None)
        if encontrado:
            coluna_metrica = encontrado
        else:
            return None

    # Garantia de colunas obrigatórias
    for col in ["grupo", "subgrupo", "codigo_ativo"]:
        if col not in df_chart.columns:
            df_chart[col] = "GERAL"

    # 🛠️ [ALTERAÇÃO CRÍTICA] Preservação do fk_ativo para identificação única do nó
    if "fk_ativo" not in df_chart.columns:
        if "id" in df_chart.columns:
            df_chart["fk_ativo"] = df_chart["id"]
        else:
            df_chart["fk_ativo"] = df_chart["codigo_ativo"]
    else:
        df_chart["fk_ativo"] = df_chart["fk_ativo"].fillna(df_chart["codigo_ativo"])

    df_chart["fk_ativo"] = df_chart["fk_ativo"].astype(str)

    # Sanitização de Texto Visual
    df_chart["grupo"] = (
        df_chart["grupo"].fillna("GERAL").astype(str).str.strip().str.upper()
    )
    df_chart["subgrupo"] = (
        df_chart["subgrupo"].fillna("GERAL").astype(str).str.strip().str.upper()
    )
    df_chart["codigo_ativo"] = (
        df_chart["codigo_ativo"]
        .fillna("N/A")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # --- 2. Limpeza e Conversão Numérica ---
    if df_chart[coluna_metrica].dtype == object:
        df_chart[coluna_metrica] = (
            df_chart[coluna_metrica]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )

    df_chart["val_num"] = pd.to_numeric(
        df_chart[coluna_metrica], errors="coerce"
    ).fillna(0.0)

    # Normalização dos pesos (%)
    soma_total = df_chart["val_num"].sum()
    if soma_total <= 0:
        return None

    df_chart["pct"] = (df_chart["val_num"] / soma_total) * 100.0
    df_chart = df_chart[df_chart["pct"] > 0]

    if df_chart.empty:
        return None

    col_pct = "pct"

    # --- 3. Totais Agregados Hierárquicos ---
    totais_grupo = df_chart.groupby("grupo")[col_pct].sum().to_dict()
    totais_subgrupo = (
        df_chart.groupby(["grupo", "subgrupo"])[col_pct].sum().to_dict()
    )

    # 🛠️ [ALTERAÇÃO CRÍTICA] Agrupamento por fk_ativo garantindo unicidade no nó do ativo
    totais_ativo = (
        df_chart.groupby(["grupo", "subgrupo", "fk_ativo", "codigo_ativo"])[col_pct]
        .sum()
        .to_dict()
    )

    # --- 4. Ordenação Hierárquica sem Colisão ---
    grupos_unicos = sorted(
        df_chart["grupo"].unique(), key=lambda g: totais_grupo[g], reverse=True
    )

    subgrupos_chaves = []
    for g in grupos_unicos:
        df_g = df_chart[df_chart["grupo"] == g]
        subs = sorted(
            df_g["subgrupo"].unique(),
            key=lambda s: totais_subgrupo.get((g, s), 0),
            reverse=True,
        )
        for s in subs:
            subgrupos_chaves.append((g, s))

    # 🛠️ [ALTERAÇÃO] Construção de chave única combinando g, s, fk_ativo e codigo_ativo
    ativos_chaves = []
    for g, s in subgrupos_chaves:
        df_s = df_chart[
            (df_chart["grupo"] == g) & (df_chart["subgrupo"] == s)
        ]
        # Pega pares únicos de (fk_ativo, codigo_ativo)
        pares_ativos = df_s[["fk_ativo", "codigo_ativo"]].drop_duplicates().to_dict("records")
        sorted_ativos = sorted(
            pares_ativos,
            key=lambda item: totais_ativo.get((g, s, item["fk_ativo"], item["codigo_ativo"]), 0),
            reverse=True,
        )
        for item in sorted_ativos:
            ativos_chaves.append((g, s, item["fk_ativo"], item["codigo_ativo"]))

    # --- 5. Cores e Estilização ---
    PALETA_CORES = [
        "#1F77B4",
        "#FF7F0E",
        "#2CA02C",
        "#D62728",
        "#9467BD",
        "#8C564B",
        "#E377C2",
        "#7F7F7F",
        "#BCBD22",
        "#17BECF",
    ]

    cor_por_grupo = {
        g: PALETA_CORES[i % len(PALETA_CORES)]
        for i, g in enumerate(grupos_unicos)
    }

    def hex_to_rgba(hex_str: str, alpha: float = 0.25) -> str:
        hex_str = hex_str.lstrip("#")
        r, g, b = tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha})"

    def fmt_pct(val: float) -> str:
        return f"{val:.2f}".replace(".", ",")

    # --- 6. Mapeamento de Nós com Chaves Únicas ---
    # 🛠️ [ALTERAÇÃO] Uso do fk_ativo na identificação do nó do ativo
    node_keys = (
        [f"g_{g}" for g in grupos_unicos]
        + [f"s_{g}|{s}" for g, s in subgrupos_chaves]
        + [f"a_{g}|{s}|{fk}" for g, s, fk, _ in ativos_chaves]
    )

    node_map = {key: i for i, key in enumerate(node_keys)}

    # 🛠️ [ALTERAÇÃO] O código do ativo (Ticker) continua sendo exibido no rótulo visual
    labels_exibicao = (
        [
            f"{g.title()} ({fmt_pct(totais_grupo[g])}%)"
            for g in grupos_unicos
        ]
        + [
            f"{s.title()} ({fmt_pct(totais_subgrupo[(g, s)])}%)"
            for g, s in subgrupos_chaves
        ]
        + [
            f"{ticker.upper()} ({fmt_pct(totais_ativo[(g, s, fk, ticker)])}%)"
            for g, s, fk, ticker in ativos_chaves
        ]
    )

    node_colors = (
        [cor_por_grupo[g] for g in grupos_unicos]
        + [cor_por_grupo[g] for g, s in subgrupos_chaves]
        + [cor_por_grupo[g] for g, s, _, _ in ativos_chaves]
    )

    # --- 7. Conexões (Links) ---
    sources, targets, values, link_colors = [], [], [], []

    # Grupo -> Subgrupo
    for g, s in subgrupos_chaves:
        val = totais_subgrupo[(g, s)]
        sources.append(node_map[f"g_{g}"])
        targets.append(node_map[f"s_{g}|{s}"])
        values.append(val)
        link_colors.append(hex_to_rgba(cor_por_grupo[g], 0.35))

    # 🛠️ [ALTERAÇÃO] Subgrupo -> Ativo mapeado com fk_ativo
    for g, s, fk, ticker in ativos_chaves:
        val = totais_ativo[(g, s, fk, ticker)]
        sources.append(node_map[f"s_{g}|{s}"])
        targets.append(node_map[f"a_{g}|{s}|{fk}"])
        values.append(val)
        link_colors.append(hex_to_rgba(cor_por_grupo[g], 0.20))

    # --- 8. Renderização no Plotly ---
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="freeform",
                textfont=dict(
                    size=11, color="#1A1A1A", family="sans-serif"
                ),
                node=dict(
                    pad=12,
                    thickness=16,
                    line=dict(color="rgba(0,0,0,0.15)", width=0.5),
                    label=labels_exibicao,
                    color=node_colors,
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color=link_colors,
                ),
            )
        ]
    )

    fig.update_layout(
        margin=dict(b=12, t=30, l=30, r=30),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=650,
    )

    return fig

def renderizar_graficos(dados: list, moeda: str):
    """Renderiza a distribuição e análise dinâmica (converte para DF apenas para o Plotly)."""
    if not dados:
        st.info("Nenhum dado disponível para renderização gráfica.")
        return

    df = pd.DataFrame(dados)
    sufixo = "_brl" if moeda == "BRL" else "_usd"
    simbolo = "R$" if moeda == "BRL" else "$"

    # --- CORREÇÃO: Garante tipo numérico nas colunas que usaremos para filtro e gráficos ---
    colunas_numericas = [
        f"valor_mercado{sufixo}", f"custo{sufixo}", f"valor_plan{sufixo}",
        f"lucro_p{sufixo}", f"lucro_div_p{sufixo}", f"aporte_p{sufixo}", "quant"
    ]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    # ------------------------------------------------------------------------------------

    col_esq, col_dir = st.columns([0.45, 0.55])

    # 1. ESQUERDA: Alocação (Sunburst / Pizza)
    with col_esq:
        col_valor_mkt = f"valor_mercado{sufixo}"
        df_graficos = df[df[col_valor_mkt] > 0].copy() if col_valor_mkt in df.columns else pd.DataFrame()

        if not df_graficos.empty:
            col_custo = f"custo{sufixo}" if f"custo{sufixo}" in df_graficos.columns else "custo"

            with st.container(horizontal=True):
                usar_custo = st.toggle("Ver por Custo", key="toggle_metrica_custo")
                tipo_grafico = st.selectbox(
                    "Visão:",
                    options=["Sunburst (Completo)", "Diagrama", "Heatmap (Treemap)","Heatmap (Lucros/Prejuízos)", "Grupo", "Subgrupo", "Ativos", "País"],
                    key="select_tipo_grafico_alocacao",
                    label_visibility="collapsed",
                )

            coluna_metrica = col_custo if usar_custo and col_custo in df_graficos.columns else col_valor_mkt
            col_cat, col_setor, col_ativo, col_pais, col_qt = "grupo", "subgrupo", "codigo_ativo", "moeda", "quant"

            if tipo_grafico == "Sunburst (Completo)":
                path_cols = [c for c in [col_cat, col_setor, col_ativo] if c in df_graficos.columns]
                fig = px.sunburst(
                    df_graficos,
                    path=path_cols,
                    values=coluna_metrica,
                    color=col_cat if col_cat in df_graficos.columns else None,
                    color_discrete_sequence= ["#FF4B4B", "#0068C9", "#83C9FF", "#FF8700", "#29B09D", "#7D44CF", "#F24C3D"]
                )
                fig.update_traces(textinfo="label+percent entry")
                fig.update_layout(margin=dict(b=0, t=10, l=0, r=0), plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, width='stretch')

            elif tipo_grafico =="Diagrama":
                fig = create_sankey_chart(df_graficos, coluna_metrica)
                st.plotly_chart(fig, width="stretch")
            elif tipo_grafico == "Heatmap (Lucros/Prejuízos)":
                col_lucro_pct = f"lucro_p{sufixo}"
                if col_lucro_pct in df_graficos.columns:
                    path_cols = [
                        c
                        for c in [col_cat, col_setor, col_ativo]
                        if c in df_graficos.columns
                    ]

                    # Criar texto formatado estilo Finviz: TICKER + PERC (ex: MSFT \n +1.62%)
                    df_graficos["texto_lucro_pct"] = df_graficos[col_lucro_pct].apply(lambda x: f"{x * 100:+.2f}" if pd.notnull(x) else "")

                    fig = px.treemap(
                        df_graficos,
                        path=path_cols,
                        values=coluna_metrica,  # Tamanho do bloco = Tamanho da Posição
                        color=col_lucro_pct,  # Cor do bloco = Lucro %
                        custom_data=["texto_lucro_pct"], # Passa o valor numérico para o customdata
                        range_color=[ -1.0, 1.0,],  # 👈 TRAVA o mínimo em -1 e o máximo em +1
                        color_continuous_scale=[
                            [0.0, "#801213"],  # Cor no limite -1.0 (Vermelho Escuro)
                            [0.25, "#F06A6A"],  # Cor no ponto -0.5 (Vermelho Claro)
                            [0.5, "#CCCCCC"],  # Cor no ponto  0.0 (Cinza Neutro)
                            [0.75, "#38A368"],  # Cor no ponto +0.5 (Verde Claro)
                            [1.0, "#085D34"],  # Cor no limite +1.0 (Verde Escuro)
                        ],
                        color_continuous_midpoint=0,  # Garante que 0% seja exatamente o #CCCCCC
                    )

                    # Ajusta os textos exibidos dentro de cada bloco
                    fig.update_traces(
                        texttemplate="%{label}<br>%{customdata[0]:+.2f}%",  # Mostra o nome do grupo/ticker e o %
                        hovertemplate="<b>%{label}</b><br>Tamanho: %{value:,.2f}<br>Resultado: %{customdata[0]:+.2f}%<extra></extra>",
                    )

                    # Oculta a barra de cor lateral para ficar mais limpo estilo Finviz
                    fig.update_layout(
                        coloraxis_showscale=False,
                        margin=dict(b=10, t=10, l=10, r=10),
                        plot_bgcolor="rgba(0,0,0,0)",
                    )

                    st.plotly_chart(fig, width="stretch")
                else:
                    st.warning(
                        f"A coluna de rentabilidade **{col_lucro_pct}** não foi encontrada no DataFrame."
                    )
            elif tipo_grafico == "Heatmap (Treemap)":
                path_cols = [ c for c in [col_cat, col_setor, col_ativo] if c in df_graficos.columns ]
                fig = px.treemap(
                    df_graficos,
                    path=path_cols,
                    values=coluna_metrica,
                    color=col_cat if col_cat in df_graficos.columns else None,
                    color_discrete_sequence= ["#FF4B4B", "#0068C9", "#83C9FF", "#FF8700", "#29B09D", "#7D44CF", "#F24C3D"]
                )
                fig.update_traces(textinfo="label+value+percent entry")
                fig.update_layout(
                    margin=dict(b=0, t=10, l=0, r=0), plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig, width="stretch")

            else:
                mapa_colunas = {
                    "Grupo": (col_cat, "Distribuição por Categoria"),
                    "Subgrupo": (col_setor, "Distribuição por Setor"),
                    "Ativos": (col_ativo, "Distribuição por Ativo"),
                    "País": (col_pais, "Distribuição por País"),
                }
                col_target, titulo_grafico = mapa_colunas.get(tipo_grafico, (None, None))

                if col_target and col_target in df_graficos.columns:
                    hover_kwargs = {"hover_data": [col_qt]} if col_qt in df_graficos.columns else {}
                    labels_kwargs = {"labels": {col_qt: "Quantidade"}} if col_qt in df_graficos.columns else {}

                    fig = px.pie(
                        df_graficos,
                        values=coluna_metrica,
                        names=col_target,
                        title=titulo_grafico,
                        hole=0.2,
                        **hover_kwargs,
                        **labels_kwargs,
                    )
                    fig.update_traces(textposition="inside", textinfo="percent+label")
                    fig.update_layout(
                        title={"y": 0.95, "x": 0.5, "xanchor": "center", "yanchor": "top"},
                        margin=dict(b=10, t=40, l=10, r=10),
                    )
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.warning(f"Coluna para **{tipo_grafico}** não encontrada.")
        else:
            st.info("Nenhum valor patrimonial acumulado para exibir.")

    # 2. DIREITA: Análise Comparativa Dinâmica (Duplo Eixo Y)
    with col_dir:
        col_qt = "quant" if "quant" in df.columns else "quantidade"
        df_plot = df[df[col_qt] > 0].copy() if col_qt in df.columns else df.copy()

        if not df_plot.empty:
            def get_col(nome_base):
                if f"{nome_base}{sufixo}" in df_plot.columns:
                    return f"{nome_base}{sufixo}"
                return nome_base if nome_base in df_plot.columns else None
            opcoes_metricas = opcoes_metricas = {
                                                    "Custo": {"col": get_col("custo"), "eixo": "y1", "tipo": "moeda", "cor": "#ff7f0e"},
                                                    "Patrimônio": {"col": get_col("valor_mercado"), "eixo": "y1", "tipo": "moeda", "cor": "#1f77b4"},
                                                    "Planejado": {"col": get_col("valor_plan"), "eixo": "y1", "tipo": "moeda", "cor": "#9467bd"},
                                                    "Lucro %": {"col": get_col("lucro_p"), "eixo": "y2", "tipo": "pct", "cor_pos": "#2ca02c", "cor_neg": "#d62728"},
                                                    "Lucro+Div %": {"col": get_col("lucro_div_p"), "eixo": "y2", "tipo": "pct", "cor_pos": "gray", "cor_neg": "IndianRed"},
                                                    "Aporte %": {"col": get_col("aporte_p"), "eixo": "y2", "tipo": "pct", "cor_pos": "#009688", "cor_neg": "#FF9800"},
                                                }

            opcoes_disponiveis = [nome for nome, cfg in opcoes_metricas.items() if cfg["col"] is not None]

            metricas_selecionadas = st.multiselect("Métricas:", options=opcoes_disponiveis,
                                                                default=[m for m in ["Lucro %"] if m in opcoes_disponiveis],
                                                                key="multiselect_metricas_grafico",
                                                                label_visibility="collapsed",
                                                            )

            if metricas_selecionadas:
                fig_dir = go.Figure()
                col_ativo = "codigo_ativo" if "codigo_ativo" in df_plot.columns else "ativo"
                eixos_usados = set()
                for metrica in metricas_selecionadas:
                    cfg = opcoes_metricas[metrica]
                    col_nome, eixo = cfg["col"], cfg["eixo"]
                    eixos_usados.add(eixo)
                    y_vals = df_plot[col_nome]

                    if cfg["tipo"] == "moeda":
                        fig_dir.add_trace(
                            go.Bar(
                                x=df_plot[col_ativo],
                                y=y_vals,
                                name=metrica,
                                yaxis="y",
                                marker=dict(color=cfg["cor"]),
                            )
                        )
                    else:
                        # Aplica a cor positiva ou negativa mapeada no próprio dicionário da métrica
                        cor_pos = cfg.get("cor_pos", "#2ca02c")
                        cor_neg = cfg.get("cor_neg", "#d62728")
                        cores_barras = y_vals.apply(lambda val: cor_pos if val >= 0 else cor_neg)

                        fig_dir.add_trace(
                            go.Bar(
                                x=df_plot[col_ativo],
                                y=y_vals,
                                name=metrica,
                                yaxis="y2",
                                textposition="auto",
                                texttemplate="%{value:.2%}",
                                textfont=dict(color="black"),
                                marker=dict(color=cores_barras, opacity=0.85, line=dict(color="rgba(0,0,0,0.3)", width=1)),
                            )
                        )

                layout_y1 = dict(title=dict(text=f"Valor ({simbolo})"), side="left", tickformat=",.2f", showgrid=True)
                layout_y2 = (
                    dict(title=dict(text="%"), side="right", overlaying="y", tickmode="sync", tickformat=".2%", showgrid=False)
                    if "y2" in eixos_usados
                    else None
                )

                fig_dir.update_layout(
                    barmode="group",
                    separators=",.",
                    yaxis=layout_y1,
                    yaxis2=layout_y2,
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"),
                    margin=dict(b=30, t=10, l=10, r=10),
                    height=350,
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_dir, width='stretch')
            else:
                st.warning("Selecione ao menos uma métrica.")
        else:
            st.info("Nenhum ativo com posição ativa para exibir no gráfico.")

def renderizar_tabela_resumo(dados: list, moeda: str):
    """Exibe a tabela detalhada invocando o componente genérico."""
    st.subheader("📋 Posição Detalhada da Carteira")

    def ver_detalhes(registro: dict):
        if registro:
            ativo_selecionado = registro.get('fk_ativo') or registro.get('codigo_ativo')
            
            if 'page_movimentacao' not in st.session_state:
                st.session_state['page_movimentacao'] = {}
            
            st.session_state['page_movimentacao']['ativo_original'] = ativo_selecionado
            st.session_state['page_movimentacao']['ativo_selecionado'] = ativo_selecionado
            st.session_state['go_to_movimentacao'] = True

    def destacar_lucros_negativos(df, **kwargs):
        colunas_lucro = [
            "lucro", "lucro_brl", "lucro_usd",
            "lucro_p", "lucro_p_brl", "lucro_p_usd",
            "lucro_div", "lucro_div_brl", "lucro_div_usd",
            "lucro_div_p", "lucro_div_p_brl", "lucro_div_p_usd",
        ]
        estilo_negativo = "color: #D9381E; background-color: rgba(217, 56, 30, 0.08);"
        estilo_positivo = "color: #2E7D32; background-color: rgba(46, 125, 50, 0.08);"
        styles = pd.DataFrame("", index=df.index, columns=df.columns)

        def obter_estilo(val):
            if pd.notnull(val) and isinstance(val, (int, float)):
                if val < 0:
                    return estilo_negativo
                elif val > 0:
                    return estilo_positivo
            return ""

        for col in df.columns:
            if col in colunas_lucro:
                styles[col] = df[col].apply(obter_estilo)

        return styles

    CONFIG_CARTEIRA = {
        "fk_ativo_visual": {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo"))},
        "nome":            {"titulo": "📌 Nome", "tipo": "text"},
        "setor":           {"titulo": "🏢 Setor", "tipo": "text"},
        "quant":           {"titulo": "🔢 Qtd.", "tipo": "number", "precisao": 6},
        "valor_mercado":   {"titulo": "💰 Patrimônio", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "custo":           {"titulo": "💵 Custo Total", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "peso":            {"titulo": "⚖️ Peso Ideal", "tipo": "number", "precisao": 2},
        "valor_plan":      {"titulo": "🎯 Meta", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "aporte":          {"titulo": "📥 Aporte", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "aporte_p":        {"titulo": "📐 Aporte (%)", "tipo": "percent", "multi_moeda": True, "precisao": 2},
        "lucro":           {"titulo": "📈 Lucro", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "lucro_p":         {"titulo": "📊 Lucro (%)", "tipo": "percent", "multi_moeda": True, "precisao": 2},
        "div_liq":         {"titulo": "💸 Proventos", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "lucro_div":       {"titulo": "🚀 Retorno Total", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "lucro_div_p":     {"titulo": "🔥 Retorno Total (%)", "tipo": "percent", "multi_moeda": True, "precisao": 2},
        "renda":           {"titulo": "🗓️ Renda Est./Mês", "tipo": "currency", "multi_moeda": True, "precisao": 2},
        "dy":              {"titulo": "⚡ DY", "tipo": "percent", "precisao": 2},
    }

    COLUNAS_RESUMIDAS = ["fk_ativo_visual", "setor", "quant", "valor_mercado", "custo", "lucro", "div_liq", "lucro_div", "renda"]

    exibir_tabela_generica(
                            dados=dados,
                            config_colunas=CONFIG_CARTEIRA,
                            colunas_resumidas=COLUNAS_RESUMIDAS,
                            callback_edit=None,
                            callback_deletar=None,
                            botoes_acao=[{
                                            "label": "",
                                            "icone": "🔍",
                                            "callback": ver_detalhes,
                                            "somente_unico": True,
                                            "help": "Ver detalhes de movimentações"
                                        }],
                            callback_estilo=destacar_lucros_negativos,
                            chave_tabela="carteira",
                            suporta_moeda=True
                        )

# ==============================================================================
# 🚀 4. EXECUÇÃO PRINCIPAL DA PÁGINA
# ==============================================================================
col_t, col_bt_obj, col_bt_div, cal_bt_mov = st.columns([0.7, 0.15, 0.15, 0.15], vertical_alignment="center")

if col_bt_obj.button("🎯 Objetivos 🌳", key="btn_objetivos", width="stretch"):
    st.switch_page("Pages/Aporte/planejar_guiado.py")
if col_bt_div.button("💰 Dividendos", key="btn_dividendos", width="stretch"):
    st.switch_page("Pages/Dividendos_usuarios/dividendos_grafico.py")
if cal_bt_mov.button("📜 Movimentações", key="btn_movimentacoes", width="stretch"):
    st.switch_page("Pages/Carteira/movimentacao.py")

col_t.title("📊 Dashboard - Overview da Carteira")
# Busca e tratamento com Cache em Session State (Evita chamadas repetidas ao backend)
if 'dados_carteira_cache' not in st.session_state:
    try:
        dados_raw = buscar_carteira_api()
        st.session_state['dados_carteira_cache'] = tratar_dados_carteira_raw(dados_raw)
    except ApiRequestError as e:
        st.error(f"❌ {e.message}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Erro inesperado ao carregar dados da carteira: {type(e).__name__}: {e}")
        st.stop()

dados_carteira = st.session_state['dados_carteira_cache']

if not dados_carteira:
    st.warning("Nenhum dado encontrado para a carteira.")
    st.stop()

# Barra de Filtros
c_filtros, kips = st.columns([0.4, 0.6], vertical_alignment="top")

with c_filtros.container(border=True, height='stretch'):
    categorias_selecionadas = componente_seletor_categorias(
        pd.DataFrame(dados_carteira), 
        chave_session="dash_filtro_categorias"
    )
    with st.container(horizontal=True, vertical_alignment="center"):
        exibir_usd = st.toggle("💵 Exibir em USD", value=False, key="toggle_moeda_carteira")
        ocultar_zerados = st.checkbox("Ocultar Posições Zeradas", value=True)


moeda_selecionada = "USD" if exibir_usd else "BRL"

# Filtragem nativa em listas de dicionários
dados_filtrados = list(dados_carteira)

if ocultar_zerados:
    dados_filtrados = [item for item in dados_filtrados if float(item.get("quant", 0) or 0) > 0]

if categorias_selecionadas:
    dados_filtrados = [item for item in dados_filtrados if item.get("categoria") in categorias_selecionadas]

# Renderização da Interface
with kips.container(border=True):
    renderizar_kpis(dados_filtrados, moeda_selecionada)
    st.write("")

with st.expander("Gráficos", expanded=True):
    renderizar_graficos(dados_filtrados, moeda_selecionada)

renderizar_tabela_resumo(dados_filtrados, moeda_selecionada)