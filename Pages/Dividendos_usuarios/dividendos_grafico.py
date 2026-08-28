from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.config as config
import plotly.express as px
from Pages.utils.request_api import ApiRequestError, obter_dividendos_usuarios_agregados_api

#===============================================================================
# CONFIGURAÇÕES DE ESTADO DA PÁGINA
# ==============================================================================
PAGE_KEY = "page_dividendos"

st.session_state.setdefault(PAGE_KEY, {})
state: Dict[str, Any] = st.session_state[PAGE_KEY]

MAPA_AGRUPAMENTOS: Dict[str, Optional[str]] = {
    "Completo": None,
    "Grupo": "grupo",
    "Categoria": "categoria",
}


def numero_padrao(numero: float) -> str:
    """Formata números para o padrão de moeda brasileiro (1.000,00)."""
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def carregar_dados_agregados( periodo: str = "12M",
                                dt_inicio: Optional[date] = None,
                                dt_fim: Optional[date] = None,
                                agrupar_por: Optional[str] = None ) -> List[dict]:
                                
    """Busca os dividendos agregados no backend FastAPI."""
    try:
        return (
            obter_dividendos_usuarios_agregados_api(
                periodo_opcao=periodo,
                agrupar_por="DATA_COM" if agrupar_por =="Data Com" else "DATA_PAG",
                data_inicio=str(dt_inicio) if dt_inicio else None,
                data_fim=str(dt_fim) if dt_fim else None,
                apenas_aceitos=True,
            )
            or []
        )
    except ApiRequestError as e:
        st.error(f"Erro ao carregar dividendos agregados: {e.message}")
        return []


def renderizar_matriz_proventos(
    df_filtered: pd.DataFrame,
    valor_liq_col: str,
    moeda_simbolo: str,
) -> None:
    """ Renderiza a matriz de proventos consumindo exclusivamente as CSS Variables nativas do Streamlit."""
    if df_filtered.empty:
        st.warning("Sem dados suficientes para montar a matriz de proventos.")
        return

    # ==============================================================================
    # 🎨 CONFIGURAÇÃO DE CORES (LEITURA DO TOML)
    # ==============================================================================
    cor_primaria_toml = config.get_option('theme.primaryColor')
    c1 = cor_primaria_toml or "#1877F2"

    def hex_to_rgba(hex_code: str, alpha: float) -> str:
        hex_code = hex_code.lstrip("#")
        r, g, b = tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r}, {g}, {b}, {alpha})"

    # Degradê de opacidade (funciona no Light e Dark)
    bg_v1, txt_v1 = hex_to_rgba(c1, 0.15), "var(--text-color)"
    bg_v2, txt_v2 = hex_to_rgba(c1, 0.30), "var(--text-color)"
    bg_v3, txt_v3 = hex_to_rgba(c1, 0.48), "var(--text-color)"
    bg_v4, txt_v4 = hex_to_rgba(c1, 0.70), "#ffffff"
    bg_v5, txt_v5 = hex_to_rgba(c1, 0.95), "#ffffff"
    # ==============================================================================
    # 1. TRATAMENTO DE DATAS E PIVOT TABLE
    # ==============================================================================
    df_matriz = df_filtered.copy()
    df_matriz["ano"] = df_matriz["ano_mes_dt"].dt.year
    df_matriz["mes_num"] = df_matriz["ano_mes_dt"].dt.month

    meses_map = {
        1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
        5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
        9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
    }
    df_matriz["mes_nome"] = df_matriz["mes_num"].map(meses_map)

    pivot = df_matriz.pivot_table(
        index="ano",
        columns="mes_nome",
        values=valor_liq_col,
        aggfunc="sum",
        fill_value=0.0,
    )

    ordem_meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    for m in ordem_meses:
        if m not in pivot.columns:
            pivot[m] = 0.0

    pivot = pivot[ordem_meses].sort_index(ascending=False)

    # ==============================================================================
    # 2. CÁLCULOS DAS MÉTRICAS
    # ==============================================================================
    pivot["TOTAL"] = pivot[ordem_meses].sum(axis=1)

    medias = []
    for ano, row in pivot.iterrows():
        medias.append(row["TOTAL"] / 12)

    pivot["MEDIA"] = medias

    pivot_asc = pivot.sort_index(ascending=True)
    pivot_asc["VAR_PCT"] = pivot_asc["TOTAL"].pct_change() * 100
    pivot["VAR_PCT"] = pivot_asc["VAR_PCT"].sort_index(ascending=False)

    # ==============================================================================
    # 🛠️ 3. CSS USANDO 100% VARIÁVEIS NATIVAS DO STREAMLIT
    # ==============================================================================
    css_code = f"""<style>
                        .matriz-container {{ 
                            background-color: var(--secondary-background-color) !important; 
                            border: 1px solid rgba(128, 128, 128, 0.2); 
                            border-radius: 8px; 
                            padding: 16px; 
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                            overflow-x: auto; 
                            margin-bottom: 25px; 
                        }}
                        .matriz-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
                        .matriz-title {{ font-size: 16px; font-weight: 600; color: var(--text-color); }}
                        .matriz-subtitle {{ font-size: 12px; opacity: 0.7; color: var(--text-color); }}
                        .matriz-table {{ width: 100%; border-collapse: collapse; text-align: center; font-size: 13px; }}
                        .matriz-table th {{ 
                            background-color: var(--background-color); 
                            color: var(--text-color); 
                            font-weight: 500; 
                            padding: 10px 4px; 
                            border: 1px solid rgba(128, 128, 128, 0.2); 
                            font-size: 12px; 
                        }}
                        .matriz-table td {{ border: 1px solid rgba(128, 128, 128, 0.2); padding: 4px; color: var(--text-color); }}
                        .col-ano {{ background-color: var(--background-color) !important; font-weight: 600; color: var(--text-color) !important; }}
                        .cell-badge {{ border-radius: 4px; padding: 6px 2px; font-size: 12px; font-weight: 500; display: block; }}
                        .val-empty {{ background-color: transparent; opacity: 0.3; color: var(--text-color); }}

                        /* NÍVEIS DE PROVENTOS */
                        .val-v1 {{ background-color: {bg_v1} !important; color: {txt_v1} !important; }}
                        .val-v2 {{ background-color: {bg_v2} !important; color: {txt_v2} !important; }}
                        .val-v3 {{ background-color: {bg_v3} !important; color: {txt_v3} !important; font-weight: 600; }}
                        .val-v4 {{ background-color: {bg_v4} !important; color: {txt_v4} !important; font-weight: 600; }}
                        .val-v5 {{ background-color: {bg_v5} !important; color: {txt_v5} !important; font-weight: 700; }}

                        .val-metric {{ background-color: var(--background-color) !important; color: var(--text-color) !important; font-weight: 500; }}
                        .val-total {{ font-weight: 700; }}
                        .var-up {{ color: #10b981 !important; font-weight: 600; }}
                        .var-down {{ color: #ef4444 !important; font-weight: 600; }}
                        </style>"""

    # ==============================================================================
    # 4. MONTAGEM DAS LINHAS HTML
    # ==============================================================================
    rows_html = []
    max_val = pivot[ordem_meses].max().max() if not pivot.empty else 1.0
    if max_val == 0:
        max_val = 1.0

    for ano, row in pivot.iterrows():
        cells_meses = []
        for mes in ordem_meses:
            val = row.get(mes, 0.0)
            if val <= 0:
                cells_meses.append("<td><span class='cell-badge val-empty'>—</span></td>")
            else:
                ratio = val / max_val
                if ratio <= 0.20:
                    cls = "val-v1"
                elif ratio <= 0.40:
                    cls = "val-v2"
                elif ratio <= 0.60:
                    cls = "val-v3"
                elif ratio <= 0.80:
                    cls = "val-v4"
                else:
                    cls = "val-v5"

                val_str = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                cells_meses.append(f"<td><span class='cell-badge {cls}'>{val_str}</span></td>")

        val_media = f"{row['MEDIA']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        val_total = f"{row['TOTAL']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        var_pct = row["VAR_PCT"]
        if pd.isna(var_pct):
            var_html = "<span class='cell-badge val-metric val-empty'>—</span>"
        elif var_pct >= 0:
            var_html = f"<span class='cell-badge val-metric var-up'>▲ {var_pct:.2f}%</span>".replace(".", ",")
        else:
            var_html = f"<span class='cell-badge val-metric var-down'>▼ {abs(var_pct):.2f}%</span>".replace(".", ",")

        meses_concat = "".join(cells_meses)
        row_str = (
            f"<tr><td class='col-ano'>{ano}</td>{meses_concat}"
            f"<td><span class='cell-badge val-metric'>{val_media}</span></td>"
            f"<td><span class='cell-badge val-metric val-total'>{val_total}</span></td>"
            f"<td>{var_html}</td></tr>"
        )
        rows_html.append(row_str)

    headers_meses = "".join([f"<th>{m}</th>" for m in ordem_meses])
    all_rows = "".join(rows_html)

    html_code = (
        f"{css_code}"
        f"<div class='matriz-container'>"
        f"<div class='matriz-header'>"
        f"<span class='matriz-title'>Proventos por mês</span>"
        f"<span class='matriz-subtitle'>Valores em {moeda_simbolo} creditados no período</span>"
        f"</div>"
        f"<table class='matriz-table'>"
        f"<thead><tr><th class='col-ano'>ANO</th>{headers_meses}<th>Média</th><th>Total</th><th>Var %</th></tr></thead>"
        f"<tbody>{all_rows}</tbody>"
        f"</table>"
        f"</div>"
    )

    st.markdown(html_code, unsafe_allow_html=True)


def renderizar_e_aplicar_filtros( df: pd.DataFrame, expander_container: Any, ) -> Tuple[pd.DataFrame, Optional[str], str, str, str]:
    """ Renderiza os widgets do Streamlit e aplica os filtros diretamente no DataFrame.

    Returns:
        Tuple contendo: (df_filtrado, coluna_agrupamento, agrupamento_label, visao, base_data)
    """
    df_filtered = df.copy()

    # 1. Filtro de Tickers no Expander Superior
    ativos_disponiveis = sorted(list(df_filtered["fk_ativo"].dropna().unique()))
    with expander_container:
        tickers = st.multiselect( "Filtrar Ativos:", key="multi_sl_Ativos", options=ativos_disponiveis )

    # 2. Controles de Visualização em 4 Colunas (Sem colunas vazias)
    col_f1, col_f2, col_f3 = st.columns(3)

    visao = col_f1.selectbox("Visão:", ("Mensal", "Anual"))

    # Define o agrupamento primeiro para alimentar as opções do filtro dinâmico
    agrupamento_label = col_f2.selectbox( "Agrupar por:", options=list(MAPA_AGRUPAMENTOS.keys()), index=0 )
    coluna_agrupamento = MAPA_AGRUPAMENTOS[agrupamento_label]

    # Renderiza o filtro do agrupamento logo em seguida (na ordem lógica)
    opcoes_filtro_especifico: List[str] = []
    if coluna_agrupamento and coluna_agrupamento in df_filtered.columns:
        opcoes_filtro_especifico.extend( sorted(list(df_filtered[coluna_agrupamento].dropna().unique())) )
    elif agrupamento_label == "Completo":
        for coluna in MAPA_AGRUPAMENTOS.values():
            if coluna in df_filtered.columns:
                opcoes_filtro_especifico.extend( list(df_filtered[coluna].dropna().unique()) )
                opcoes_filtro_especifico = sorted(list(set(opcoes_filtro_especifico)))


    valor_filtro_selecionado = col_f3.multiselect( f"Filtrar por {agrupamento_label}:", options=opcoes_filtro_especifico )

    df_filtered["ano_mes_dt"] = pd.to_datetime(df_filtered['ano_mes_ref'])
    df_filtered["periodo_str"] = df_filtered["ano_mes_dt"].dt.strftime("%Y-%m")

    # Aplicação direta das regras de filtragem
    if tickers:
        df_filtered = df_filtered[df_filtered["fk_ativo"].isin(tickers)]
    
    if valor_filtro_selecionado:
        if coluna_agrupamento and coluna_agrupamento in df_filtered.columns:
            # Filtro dinâmico na coluna selecionada
            df_filtered = df_filtered[df_filtered[coluna_agrupamento].isin(valor_filtro_selecionado)]
        elif agrupamento_label == "Completo":
            # Busca o valor selecionado tanto em 'grupo' quanto em 'categoria' usando o operador '|'
            cond_grupo = df_filtered["grupo"].isin(valor_filtro_selecionado) if "grupo" in df_filtered.columns else False
            cond_categoria = df_filtered["categoria"].isin(valor_filtro_selecionado) if "categoria" in df_filtered.columns else False
            
            df_filtered = df_filtered[cond_grupo | cond_categoria]  

    if visao == "Anual":
        df_filtered["periodo_agrupado"] = df_filtered["ano_mes_dt"].dt.year.astype(str)
    else:
        df_filtered["periodo_agrupado"] = df_filtered["periodo_str"]

    return df_filtered, coluna_agrupamento, agrupamento_label, visao

# ==============================================================================
# CABEÇALHO E FILTROS DE PERÍODO (FETCH API)
# ==============================================================================
c1_t, _, c2_t = st.columns([5, 3, 2])
c1_t.title("📈 Gráfico de Dividendos Recebidos 🤑")
moeda = c2_t.radio("Moeda dos valores", ["BRL", "USD"], key="moeda_valores", horizontal=True)

c1_f, c2_f = st.columns(2)
with c1_f.expander("📅 Filtros de Período", expanded=False):
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    base_data = col_p1.selectbox( "Base de Data:", options=["Pagamento", "Data Com"], index=0,
                                    help="Data Com: Competência do direito | Data Pagamento: Data de recebimento", )
    periodo_selecionado = col_p2.selectbox( "Período de Consulta:", options=["12M", "TUDO", "CUSTOM"], index=0,
                                                help="12M: Últimos 12 meses | TUDO: Todo o histórico disponível | CUSTOM: Faixa personalizada", )

    data_ini = None
    data_fim = None

    if periodo_selecionado == "CUSTOM":
        data_ini = col_p3.date_input("Data Início", value=date.today().replace(month=1, day=1))
        data_fim = col_p4.date_input("Data Fim", value=date.today())

    if (
        "grafico" not in state
        or state.get("ultimo_periodo_opcao") != f"{periodo_selecionado}_{base_data}"
        or state.get("ultima_dt_ini") != data_ini
        or state.get("ultima_dt_fim") != data_fim
    ):
        state["grafico"] = carregar_dados_agregados( periodo=periodo_selecionado, dt_inicio=data_ini, dt_fim=data_fim, agrupar_por=base_data)
        state["ultimo_periodo_opcao"] = f"{periodo_selecionado}_{base_data}"
        state["ultima_dt_ini"] = data_ini
        state["ultima_dt_fim"] = data_fim

if not state["grafico"]:
    st.info("💡 Nenhum dividendo encontrado para o período selecionado.")
    st.stop()

# ==============================================================================
# TRATAMENTO DO PAYLOAD AGREGADO
# ==============================================================================
df_base = pd.DataFrame(state["grafico"])

if moeda == "BRL":
    valor_bruto_col = "valor_bruto_brl"
    valor_liq_col = "valor_liq_brl"
    imposto_col = "imposto_brl"
    moeda_simbolo = "R$"
else:
    valor_bruto_col = "valor_bruto_usd"
    valor_liq_col = "valor_liq_usd"
    imposto_col = "imposto_usd"
    moeda_simbolo = "US$"

for col in [valor_bruto_col, imposto_col, valor_liq_col]:
    df_base[col] = pd.to_numeric(df_base[col], errors="coerce").fillna(0.0)

for agrp_col in ["categoria", "grupo"]:
    if agrp_col in df_base.columns:
        df_base[agrp_col] = df_base[agrp_col].fillna("Não Informado")

# ==============================================================================
# FILTROS DE VISUALIZAÇÃO E DADOS
# ==============================================================================
expander_ativos = c2_f.expander("🏷️ Filtros de Ativos", expanded=False)

df_filtered, coluna_agrupamento, agrupamento_label, visao = renderizar_e_aplicar_filtros( df=df_base, expander_container=expander_ativos)

if df_filtered.empty:
    st.warning("Nenhum dado retornado para os filtros aplicados.")
    st.stop()

# ==============================================================================
# CONSOLIDAÇÃO DOS DADOS DO GRÁFICO
# ==============================================================================
if coluna_agrupamento:
    df_chart = (
        df_filtered.groupby(["periodo_agrupado", coluna_agrupamento])[valor_liq_col]
        .sum()
        .reset_index()
    )
else:
    df_chart = (
        df_filtered.groupby("periodo_agrupado")[valor_liq_col].sum().reset_index()
    )

hoje_str = pd.Timestamp.now().strftime("%Y-%m") if visao != "Anual" else str(pd.Timestamp.now().year)
def definir_status(periodo: str) -> str:
    return "Futuro" if periodo > hoje_str else "Realizado"
df_chart["Status_Periodo"] = df_chart["periodo_agrupado"].apply(definir_status)


df_chart["Rotulo"] = df_chart[valor_liq_col].apply(lambda x: f"{moeda_simbolo} {numero_padrao(x)}")

if visao == "Anual":
    df_chart["Média Mensal"] = (df_chart[valor_liq_col] / 12).apply(lambda x: f"{moeda_simbolo} {numero_padrao(x)}")
else:
    df_chart["Média Mensal"] = df_chart["Rotulo"]

# ==============================================================================
# VISUALIZAÇÃO GRÁFICA
# ==============================================================================
labels_plotly = {
    "periodo_agrupado": f"Período ({base_data})",
    valor_liq_col: f"Valor Líquido ({moeda_simbolo})",
}
if coluna_agrupamento:
    labels_plotly[coluna_agrupamento] = agrupamento_label

# Mapeamento das Cores (Ajuste o código hex da cor padrão do seu tema se desejar)
COR_REALIZADO = "#C29B38"  # Tom dourado/ocre das barras atuais
COR_FUTURO = "#E6D3A3"     # Tom bem mais claro para os valores futuros

color_col = coluna_agrupamento if coluna_agrupamento else "Status_Periodo"
color_map = {"Realizado": COR_REALIZADO, "Futuro": COR_FUTURO} if not coluna_agrupamento else None

fig = px.bar(
    df_chart,
    x="periodo_agrupado",
    y=valor_liq_col,
    color=color_col,
    color_discrete_map=color_map,
    barmode="group" if coluna_agrupamento else "overlay",
    text="Rotulo",
    custom_data=["Média Mensal"],
    title=f"Proventos Agregados por Período ({visao} - {base_data}) - {agrupamento_label}",
    labels=labels_plotly,
    height=530,
)
# Configura o que aparece no valor suspenso (Hover)
if visao == "Anual":
    fig.update_traces(
        hovertemplate=(
            "<b>Período:</b> %{x}<br>"
            f"<b>Total Líquido:</b> {moeda_simbolo} %{{y:,.2f}}<br>"
            "<b>Média Mensal:</b> %{customdata[0]}<extra></extra>"
        )
    )
else:
    fig.update_traces(
        hovertemplate=(
            "<b>Período:</b> %{x}<br>"
            f"<b>Total Líquido:</b> {moeda_simbolo} %{{y:,.2f}}<extra></extra>"
        )
    )
fig.update_layout(
    separators=",.",
    yaxis_tickformat=",.2f",
    xaxis_type="category",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.3,
        xanchor="center",
        x=0.5,
    ),
)
st.plotly_chart(fig, width="stretch")

# ==============================================================================
# MATRIZ VISUAL DE PROVENTOS (ESTILO MAPA DE CALOR DA IMAGEM)
# ==============================================================================
renderizar_matriz_proventos( df_filtered=df_filtered, valor_liq_col=valor_liq_col, moeda_simbolo=moeda_simbolo)
