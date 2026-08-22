import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from Pages.utils.components import componente_buscador_ativo, componente_seletor_categorias
from Pages.utils.request_api import (
    ApiRequestError,
    buscar_carteira_api,
    executar_requisicao_atualizar_planejamento_carteira,
    obter_configuracoes_usuario_api,
    executar_requisicao_atualizar_configuracoes
)
from Pages.utils.ferramentas import tratar_dados_carteira_raw


# ============================================================
# CONFIGURAÇÕES
# ============================================================
TIERS = {
    "TIER 1": (8, 10),
    "TIER 2": (5, 7),
    "TIER 3": (1, 4),
    "PAUSA": (0, 0)
}

# ============================================================
# FUNÇÕES MODULARES
# ============================================================
def create_sunburst_chart(df: pd.DataFrame):
    if df.empty:
        return None

    df_chart = df.copy()

    # interno: snake_case
    df_chart.rename(columns={
        "Grupo": "grupo",
        "Subgrupo": "subgrupo",
        "Ativo": "ativo",
        "Peso": "peso"
    }, inplace=True)

    df_chart["grupo"] = df_chart["grupo"].fillna("GERAL").astype(str).str.strip()
    df_chart["subgrupo"] = df_chart["subgrupo"].fillna("GERAL").astype(str).str.strip()
    df_chart["ativo"] = df_chart["ativo"].fillna("N/A").astype(str).str.strip()
    df_chart["peso"] = pd.to_numeric(df_chart["peso"], errors="coerce").fillna(0.0)


    # UI: aqui é onde você controla o visual
    df_ui = pd.DataFrame({
        "Grupo": df_chart["grupo"].str.title(),      # ou só df_chart["grupo"] se quiser 100% original
        "Subgrupo": df_chart["subgrupo"].str.title(),# idem
        "Ativo": df_chart["ativo"],                  # mantém ticker como veio
        "Peso": df_chart["peso"],
    })

    fig = px.sunburst(
        df_ui,
        path=["Grupo", "Subgrupo", "Ativo"],
        values="Peso",
        color="Grupo",
        color_discrete_sequence= ["#FF4B4B", "#0068C9", "#83C9FF", "#FF8700", "#29B09D", "#7D44CF", "#F24C3D"]
    )

    fig.update_traces(textinfo="label+percent entry")
    fig.update_layout(
        margin=dict(b=0, t=0, l=0, r=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
    )

    return fig

def create_sankey_chart(df: pd.DataFrame):
    """Cria o gráfico de Sankey com ordenação hierárquica (em cascata) utilizando fk_ativo para nós únicos."""

    if df.empty:
        return None

    # --- Normalização LEGACYINVEST ---
    df_chart = df.copy()

    # Mapeia colunas mantendo fk_ativo se existir
    rename_dict = {
        "Grupo": "grupo",
        "Subgrupo": "subgrupo",
        "Ativo": "ativo",
        "Peso": "peso",
        "%": "pct",
    }
    if "fk_ativo" in df_chart.columns:
        rename_dict["fk_ativo"] = "fk_ativo"

    df_chart.rename(columns=rename_dict, inplace=True)

    col_pct = "pct" if "pct" in df_chart.columns else "peso"

    # Sanitização
    df_chart["grupo"] = (
        df_chart["grupo"].fillna("GERAL").astype(str).str.strip().str.upper()
    )
    df_chart["subgrupo"] = (
        df_chart["subgrupo"].fillna("GERAL").astype(str).str.strip().str.upper()
    )
    df_chart["ativo"] = (
        df_chart["ativo"].fillna("N/A").astype(str).str.strip().str.upper()
    )

    # 🛠️ Se fk_ativo não existir, gera uma chave composta com base no index/subgrupo/ativo
    if "fk_ativo" not in df_chart.columns or df_chart["fk_ativo"].isnull().all():
        df_chart["fk_ativo"] = (
            df_chart["grupo"]
            + "_"
            + df_chart["subgrupo"]
            + "_"
            + df_chart["ativo"]
            + "_"
            + df_chart.index.astype(str)
        )

    # Limpeza e conversão numérica
    if df_chart[col_pct].dtype == object:
        df_chart[col_pct] = (
            df_chart[col_pct]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
        )

    df_chart[col_pct] = pd.to_numeric(
        df_chart[col_pct], errors="coerce"
    ).fillna(0.0)

    # Normalização dos pesos (%)
    soma_total = df_chart[col_pct].sum()
    if soma_total <= 0:
        return None

    df_chart[col_pct] = (df_chart[col_pct] / soma_total) * 100.0
    df_chart = df_chart[df_chart[col_pct] > 0]

    if df_chart.empty:
        return None

    # --- Totais agregados ---
    totais_grupo = df_chart.groupby("grupo")[col_pct].sum().to_dict()
    totais_subgrupo = df_chart.groupby("subgrupo")[col_pct].sum().to_dict()
    totais_fk = df_chart.groupby("fk_ativo")[col_pct].sum().to_dict()

    # Mapeamentos de apoio
    ticker_do_fk = df_chart.set_index("fk_ativo")["ativo"].to_dict()
    grupo_do_subgrupo = (
        df_chart.groupby("subgrupo")["grupo"].first().to_dict()
    )
    grupo_do_fk = df_chart.set_index("fk_ativo")["grupo"].to_dict()

    # --- MONTAGEM DA ORDENAÇÃO HIERÁRQUICA (EM CASCATA) ---

    # 1. Grupos ordenados por % total (Maior -> Menor)
    grupos_unicos = sorted(
        df_chart["grupo"].unique(),
        key=lambda g: totais_grupo.get(g, 0),
        reverse=True,
    )

    # 2. Subgrupos ordenados DENTRO de cada Grupo Pai (Maior -> Menor)
    subgrupos_unicos = []
    for g in grupos_unicos:
        df_g = df_chart[df_chart["grupo"] == g]
        subs_do_grupo = sorted(
            df_g["subgrupo"].unique(),
            key=lambda s: totais_subgrupo.get(s, 0),
            reverse=True,
        )
        subgrupos_unicos.extend(subs_do_grupo)

    # 3. Ativos (fk_ativo) ordenados DENTRO de cada Subgrupo Pai (Maior -> Menor)
    fk_unicos = []
    for s in subgrupos_unicos:
        df_s = df_chart[df_chart["subgrupo"] == s]
        fks_do_subgrupo = sorted(
            df_s["fk_ativo"].unique(),
            key=lambda fk: totais_fk.get(fk, 0),
            reverse=True,
        )
        fk_unicos.extend(fks_do_subgrupo)

    # Paleta de Cores por Grupo
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

    # --- Mapeamento de Nós ---
    # 🛠️ Mapeia nós de ativos pela chave única fk_ativo em vez do ticker simples
    todos_nos_keys = (
        [f"g_{x}" for x in grupos_unicos]
        + [f"s_{x}" for x in subgrupos_unicos]
        + [f"a_{x}" for x in fk_unicos]
    )
    node_map = {no: i for i, no in enumerate(todos_nos_keys)}

    def fmt_pct(val: float) -> str:
        return f"{val:.2f}".replace(".", ",")

    # 🛠️ Rótulo do nó usa o ticker visual (ticker_do_fk) para exibição limpa
    labels_exibicao = (
        [
            f"{g.title()} ({fmt_pct(totais_grupo.get(g, 0.0))}%)"
            for g in grupos_unicos
        ]
        + [
            f"{s.title()} ({fmt_pct(totais_subgrupo.get(s, 0.0))}%)"
            for s in subgrupos_unicos
        ]
        + [
            f"{ticker_do_fk.get(fk, 'N/A').upper()} ({fmt_pct(totais_fk.get(fk, 0.0))}%)"
            for fk in fk_unicos
        ]
    )

    node_colors = (
        [cor_por_grupo[g] for g in grupos_unicos]
        + [
            cor_por_grupo.get(
                grupo_do_subgrupo.get(s, "GERAL"), "#1F77B4"
            )
            for s in subgrupos_unicos
        ]
        + [
            cor_por_grupo.get(grupo_do_fk.get(fk, "GERAL"), "#1F77B4")
            for fk in fk_unicos
        ]
    )

    # --- CONEXÕES (LINKS) MANTENDO A ORDEM HIERÁRQUICA ---
    sources, targets, values, link_colors = [], [], [], []

    # Links: Grupo -> Subgrupo
    for g in grupos_unicos:
        df_g = df_chart[df_chart["grupo"] == g]
        g_s_agrupado = (
            df_g.groupby("subgrupo")[col_pct]
            .sum()
            .reset_index()
            .sort_values(by=col_pct, ascending=False)
        )

        for _, row in g_s_agrupado.iterrows():
            sources.append(node_map[f"g_{g}"])
            targets.append(node_map[f"s_{row['subgrupo']}"])
            values.append(row[col_pct])
            link_colors.append(
                hex_to_rgba(cor_por_grupo.get(g, "#1F77B4"), 0.3)
            )

    # Links: Subgrupo -> Ativo (via fk_ativo)
    for s in subgrupos_unicos:
        df_s = df_chart[df_chart["subgrupo"] == s]
        g_pai = grupo_do_subgrupo.get(s, "GERAL")
        s_a_agrupado = (
            df_s.groupby("fk_ativo")[col_pct]
            .sum()
            .reset_index()
            .sort_values(by=col_pct, ascending=False)
        )

        for _, row in s_a_agrupado.iterrows():
            sources.append(node_map[f"s_{s}"])
            targets.append(node_map[f"a_{row['fk_ativo']}"])
            values.append(row[col_pct])
            link_colors.append(
                hex_to_rgba(cor_por_grupo.get(g_pai, "#1F77B4"), 0.2)
            )

    # --- Renderização ---
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="freeform",
                textfont=dict(
                    size=11, color="#1A1A1A", family="sans-serif"
                ),
                node=dict(
                    pad=10,
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
        margin=dict(b=12, t=10, l=40, r=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=650,
    )

    return fig

def barra_colorida(label, dados, cor):
    """Renderiza uma barra de distribuição com regra especial para ativos."""
    # Se for um ativo individual (não tem 'count' ou count == 1), simplifica o label
    if isinstance(dados, dict):
        pct = dados.get("pct", 0)
        count = dados.get("count", 1)
        media = dados.get("media_pct", pct)
    else:
        # Caso seja passado só o percentual (ex.: ativos)
        pct = float(dados)
        count = 1
        media = pct

    # Regra: se for ativo individual, não mostra count nem média
    if count <= 1:
        texto_label = f"{label} — {pct:.2f}% • {count} ativos"
    else:
        texto_label = f"{label} — {pct:.2f}% • {count} ativos • média {media:.2f}%"

    st.markdown(f"""
    <div style="margin-bottom:6px;">
      <div style="font-size:13px; margin-bottom:2px;">{texto_label}</div>
      <div style="background:#eee; border-radius:6px; overflow:hidden;">
        <div style="width:{pct}%; background:{cor}; height:10px;"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

def icone_grupo(nome):
    nome_norm = (nome or "").strip().upper()

    if nome_norm in ["AÇÕES", "AÇÃO"]:
        return "📈"
    if "FII" in nome_norm or "FIAGRO" in nome_norm:
        return "🏢"
    if "BDR" in nome_norm:
        return "🌎"
    if "ETF" in nome_norm:
        return "📊"
    if "REIT" in nome_norm:
        return "🏙️"
    if "STOCK" in nome_norm:
        return "💼"
    return "📁"

def icone_tier(tier):
    tier_norm = (tier or "").strip().upper()

    if tier_norm == "TIER 1":
        return "🥇"
    if tier_norm == "TIER 2":
        return "🥈"
    if tier_norm == "TIER 3":
        return "🥉"
    return "⏸️"

def get_tier(nota):
    for tier, (mn, mx) in TIERS.items():
        if mn <= nota <= mx:
            icone = icone_tier(tier)
            return tier, icone
    return "PAUSA", "⏸️"

def calcular_pesos_automaticos(state):
    ativos = state["ativos"]
    # 1. soma dos grupos por macro
    soma_grupos_macro = {}
    for grupo, pct in state["pesos_grupos"].items():
        macro_do_grupo = None
        for a in ativos:
            if (a["grupo"] or "").strip().upper() == grupo:
                macro_do_grupo = (a["macro"] or "").strip().upper()
                break
        if macro_do_grupo:
            soma_grupos_macro[macro_do_grupo] = soma_grupos_macro.get(macro_do_grupo, 0) + pct

    # 2. contagem por subgrupo
    count_sub = {}
    for a in ativos:
        grupo = (a["grupo"] or "").strip().upper()
        sub   = (a["subgrupo"] or "").strip().upper()
        count_sub[(grupo, sub)] = count_sub.get((grupo, sub), 0) + 1

    pesos_base = {}

    for a in ativos:
        macro = (a["macro"] or "").strip().upper()
        grupo = (a["grupo"] or "").strip().upper()
        sub   = (a["subgrupo"] or "").strip().upper()
        tier  = (a["tier"] or "").strip().upper()
        nota  = a.get("nota", 10)

        macro_pct = state["pesos_macro"].get(macro, 0.0)
        grupo_pct = state["pesos_grupos"].get(grupo, 0.0)
        sub_pct   = state["pesos_subgrupos"].get(grupo, {}).get(sub, 0.0)

        # regra de 2 do macro
        soma_grupos = soma_grupos_macro.get(macro, macro_pct)
        f_macro = macro_pct / soma_grupos

        grupo_ajustado = grupo_pct * f_macro

        # peso base do subgrupo
        peso_sub = (sub_pct / 100.0) / count_sub[(grupo, sub)]

        # fator tier
        fator_tier = state["pesos_tiers"].get(tier, 100) / 100.0

        # peso final base
        peso_final = (grupo_ajustado / 100.0) * peso_sub
        peso_final *= fator_tier

        # nota só entra se a opção estiver ativada
        if state["regra_tier"].strip().upper() == "PROPORCIONAL À NOTA":
            peso_final *= (nota / 10.0)

        pesos_base[a["ticker"]] = peso_final

    soma = sum(pesos_base.values()) or 1.0
    return {t: round((v / soma) * 1000, 4) for t, v in pesos_base.items()}

def calcular_distribuicoes(ativos):
    total_peso = sum(a["peso"] for a in ativos) or 1.0

    grupos = {}
    subgrupos = {}
    macros = {}
    tiers = {}
    ativos_pct = {}

    for a in ativos:
        fk_ativo = a['fk_ativo']
        peso = float(a["peso"])

        # --- VISUAL (Title Case) ---
        grupo_raw = a.get("grupo") or "Sem Grupo"
        grupo_vis = f"{icone_grupo(grupo_raw)} {grupo_raw}".title()

        subgrupo_raw = a.get("subgrupo") or "Sem Subgrupo"
        subgrupo_vis = subgrupo_raw.title()

        macro_raw = a.get("macro") or "Sem Macro"
        macro_vis = f"🇧🇷 {macro_raw}" if macro_raw.strip().upper() == "BRASIL" else f"🌎 {macro_raw}"
        macro_vis = macro_vis.title()

        tier, icone = get_tier(a.get("nota", 0))
        tier_vis = f"{tier} {icone}".title() if tier else "⏸️ Pausa"

        nome_ativo = f"{a['ticker']} - {tier_vis}"

        # --- AGRUPAMENTO ---
        grupos.setdefault(grupo_vis, {"peso": 0.0, "count": 0})
        grupos[grupo_vis]["peso"] += peso
        grupos[grupo_vis]["count"] += 1

        subgrupos.setdefault(subgrupo_vis, {"peso": 0.0, "count": 0})
        subgrupos[subgrupo_vis]["peso"] += peso
        subgrupos[subgrupo_vis]["count"] += 1

        macros.setdefault(macro_vis, {"peso": 0.0, "count": 0})
        macros[macro_vis]["peso"] += peso
        macros[macro_vis]["count"] += 1

        tiers.setdefault(tier_vis, {"peso": 0.0, "count": 0})
        tiers[tier_vis]["peso"] += peso
        tiers[tier_vis]["count"] += 1

        ativos_pct[fk_ativo] = { "nome": nome_ativo, "peso": peso }

    # Normalização
    def norm(d):
        return {
            k: {
                "pct": (v["peso"] / total_peso) * 100.0,
                "count": v["count"],
                "media_pct": ((v["peso"] / total_peso) * 100.0) / v["count"]
            }
            for k, v in d.items()
        }

    return {
        "grupos": norm(grupos),
        "subgrupos": norm(subgrupos),
        "macros": norm(macros),
        "tiers": norm(tiers),
        "ativos": [ (v["nome"], (v["peso"] / total_peso) * 100.0) for v in ativos_pct.values()]
    }

def renderizar_distribuicoes(dist):
    st.divider()
    st.markdown("### 📊 Distribuição dos Pesos (em %)")

    col1, col2, col3, col4 = st.columns(4)

    # ---------------- MACRO ----------------
    with col1:
        st.write("**Por Macro (Maior → Menor)**")
        for nome, dados in sorted(dist["macros"].items(), key=lambda x: x[1]["pct"], reverse=True):
            barra_colorida(nome, dados, "#8E24AA")

    # ---------------- GRUPO ----------------
    with col2:
        st.write("**Por Grupo (Maior → Menor)**")
        for nome, dados in sorted(dist["grupos"].items(), key=lambda x: x[1]["pct"], reverse=True):
            barra_colorida(nome, dados, "#1976D2")

    # ---------------- SUBGRUPO ----------------
    with col3:
        st.write("**Por Subgrupo (Maior → Menor)**")
        for nome, dados in sorted(dist["subgrupos"].items(), key=lambda x: x[1]["pct"], reverse=True):
            barra_colorida(nome, dados, "#43A047")

    # ---------------- TIER ----------------
    with col4:
        st.write("**Por Tier (Maior → Menor)**")
        for nome, dados in sorted(dist["tiers"].items(), key=lambda x: x[1]["pct"], reverse=True):
            barra_colorida(nome, dados, "#FB8C00")

    # ---------------- TOP 10 ----------------
    st.divider()
    st.markdown("### 🏆 Top 10 Ativos — Maiores e Menores Pesos")

    colA, colB = st.columns(2)
    ordenados_maiores = sorted(dist["ativos"], key=lambda x: x[1], reverse=True)

    with colA:
        st.write("**🔝 Top 10 Maiores Pesos**")
        for nome, pct in ordenados_maiores[:10]:
            barra_colorida(nome, {"pct": pct, "count": 1, "media_pct": pct}, "#0288D1")

    ordenados_menores = sorted(dist["ativos"], key=lambda x: x[1], reverse=False)
    with colB:
        st.write("**🔻 Top 10 Menores Pesos**")
        for nome, pct in ordenados_menores[:10:]:
            barra_colorida(nome, {"pct": pct, "count": 1, "media_pct": pct}, "#D32F2F")

def adicionar_ativo(state, dados):
    # Identificador único absoluto (FK do banco de dados)
    fk_ativo = dados.get("fk_ativo") or dados.get("id_ativo") or dados.get("ativo_cat")

    if not fk_ativo:
        return ( False, "⚠️ Erro ao adicionar: O identificador único (fk_ativo) do ativo não foi informado.", )
    
    ticker = (dados.get("codigo_ativo") or dados.get("ticker") or "").strip()
    nome = dados.get("nome")
    categoria = (dados.get("categoria") or "").strip().upper()
    setor = (dados.get("setor") or "").strip().upper()
    moeda = (dados.get("moeda") or "").strip().upper()
    origem = dados.get("origem")

    if categoria == "SUBS":
        return False, f"⚠️ Ativo {ticker} é uma subscrição, não usamos para planejamento."
    # Macro
    macro = "BRASIL" if (moeda == "BRL") else "EXTERIOR"

    # Grupo/Subgrupo normalizados
    grupo_norm = (dados.get("grupo") or categoria or "OUTROS").strip().upper()
    sub_norm = (dados.get("subgrupo") or setor or "SEM SETOR").strip().upper()

    # Nota e Tier
    nota = int(dados.get("nota", 1))
    tier, _ = get_tier(nota)

    peso = float(dados.get("peso", 0))

    # --- VALIDAÇÃO DE DUPLICATAS POR FK_ATIVO ---
    fks_existentes = [ a.get("fk_ativo") for a in state["ativos"] if a.get("fk_ativo") is not None ]

    if fk_ativo in fks_existentes:
        return ( False, f"⚠️ O ativo {ticker} (ID: {fk_ativo}) já está presente no planejamento.⚠️",
        )

    # Atualiza listas auxiliares
    if grupo_norm not in [g.strip().upper() for g in state["grupos"]]:
        state["grupos"].append(grupo_norm)
        state["grupos"] = sorted(state["grupos"],key=lambda g: g.strip().upper())

    if sub_norm not in [s.strip().upper() for s in state["subgrupos"]]:
        state["subgrupos"].append(sub_norm)
        state["subgrupos"] = sorted(state["subgrupos"],key=lambda s: s.strip().upper())

# Adiciona ativo preservando a FK
    state["ativos"].append({
        "fk_ativo": fk_ativo,
        "ticker": ticker,
        "nome": nome,
        "categoria": categoria,
        "setor": setor,
        "moeda": moeda,
        "macro": macro,
        "grupo": grupo_norm,
        "subgrupo": sub_norm,
        "nota": nota,
        "tier": tier,
        "peso": peso,
        "origem": origem,
    })

    return True, f"✅ Ativo {ticker} adicionado com sucesso."

def componente_barra_adicao_rapida(state: dict, prefixo_key: str = "default"):
    """
    Barra de ações reutilizável para buscar/adicionar ativo, criar novos grupos e subgrupos.
    
    :param state: Dicionário de estado do aplicativo.
    :param prefixo_key: Prefixo único para evitar conflitos de keys do Streamlit entre etapas.
    """
    col1, col2, col3 = st.columns([1.2, 1, 1], gap="small")

    # ------------------------------------------------------------
    # COLUNA 1 — BUSCAR + ADICIONAR ATIVO
    # ------------------------------------------------------------
    with col1.container(border=True, horizontal=True, vertical_alignment="center"):
        sufixo_buscador = f"planejamento_guiado_{prefixo_key}"
        componente_buscador_ativo(state_dict=state, sufixo_key=sufixo_buscador)

        dados_ativo = state.get(f"dados_{sufixo_buscador}")

        def adicionar_ativo_manual():
            if dados_ativo:
                dados_ativo["origem"] = "manual"
                ok, msg = adicionar_ativo(state, dados_ativo)
                st.toast(msg)
            else:
                st.toast("⚠️ Nenhum ativo selecionado para adicionar.")

        st.button(
            "➕ Ativo",
            width="stretch",
            on_click=adicionar_ativo_manual,
            key=f"btn_add_ativo_{prefixo_key}",
        )

    # ------------------------------------------------------------
    # COLUNA 2 — CRIAR NOVO GRUPO
    # ------------------------------------------------------------
    with col2.container(border=True, horizontal=True, vertical_alignment="center"):
        key_grupo = f"novo_grupo_{prefixo_key}"
        st.text_input(
            "Criar novo grupo",
            placeholder="Novo grupo...",
            label_visibility="collapsed",
            key=key_grupo,
        )

        def criar_novo_grupo():
            val = st.session_state.get(key_grupo, "").strip()
            if not val:
                st.toast("⚠️ Digite um nome para o grupo.")
            else:
                grupo_norm = val.upper()
                grupo_vis = val.title()

                if grupo_norm in state.get("grupos", []):
                    st.toast(f"⚠️ O grupo **{grupo_vis}** já existe.")
                else:
                    state["grupos"].append(grupo_norm)
                    state["grupos"] = sorted(state["grupos"], key=lambda g: g.strip().upper())
                    st.toast(f"✅ Grupo '{grupo_vis}' adicionado!")

        st.button(
            "➕ Grupo",
            width="stretch",
            on_click=criar_novo_grupo,
            key=f"btn_add_grupo_{prefixo_key}",
        )

    # ------------------------------------------------------------
    # COLUNA 3 — CRIAR NOVO SUBGRUPO
    # ------------------------------------------------------------
    with col3.container(border=True, horizontal=True, vertical_alignment="center"):
        key_sub = f"novo_sub_{prefixo_key}"
        st.text_input(
            "Criar novo subgrupo",
            placeholder="Novo subgrupo...",
            label_visibility="collapsed",
            key=key_sub,
        )

        def criar_novo_subgrupo():
            val = st.session_state.get(key_sub, "").strip()
            if not val:
                st.toast("⚠️ Digite um nome para o subgrupo.")
            else:
                sub_norm = val.upper()
                sub_vis = val.title()

                if sub_norm in state.get("subgrupos", []):
                    st.toast(f"⚠️ O subgrupo **{sub_vis}** já existe.")
                else:
                    state["subgrupos"].append(sub_norm)
                    state["subgrupos"] = sorted(state["subgrupos"], key=lambda s: s.strip().upper())
                    st.toast(f"✅ Subgrupo '{sub_vis}' adicionado!")

        st.button(
            "➕ Subgrupo",
            width="stretch",
            on_click=criar_novo_subgrupo,
            key=f"btn_add_sub_{prefixo_key}",
        )

# ============================================================
# INICIALIZAÇÃO DO ESTADO
# ============================================================
if 'fez_planejamento' not in st.session_state:
    if "configuracoes" not in st.session_state:
        st.session_state['configuracoes'] = obter_configuracoes_usuario_api() or {}
        config_user = st.session_state['configuracoes']

    if 'fez_planejamento' not in config_user:
        st.session_state["fez_planejamento"] = False
    else:
        st.session_state["fez_planejamento"] = config_user['fez_planejamento']

if "planejamento_guiado" not in st.session_state:
    st.session_state.planejamento_guiado = {
        "etapa": 4 if st.session_state["fez_planejamento"] else 1,
        "modo_wizard": False if st.session_state["fez_planejamento"] else True,

        # dados carregados
        "ativos": [],

        "macro": ["BRASIL", "EXTERIOR"],
  
        # listas internas (sempre UPPERCASE)
        "grupos": [],
        "subgrupos": [],

        # pesos internos (sempre UPPERCASE)
        "pesos_grupos": {},
        "pesos_subgrupos": {},
        "pesos_macro": {},

        # tiers já vêm corretos
        "pesos_tiers": {"TIER 1": 60.0, "TIER 2": 30.0, "TIER 3": 10.0},

        # regra interna sempre UPPERCASE
        "regra_tier": "PROPORCIONAL À NOTA",
    }

state = st.session_state.planejamento_guiado

# ============================================================
# CARREGAMENTO DA CARTEIRA
# ============================================================
if "carregou_carteira" not in st.session_state or st.session_state.carregou_carteira == False:

    if "dados_carteira_cache" not in st.session_state:
        try:
            dados_raw = buscar_carteira_api()
            st.session_state["dados_carteira_cache"] = tratar_dados_carteira_raw(dados_raw)
        except ApiRequestError:
            st.session_state["dados_carteira_cache"] = []
            st.warning("Não foi possível carregar a carteira no momento.")

    carteira = st.session_state.get("dados_carteira_cache", [])
    state["ativos"] = []
    for item in carteira:
        item["origem"] = "api"
        adicionar_ativo(state, item)

    st.session_state.carregou_carteira = True

# ============================================================
# ETAPAS MODULARIZADAS
# ============================================================

def etapa1(state):
    
    def avaliar_classificar_ativos_etapa_1(state):

        st.markdown("### ⭐ Avaliação e Classificação dos Ativos")

        # Ordenação LEGACY SEED
        ativos_ordenados = sorted(
            state["ativos"],
            key=lambda a: (
                a["grupo"].strip().upper(),
                a["subgrupo"].strip().upper(),
                {"TIER 1": 1, "TIER 2": 2, "TIER 3": 3, "PAUSA": 4}[a["tier"]],
                -a["nota"],
                a["ticker"]
            )
        )

        # Agrupar por grupo (VISUAL)
        grupos_dict = {}
        for ativo in ativos_ordenados:
            grupo_vis = ativo["grupo"].strip().title()
            grupos_dict.setdefault(grupo_vis, []).append(ativo)

        # Renderização
        for grupo_vis, ativos_do_grupo in grupos_dict.items():
            with st.expander(f"{icone_grupo(grupo_vis)} {grupo_vis} - {len(ativos_do_grupo)} Ativos", key=f"expander_{grupo_vis}"):
                for a in ativos_do_grupo:
                    fk_ativo = ( a.get("fk_ativo") or a.get("id_ativo") or a.get("ativo_cat") )

                    ticker = a["ticker"]
                    nome = a["nome"].title() if a["nome"] else "N/A"
                    categoria = a["categoria"].title() if a["categoria"] else "N/A"

                    grupo_vis = a["grupo"].strip().title()
                    sub_vis = a["subgrupo"].strip().title()

                    col_tit, col_grp, col_sub, col_nota, col_tier, col_exclir = (
                        st.container(border=True).columns([2, 2, 2, 2, 0.5, 0.5]))

                    # Título
                    with col_tit:
                        st.markdown(
                            f"<div style='font-size:16px;font-weight:600;margin-top:8px;'>"
                            f"{ticker} — {nome} <span style='color:#777'>({categoria})</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    
                    # Atualiza grupo/subgrupo
                    def atualizar_ativo_select(key, fk_ativo, campo):
                        valor_vis = st.session_state[key]
                        valor_norm = valor_vis.strip().upper()

                        for ativo in state["ativos"]:
                            ativo_fk = (ativo.get("fk_ativo") or ativo.get("id_ativo") or ativo.get("ativo_cat") )
                            if ativo_fk == fk_ativo:
                                ativo[campo] = valor_norm
                                break

                    # Grupo (VISUAL)
                    grupos_vis = [g.title() for g in state["grupos"]]

                    col_grp.selectbox( "grupo", grupos_vis, key=f"grupo_{fk_ativo}",
                        index=grupos_vis.index(grupo_vis), label_visibility="collapsed",
                        on_change=atualizar_ativo_select,
                        kwargs={ "key": f"grupo_{fk_ativo}",  "fk_ativo": fk_ativo, "campo": "grupo", } )

                    # Subgrupo (VISUAL)
                    subs_vis = [s.title() for s in state["subgrupos"]]

                    col_sub.selectbox( "subgrupo", subs_vis, key=f"sub_{fk_ativo}",
                        index=subs_vis.index(sub_vis), label_visibility="collapsed",
                        on_change=atualizar_ativo_select,
                        kwargs={"key": f"sub_{fk_ativo}", "fk_ativo": fk_ativo, "campo": "subgrupo"}
                    )

                    # Atualiza nota
                    def atualizar_nota(key, fk_ativo):
                        valor = st.session_state[key]

                        for ativo in state["ativos"]:                           
                            ativo_fk = ( ativo.get("fk_ativo") or ativo.get("id_ativo") or ativo.get("ativo_cat") )
                            if ativo_fk == fk_ativo:
                                ativo["nota"] = valor
                                ativo["tier"], _ = get_tier(valor)
                                break

                    # Nota
                    nota = col_nota.slider( "nota", 0, 10, int(a.get("nota", 1)), step=1,
                        key=f"nota_{fk_ativo}", label_visibility="collapsed", on_change=atualizar_nota,
                        kwargs={"key": f"nota_{fk_ativo}", "fk_ativo": fk_ativo} )

                    # Tier visual
                    tier, icone_tier = get_tier(nota)
                    cor_tier = {"TIER 1": "#FFD700", "TIER 2": "#C0C0C0", "TIER 3": "#CD7F32"}.get(tier, "#7608F3")

                    with col_tier:
                        st.markdown(
                            f"""
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="color: {cor_tier}; font-size: 22px;">{icone_tier}</span>
                                <span style="font-size: 0.8rem; color: rgba(49, 51, 63, 0.6);">{tier.title()}</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Excluir / Pausar
                    def excluir_ativo(ticker):
                        ativos = state["ativos"]

                        for ativo in ativos:
                            ativo_fk = ( ativo.get("fk_ativo") or ativo.get("id_ativo") or ativo.get("ativo_cat") )
                            if ativo_fk == ticker:
                                t_nome = ativo.get("ticker", "")
                                if ativo.get("origem") == "api":
                                    ativo["nota"] = 0
                                    ativo["tier"], _ = get_tier(0)
                                    st.session_state[ f"nota_{fk_ativo}" ] = 0
                                    st.toast(f"⏸️ Ativo {ticker} pausado (nota zero).")
                                    return

                                state["ativos"] = [x for x in ativos if ( x.get("fk_ativo") or x.get("id_ativo") or x.get("ativo_cat") ) != fk_ativo]
                                st.toast(f"🗑️ Ativo {ticker} removido.")
                                return
                
                    with col_exclir:
                        st.button( "🗑️", key=f"wizard_excluir_{fk_ativo}", on_click=excluir_ativo, args=(fk_ativo,))

    #-----------------------------------------------------------------------------------------
    st.subheader("📌 Passo 1 — Adicione os ativos e personalize grupos/subgrupos")
    state["pesos_grupos"] = {}
    state["pesos_subgrupos"] = {}
    state["pesos_macro"] = {}
    # ------------------------------------------------------------
    # COLUNAS: BUSCADOR | NOVO GRUPO | NOVO SUBGRUPO
    # ------------------------------------------------------------
    componente_barra_adicao_rapida(state, prefixo_key="etapa1")

    st.divider()

    # ------------------------------------------------------------
    # MAPEAMENTO DOS ATIVOS — TÍTULO + GRUPO + SUBGRUPO
    # ------------------------------------------------------------
    if state["ativos"]:
        avaliar_classificar_ativos_etapa_1(state)
    else:
        st.info("Nenhum ativo adicionado ainda.")

def etapa2(state):

    def inicializar_macro(state):
        ativos = state["ativos"]

        brasil = 0
        exterior = 0

        for a in ativos:
            # macro interno sempre UPPER
            macro = (a.get("macro", "BRASIL") or "").strip().upper()

            if macro == "BRASIL":
                brasil += 1
            else:
                exterior += 1

        total = brasil + exterior

        if total == 0:
            # fallback interno (UPPER)
            state["pesos_macro"] = {"BRASIL": 50.0, "EXTERIOR": 50.0}
            return

        state["pesos_macro"] = {
            "BRASIL": round(brasil / total * 100, 2),
            "EXTERIOR": round(exterior / total * 100, 2),
        }

    def inicializar_pesos_grupos(state):
        ativos = state["ativos"]

        # Normaliza grupos (UPPER)
        grupos = { (a["grupo"] or "").strip().upper() for a in ativos }

        total = len(ativos) or 1

        state["pesos_grupos"] = {
            g: round(
                (sum(1 for a in ativos if (a["grupo"] or "").strip().upper() == g) / total) * 100,
                2
            )
            for g in grupos
        }

    def inicializar_pesos_subgrupos(state):
        ativos = state["ativos"]
        pesos = {}

        # Normaliza grupos
        grupos = { (a["grupo"] or "").strip().upper() for a in ativos }

        for g in grupos:
            # Normaliza subgrupos
            subgrupos = [
                (a["subgrupo"] or "").strip().upper()
                for a in ativos
                if (a["grupo"] or "").strip().upper() == g
            ]

            total = len(subgrupos) or 1

            pesos[g] = {
                sg: round((subgrupos.count(sg) / total) * 100, 2)
                for sg in set(subgrupos)
            }

        state["pesos_subgrupos"] = pesos

    def calcular_diferenca_total(total_atual, alvo=100):
        """
        total_atual: soma dos pesos da seção (grupos, subgrupos de um grupo, tiers)
        alvo: valor desejado (default 100)
        retorna (diff, icone, cor)
        """
        diff = alvo - total_atual
        if diff == 0:
            return diff, "✅", "#4CAF50"      # ok
        elif diff > 0:
            return diff, "⬆️", "#1976D2"     # falta aumentar
        else:
            return diff, "⬇️", "#D32F2F"     # precisa reduzir

    def renderizar_distribuicoes_grupos(state):
        st.markdown("### 📊 Distribuição dos Pesos (em %)")

        col1, col2, col3, col4 = st.columns(4)

        ativos = state["ativos"]

        # ---------------- MACRO ----------------
        with col1:
            st.write("**Por Macro (Maior → Menor)**")

            # conta ativos por macro
            contagem_macro = {}
            for a in ativos:
                macro = a["macro"].strip().upper()
                contagem_macro.setdefault(macro, 0)
                contagem_macro[macro] += 1

            total_macro = sum(state["pesos_macro"].values()) or 1

            for nome, peso in sorted(state["pesos_macro"].items(), key=lambda x: x[1], reverse=True):
                nome_vis = f"🇧🇷 {nome}" if nome == "BRASIL" else f"🌎 {nome}"
                nome_vis = nome_vis.title()

                pct = (peso / total_macro) * 100
                count = contagem_macro.get(nome.strip().upper(), 0)
                media = pct / count if count else pct

                dados = {"pct": pct, "count": count, "media_pct": media}
                barra_colorida(nome_vis, dados, "#8E24AA")

        # ---------------- GRUPO ----------------
        with col2:
            st.write("**Por Grupo (Maior → Menor)**")

            contagem_grupos = {}
            for a in ativos:
                g = a["grupo"].strip().upper()
                contagem_grupos.setdefault(g, 0)
                contagem_grupos[g] += 1

            total_grupos = sum(state["pesos_grupos"].values()) or 1

            for nome, peso in sorted(state["pesos_grupos"].items(), key=lambda x: x[1], reverse=True):
                nome_vis = f"{icone_grupo(nome.title())} {nome.title()}"

                pct = (peso / total_grupos) * 100
                count = contagem_grupos.get(nome.strip().upper(), 0)
                media = pct / count if count else pct

                dados = {"pct": pct, "count": count, "media_pct": media}
                barra_colorida(nome_vis, dados, "#1976D2")

        # ---------------- SUBGRUPO ----------------
        with col3:
            st.write("**Por Subgrupo (Maior → Menor)**")

            contagem_sub = {}
            for a in ativos:
                sg = a["subgrupo"].strip().upper()
                contagem_sub.setdefault(sg, 0)
                contagem_sub[sg] += 1

            for grupo, subgrupos in state["pesos_subgrupos"].items():
                total_sub = sum(subgrupos.values()) or 1
                grupo_vis = grupo.title()

                for sg, peso in sorted(subgrupos.items(), key=lambda x: x[1], reverse=True):
                    sg_vis = sg.title()

                    pct = (peso / total_sub) * 100
                    count = contagem_sub.get(sg.strip().upper(), 0)
                    media = pct / count if count else pct

                    dados = {"pct": pct, "count": count, "media_pct": media}
                    barra_colorida(f"{sg_vis} ({grupo_vis})", dados, "#43A047")

        # ---------------- TIER ----------------
        with col4:
            st.write("**Por Tier (Maior → Menor)**")

            contagem_tier = {}
            for a in ativos:
                tier, _ = get_tier(a["nota"])
                tier = tier.strip().upper()
                contagem_tier.setdefault(tier, 0)
                contagem_tier[tier] += 1

            total_tiers = sum(state["pesos_tiers"].values()) or 1

            for nome, peso in sorted(state["pesos_tiers"].items(), key=lambda x: x[1], reverse=True):
                nome_vis = f"{icone_tier(nome)} {nome}"

                pct = (peso / total_tiers) * 100
                count = contagem_tier.get(nome.strip().upper(), 0)
                media = pct / count if count else pct

                dados = {"pct": pct, "count": count, "media_pct": media}
                barra_colorida(nome_vis, dados, "#FB8C00")

    def validar_etapa2(state):
        erros = []

        # Grupos
        soma_grupos = sum(state["pesos_grupos"].values())
        if soma_grupos != 100:
            erros.append("Grupos devem somar 100%.")

        # Subgrupos
        for g, subpesos in state["pesos_subgrupos"].items():
            soma_sub = sum(subpesos.values())
            if soma_sub != 100:
                erros.append(f"Subgrupos de {g.title()} devem somar 100%.")

        # Tiers
        soma_tiers = sum(state["pesos_tiers"].values())
        if soma_tiers != 100:
            erros.append("Tiers devem somar 100%.")

        state["etapa2_ok"] = (len(erros) == 0)
        state["etapa2_erros"] = erros

    def label_categoria(g, campo):
        g_norm = g.strip().upper()
        g_vis = g_norm.title()
        icon = icone_grupo(g_vis)

        peso_atual = st.session_state.get( f"slider_grupo_{g}", state["pesos_grupos"].get(g, 0) )

        # contar ativos
        count = 0
        for a in state["ativos"]:
            if str(a[campo]).strip().upper() == g_norm:
                count += 1

        media = peso_atual / count if count else 0

        st.session_state[f"resp_slider_grupo_{g}"] = ( f"{icon} {g_vis} — {count} ativos • média {media:.1f}%" )

    def label_macro():
        macro_norm = "BRASIL"
        macro_vis = macro_norm.title()

        icon = "🇧🇷"

        peso_atual = st.session_state.get(
            f"slider_macro_{macro_norm}",
            state["pesos_macro"].get(macro_norm, 0)
        )

        # contar ativos
        count = 0
        count_ex = 0
        for a in state["ativos"]:
            if str(a["macro"]).strip().upper() == macro_norm:
                count += 1
            else:
                count_ex += 1

        media = peso_atual / count if count else 0
        media_ex = (100 - peso_atual) / count_ex if count_ex else 0

        st.session_state[f"resp_slider_macro_{macro_norm}"] = (
            f"{icon} {macro_vis} — {count} ativos • média {media:.1f}%"
        )

        st.session_state["resp_slider_macro_EXTERIOR"] = (
            f"🌎 Exterior — {count_ex} ativos • média {media_ex:.1f}%"
        )

    def label_subgrupo(g, sg):
        g_norm = g.strip().upper()
        sg_norm = sg.strip().upper()

        sg_vis = sg_norm.title()

        peso_atual = st.session_state.get(
            f"slider_sub_{g}_{sg}",
            state["pesos_subgrupos"].get(g, {}).get(sg, 0)
        )

        # contar ativos do subgrupo
        count = 0
        for a in state["ativos"]:
            if str(a["grupo"]).strip().upper() == g_norm and str(a["subgrupo"]).strip().upper() == sg_norm:
                count += 1

        media = peso_atual / count if count else 0

        st.session_state[f"resp_slider_sub_{g}_{sg}"] = (
            f"{sg_vis} — {count} ativos • média {media:.1f}%"
        )

    def label_tier(tier_nome):
        tier_norm = tier_nome.strip().upper()
        tier_vis = tier_norm.title()
        icon = icone_tier(tier_norm)

        peso_atual = st.session_state.get( f"slider_tier_{tier_norm}", state["pesos_tiers"].get(tier_norm, 0))

        # contar ativos do tier
        count = 0
        for a in state["ativos"]:
            if str(a["tier"]).strip().upper() == tier_norm:
                count += 1

        media = peso_atual / count if count else 0

        st.session_state[f"resp_slider_tier_{tier_norm}"] = (f"{icon} {tier_vis} % — {count} ativos • média {media:.1f}%")
  
    # ============================================================
    # Inicialização automática dos pesos (somente na primeira vez)
    # ============================================================

    if not state["pesos_macro" ]:
        inicializar_macro(state)

    if not state["pesos_grupos"]:
        inicializar_pesos_grupos(state)

    if not state["pesos_subgrupos"]:
        inicializar_pesos_subgrupos(state)

    st.subheader("🎚️ Passo 2 — Definir Pesos da Estrutura")

    st.markdown( "Ajuste sua alocação de forma visual e intuitiva. "
        "Use os controles deslizantes para definir proporções por macro, grupo, subgrupo e tier.")

    # ============================================================
    # 🌎 Linha 1 — Macro / Grupo / Subgrupo / Tier
    # ============================================================
    st.markdown("### 🌎 Estrutura de Alocação")

    col_macro, col_grupo, col_sub, col_tier = st.columns(4)

    # ------------------------------------------------------------
    # MACRO
    # ------------------------------------------------------------
    with col_macro:
        cm, im = st.columns([1, 0.5], width='stretch')
        cm.markdown("**(🇧🇷 Brasil x 🌎 Exterior)**")

        if "resp_slider_macro_BRASIL" not in st.session_state:
            label_macro()

        label = st.session_state["resp_slider_macro_BRASIL"]

        brasil = st.slider(label, 0, 100, int(state["pesos_macro"]["BRASIL"]),
                            step=1, key="slider_macro_BRASIL", on_change=label_macro )

        exterior = 100 - brasil

        state["pesos_macro"]["BRASIL"] = brasil
        state["pesos_macro"]["EXTERIOR"] = exterior

        st.markdown(
            f"""
            <div style="background:#e0e0e0;border-radius:6px;overflow:hidden;height:10px;">
                <div style="width:{exterior}%;background:#2196F3;height:10px;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(
            f"{st.session_state['resp_slider_macro_EXTERIOR']} — **{exterior}%**"
        )

        im.markdown("✅ Macro 100%", unsafe_allow_html=True)

    # ------------------------------------------------------------
    # GRUPOS
    # ------------------------------------------------------------
    with col_grupo:
        c, i, _ = st.columns([1, 1, 2], width='stretch')
        c.markdown("**Grupos**")

        grupos_unicos = sorted({a["grupo"] for a in state["ativos"]})
        novos_pesos_grupos = {}

        for g in grupos_unicos:
            if f"resp_slider_grupo_{g}" not in st.session_state:
                label_categoria(g, "grupo")

            label = st.session_state[f"resp_slider_grupo_{g}"]

            peso = st.slider( label, 0, 100, int(state["pesos_grupos"].get(g, 0)), step=1, key=f"slider_grupo_{g}", 
                             on_change=label_categoria, kwargs={"g": g, "campo": "grupo"})

            novos_pesos_grupos[g] = peso

        state["pesos_grupos"] = novos_pesos_grupos

        soma_grupos = sum(novos_pesos_grupos.values())
        diff_g, icone_g, cor_g = calcular_diferenca_total(soma_grupos)

        i.markdown(
            f"<span style='color:{cor_g}'>{icone_g} {abs(diff_g):.1f}%</span>",
            unsafe_allow_html=True,)


    # ------------------------------------------------------------
    # SUBGRUPOS
    # ------------------------------------------------------------
    with col_sub:
        st.markdown("**Subgrupos**")

        novos_pesos_sub = {}

        for g in grupos_unicos:
            g_vis = g.title()

            c, i = st.columns([5, 1], width='stretch')
            with c.expander(f"{icone_grupo(g_vis)} {g_vis}", expanded=False):

                subgrupos_do_grupo = [ a["subgrupo"] for a in state["ativos"] if a["grupo"] == g]
                subgrupos_unicos = sorted(set(subgrupos_do_grupo))

                pesos_sub = {}

                for sg in subgrupos_unicos:
                    # inicializar label se não existir
                    if f"resp_slider_sub_{g}_{sg}" not in st.session_state:
                        label_subgrupo(g, sg)

                    label = st.session_state[f"resp_slider_sub_{g}_{sg}"]

                    peso = st.slider(label, 0, 100, int(state["pesos_subgrupos"].get(g, {}).get(sg, 0)),
                                     step=1, key=f"slider_sub_{g}_{sg}", on_change=label_subgrupo,
                                     kwargs={"g": g, "sg": sg})

                    pesos_sub[sg] = peso

                soma_sub = sum(pesos_sub.values())
                diff_s, icone_s, cor_s = calcular_diferenca_total(soma_sub)

                novos_pesos_sub[g] = pesos_sub

            i.markdown(f"<span style='color:{cor_s}'>{icone_s} {abs(diff_s):.1f}%</span>", unsafe_allow_html=True,)

    state["pesos_subgrupos"] = novos_pesos_sub


    # ------------------------------------------------------------
    # TIERS
    # ------------------------------------------------------------
    with col_tier:
        c, i, _ = st.columns([1, 2, 3], width='stretch')
        c.markdown("**Tiers**")

        # inicializar labels
        for tier_nome in ["TIER 1", "TIER 2", "TIER 3"]:
            if f"resp_slider_tier_{tier_nome}" not in st.session_state:
                label_tier(tier_nome)

        label_t1 = st.session_state["resp_slider_tier_TIER 1"]
        t1 = st.slider(label_t1, 0, 100, int(state["pesos_tiers"]["TIER 1"]), step=1,
                        key="slider_tier_TIER 1", on_change=label_tier, kwargs={"tier_nome": "TIER 1"})
        
        label_t2 = st.session_state["resp_slider_tier_TIER 2"]
        t2 = st.slider(label_t2, 0, 100, int(state["pesos_tiers"]["TIER 2"]), step=1,
                        key="slider_tier_TIER 2", on_change=label_tier, kwargs={"tier_nome": "TIER 2"})

        label_t3 = st.session_state["resp_slider_tier_TIER 3"]         
        t3 = st.slider(label_t3, 0, 100, int(state["pesos_tiers"]["TIER 3"]), step=1,
                        key="slider_tier_TIER 3", on_change=label_tier, kwargs={"tier_nome": "TIER 3"})

        state["pesos_tiers"] = {"TIER 1": t1, "TIER 2": t2, "TIER 3": t3}

        soma_tiers = t1 + t2 + t3
        diff_t, icone_t, cor_t = calcular_diferenca_total(soma_tiers)

        i.markdown(f"<span style='color:{cor_t}'>{icone_t} {abs(diff_t):.1f}%</span>", unsafe_allow_html=True,)

        regra = st.radio( "Regra de distribuição", ["Igual", "Proporcional à Nota"], key="regra_tier_radio", )

        state["regra_tier"] = regra.strip().upper()

    st.divider()

    # ============================================================
    # 📋 Linha 2 — Resumo visual compacto
    # ============================================================
    renderizar_distribuicoes_grupos(state)
    validar_etapa2(state)

def etapa3(state):

    def houve_alteracoes(list_editado):
        """Compara a lista editada com o cache original seguindo as regras LEGACY SEED."""
        dados_cache = st.session_state.get("dados_carteira_cache", [])
        if not list_editado or not dados_cache:
            return False

        # Mapeia cache por ticker
        cache_map = {}
        for item in dados_cache:
            key_id = item.get("fk_ativo") or item.get("ativo_cat") or item.get("ticker") or item.get("codigo_ativo") or item.get("Ativo") 
            if key_id:
                cache_map[key_id] = item
        
        for linha in list_editado:
            key_id = linha.get("fk_ativo") or linha.get("ativo_cat") or linha.get("ticker") or linha.get("codigo_ativo") or linha.get("Ativo")
            if key_id not in cache_map:
                return True

            original = cache_map[key_id]
            # -----------------------------
            # GRUPO
            # -----------------------------
            grupo_edit = str(linha.get("Grupo", "")).strip().upper()
            grupo_orig = str( original.get("grupo") or original.get("Grupo") or "" ).strip().upper()

            if grupo_edit != grupo_orig:
                return True

            # -----------------------------
            # SUBGRUPO
            # -----------------------------
            sub_edit = str(linha.get("Subgrupo", "")).strip().upper()
            sub_orig = str( original.get("subgrupo") or original.get("Subgrupo") or "" ).strip().upper()

            if sub_edit != sub_orig:
                return True

            # -----------------------------
            # NOTA (somente se regra ativa)
            # -----------------------------
            nota_edit = int(linha.get("Nota") or 0)
            nota_orig = int(original.get("nota") or 0)

            if nota_edit != nota_orig:
                return True

            # -----------------------------
            # PESO (somente se modo manual)
            # -----------------------------
            peso_edit = int(linha.get("Peso") or 0)
            peso_orig = int(round(float(original.get("peso") or 0)))

            if peso_edit != peso_orig:
                return True

        return False

    def atualizar_ativos_editados(df_editado, ativos_totais):
        """Atualiza a lista completa de ativos sem perder os ativos ocultos por filtros."""
        # 🛠️ Mapeia linhas editadas via fk_ativo (fallback ticker)
        mapa_editados = {}
        for row in df_editado:
            key_id = row.get("fk_ativo") or row.get("Ativo")
            if key_id:
                mapa_editados[key_id] = row

        novos = []

        for a in ativos_totais:
            key_id = a.get("fk_ativo") or a.get("ativo_cat")

            if key_id in mapa_editados:
                row = mapa_editados[key_id]

                nota = int(row["Nota"])
                tier, _ = get_tier(nota)
                peso = int(float(row["Peso"])) # peso manual

                novos.append(
                                {
                                    **a,
                                    "grupo": str(row["Grupo"]).strip().upper(),
                                    "subgrupo": str(row["Subgrupo"]).strip().upper(),
                                    "nota": nota,
                                    "tier": tier,
                                    "peso": peso,
                                }
                            )
            else:
                novos.append(a)

        return novos

    # -------------------------------------------------------------
    # MODO WIZARD / HOME
    # -------------------------------------------------------------
    if state.get("modo_wizard", True):
        col1, col2 = st.columns([1.2, 1], gap="medium")
        col1.subheader("📋 Revisão Final — Nada foi salvo ainda")
        if col1.button("🔄 Refazer Planejamento Guiado"):
            state["etapa"] = 1
    else:
        col1, col2 = st.columns([1.2, 1], gap="medium")
        col1.subheader("✏️ Editar Planejamento Atual")
        col1.info("Edite seu planejamento e clique em **Salvar Alterações**.")
    
    # -------------------------------------------------------------
    # FILTRO DE GRUPOS
    # -------------------------------------------------------------
    filtro = col2.container( horizontal=True, border=True, vertical_alignment="center", width="stretch" )

    with filtro:
        def parcial_save():
            if 'preview_ativos' in state:
                state["ativos"] = state['preview_ativos']
        list_grupo = [a["grupo"] for a in state["ativos"]]
        categorias_selecionadas = componente_seletor_categorias(list_grupo, "key_grupo_selecionado", "Grupo", callback_sl=parcial_save )

    dados_filtrados = list(state["ativos"])
    if categorias_selecionadas:
        grupos_sel = {g.strip().upper() for g in categorias_selecionadas}
        dados_filtrados = [ item for item in dados_filtrados if str(item.get("grupo", "")).strip().upper() in grupos_sel ]

    # -------------------------------------------------------------
    # TIPO DE GRÁFICO
    # -------------------------------------------------------------
    tipo_grafico = filtro.selectbox( "Visualização do Gráfico", label_visibility="collapsed", options=["Pizza", "Diagrama"],
        index=0, key="select_tipo_grafico_edit", width=150 )


    # -------------------------------------------------------------
    # BARRA DE AÇÕES: ADICIONAR ATIVO / GRUPO / SUBGRUPO
    # -------------------------------------------------------------
    if st.checkbox('Adicionar dados'):
        componente_barra_adicao_rapida(state, prefixo_key="etapa3")
    # -------------------------------------------------------------
    # DIVISÃO DA TELA
    # -------------------------------------------------------------
    col_tabela, col_grafico = st.columns([1.2, 1], gap="medium")

    # -------------------------------------------------------------
    # LISTA PARA EDIÇÃO (UI)
    # -------------------------------------------------------------
    # 🛠️ Indexação interna por fk_ativo para normalização dos pesos
    pesos_norm = { (a.get("fk_ativo") or a.get("ativa_cat") or a.get("ticker")): float(a.get("peso", 0.0)) for a in state.get("ativos", []) }

    list_edit = []
    for a in dados_filtrados:
        key_id = a.get("fk_ativo") or a.get("ativo_cat")
        list_edit.append({
            "fk_ativo": key_id,  # Armazenado para controle do editor (não visível)
            "Ativo": a.get("ticker", ""),   # VISUAL: Ticker exibido ao usuário
            "Macro": str(a["macro"]).title(),
            # VIEW → Title Case
            "Grupo": str(a["grupo"]).title(),
            "Subgrupo": str(a["subgrupo"]).title(),
            "Nota": int(float(a["nota"])),
            "Peso": int(round(pesos_norm.get(key_id, 0.0))),
        })
    # -------------------------------------------------------------
    # ORDENAR (LEGACY SEED)
    # -------------------------------------------------------------
    list_edit = sorted( list_edit, key=lambda x: ( x["Grupo"].strip().upper(), x["Subgrupo"].strip().upper(), -x["Peso"], -x["Nota"], ) )
    # -------------------------------------------------------------
    # CONFIGURAÇÃO DAS COLUNAS
    # -------------------------------------------------------------
    grupo_wiew = [g.title() for g in state["grupos"]]
    subgrupo_wiew = [g.title() for g in state["subgrupos"]]
    colunas_config = {
        "Ativo": st.column_config.TextColumn("Ativo", disabled=True),
        "Macro": st.column_config.TextColumn("Macro", disabled=True),
        "Grupo": st.column_config.SelectboxColumn("Grupo", options=list(grupo_wiew), required=True ),
        "Subgrupo": st.column_config.SelectboxColumn("Subgrupo", options=list(subgrupo_wiew), required=True ),
        "Nota": st.column_config.NumberColumn( "Nota", min_value=0, max_value=10, step=1, format="%d ⭐", required=True ),
        "Peso": st.column_config.NumberColumn( "Peso", min_value=0, step=1, format="plain", required=True ),
    }
    
    # -------------------------------------------------------------
    # DATA EDITOR
    # -------------------------------------------------------------
    list_editado = col_tabela.data_editor( list_edit,
                                            hide_index=True,
                                            column_config=colunas_config,
                                            column_order=["Ativo", "Macro", "Grupo", "Subgrupo", "Nota", "Peso"],
                                            key="data_editor_planejamento",
                                            num_rows="fixed",
                                            height=450,
                                            width="stretch", )

    # -------------------------------------------------------------
    # NORMALIZAÇÃO DE CAMPOS DA UI
    # -------------------------------------------------------------
    grupo_padrao = state["grupos"][0] if state["grupos"] else ""
    subgrupo_padrao = state["subgrupos"][0] if state["subgrupos"] else ""

    for linha in list_editado:
        linha["Nota"] = int(float(linha.get("Nota") or 0))
        linha["Peso"] = int(float(linha.get("Peso") or 0))

        # interno → UPPER
        linha["Grupo"] = str(linha.get("Grupo") or grupo_padrao).strip().upper()
        linha["Subgrupo"] = str(linha.get("Subgrupo") or subgrupo_padrao).strip().upper()

    # -------------------------------------------------------------
    # DETECTAR ALTERAÇÕES
    # -------------------------------------------------------------
    alteracoes_pendentes = houve_alteracoes(list_editado)

    if alteracoes_pendentes:
        st.warning("⚠️ Alterações detectadas. Clique em **Salvar Planejamento**.")
    else:
        st.info("Nenhuma alteração pendente.")

    # -------------------------------------------------------------
    # GRÁFICO (MANTIDO EXATAMENTE COMO VOCÊ PEDIU)
    # -------------------------------------------------------------
    with col_grafico:
        df_view_chart = pd.DataFrame(list_editado)

        if tipo_grafico == "Pizza":
            fig_sunburst = create_sunburst_chart(df_view_chart)
            if fig_sunburst:
                st.plotly_chart(fig_sunburst, width="stretch")

        elif tipo_grafico == "Diagrama":
            fig_sankey = create_sankey_chart(df_view_chart)
            if fig_sankey:
                st.plotly_chart(fig_sankey, width="stretch")

    # -------------------------------------------------------------
    # ATUALIZAR ATIVOS EDITADOS
    # -------------------------------------------------------------
    novos = atualizar_ativos_editados(list_editado, state["ativos"])
    state["preview_ativos"] = novos

    # -------------------------------------------------------------
    # REPROCESSAR DISTRIBUIÇÕES (AGORA SIM, FILTRADA E EDITADA)
    # -------------------------------------------------------------
    ativos_filtrados_editados = [
        {
            "fk_ativo": linha.get("fk_ativo"),
            "ticker": linha["Ativo"],
            "macro": linha["Macro"],
            "grupo": linha["Grupo"],
            "subgrupo": linha["Subgrupo"],
            "nota": linha["Nota"],
            "peso": linha["Peso"],
        }
        for linha in list_editado
    ]

    dist_filtrada = calcular_distribuicoes(ativos_filtrados_editados)
    renderizar_distribuicoes(dist_filtrada)

def pagina_inicial(state):

    def tabela_grafico_home(dados_filtrados, tipo_grafico):
        col_tabela, col_grafico = st.columns([1.2, 1], gap="medium")

        soma_pesos = sum(a.get("peso", 0) for a in dados_filtrados)

        list_view = []
        for a in dados_filtrados:

            # VISUAL (sem upper)
            grupo_vis = a["grupo"].title() if a["grupo"] else ""
            subgrupo_vis = a["subgrupo"].title() if a["subgrupo"] else ""
            macro_vis = a["macro"].title() if a["macro"] else ""

            tier, icone = get_tier(a["nota"])

            list_view.append({
                "fk_ativo": a.get( "fk_ativo", a.get("ativo_cat", a.get("ticker"))),
                "Ativo": a["ticker"],
                "Macro": macro_vis,
                "Grupo": grupo_vis,
                "Subgrupo": subgrupo_vis,
                "Nota": a["nota"],
                "Peso": a["peso"],
                "Tier": f"{icone} {tier}".title(),
                "%": a["peso"] / soma_pesos if soma_pesos > 0 else 0,
            })

        # Ordenação LEGACY SEED (UPPER para lógica)
        list_view = sorted( list_view, key=lambda x: ( x["Grupo"].strip().upper(), x["Subgrupo"].strip().upper(), -x["Peso"], -x["Nota"], ), )

        colunas_config = {
            "Ativo": st.column_config.TextColumn("Ativo"),
            "Macro": st.column_config.TextColumn("Macro"),
            "Grupo": st.column_config.TextColumn("Grupo"),
            "Subgrupo": st.column_config.TextColumn("Subgrupo"),
            "Nota": st.column_config.ProgressColumn("Nota", min_value=0, max_value=10, format="%d ⭐"),
            "Peso": st.column_config.NumberColumn("Peso", format="plain"),
            "Tier": st.column_config.TextColumn("Tier"),
            "%": st.column_config.ProgressColumn("%", min_value=0, max_value=1, format="percent"),
        }

        col_tabela.dataframe(
            list_view,
            hide_index=True,
            column_order=[ "Ativo", "Macro", "Grupo", "Subgrupo", "Nota", "Peso", "Tier", "%" ],
            column_config=colunas_config,
            height=450,
            width="stretch",
        )

        with col_grafico:
            df_view_chart = pd.DataFrame(list_view)

            if tipo_grafico == "Pizza":
                fig_sunburst = create_sunburst_chart(df_view_chart)
                if fig_sunburst:
                    st.plotly_chart(fig_sunburst, width="stretch")

            elif tipo_grafico == "Diagrama":
                fig_sankey = create_sankey_chart(df_view_chart)
                if fig_sankey:
                    st.plotly_chart(fig_sankey, width="stretch")

    # ------------------------------------------------------------------------------------------
    col1, col2 = st.columns([1.2, 1], gap="medium")
    col1.subheader("🌳 Objetivos 🎯")

    # Seletor de Categoria / Filtros
    filtro = col2.container(horizontal=True, border=True, vertical_alignment="center", width="stretch")
    with filtro:

        # VISUAL: grupos em Title Case
        grupos = [a["grupo"] for a in state["ativos"]]
        categorias_selecionadas = componente_seletor_categorias( grupos, "key_grupo_selecionado", "Grupo" )

        dados_filtrados = list(state["ativos"])

        if categorias_selecionadas:
            # LÓGICA: normaliza para UPPER
            categorias_norm = [c.upper() for c in categorias_selecionadas]

            dados_filtrados = [ item for item in dados_filtrados 
                                if item.get("grupo") in categorias_norm ]

    # Botões de Navegação
    with col1.container(horizontal=True, horizontal_alignment="left"):

        def resetar_wizard(state):
            state["etapa"] = 1
            state["modo_wizard"] = True

        def entrar_modo_edicao(state):
            state["etapa"] = 3
            state["modo_wizard"] = False

        st.button( "🔄 Refazer Planejamento Guiado", on_click=lambda: resetar_wizard(state), width="stretch", )
        st.button( "✏️ Editar Planejamento", on_click=lambda: entrar_modo_edicao(state), width="stretch", )

    # Selectbox para alternar a visualização
    tipo_grafico = filtro.selectbox( "Visualização do Gráfico", label_visibility="collapsed", options=["Pizza", "Diagrama"],
                                        index=0, key="select_tipo_grafico_home", width=150 )

    # Resumo visual
    tabela_grafico_home(dados_filtrados, tipo_grafico)

    # Recalcula distribuições consolidadas
    dist = calcular_distribuicoes(dados_filtrados)
    renderizar_distribuicoes(dist)

# ============================================================
# EXECUÇÃO DO WIZARD
# ============================================================

def executar_wizard(state):
    etapa = state["etapa"]
    if etapa <= 3 and  state["modo_wizard"] == True:
        # Barra de progresso do wizard
        total_etapas = 3
        progresso = (etapa / total_etapas) * 100

        st.markdown(
            f"""
            <div style="margin-bottom:15px;">
                <div style="background:#e0e0e0;border-radius:6px;overflow:hidden;height:12px;">
                    <div style="width:{progresso}%;background:#2196F3;height:12px;"></div>
                </div>
                <p style="text-align:center;font-weight:500;color:#2196F3;margin-top:4px;">
                    Etapa {etapa} de {total_etapas}
                </p>
            </div>
            """,
        unsafe_allow_html=True, )

    with st.container(horizontal_alignment="distribute", horizontal=True):
        col1 = st.container(horizontal_alignment="left")
        col2 = st.container(horizontal_alignment="right")

    if etapa == 1:
        etapa1(state)
    elif etapa == 2:
        etapa2(state)
    elif etapa == 3:
        etapa3(state)
    elif etapa == 4:
        pagina_inicial(state)

    with col1:
        # Wizard: voltar
        if etapa in [2, 3] and state["modo_wizard"]:
            if st.button("⬅️ Voltar"):
                state["etapa"] -= 1
                st.rerun()

        # Home: sair da edição
        elif etapa in [1, 3]:
            if st.button("⬅️ Objetivos 🌳🎯"):
                state["etapa"] = 4
                state["modo_wizard"] = False
                st.session_state.carregou_carteira = False
                st.rerun()

    with col2:
        # Wizard: avançar etapa 1
        if etapa == 1 and state["modo_wizard"] == True: 
            if st.button("Avançar ➡️"): 
                state["etapa"] = 2
                st.rerun()

        # Wizard: avançar etapa 2
        elif etapa == 2:
            if not state.get("etapa2_ok", False):
                st.error("⚠️ Ajuste necessário antes de avançar.")
            else:
                if st.button("Avançar ➡️"):
                    # calcular pesos automáticos aqui
                    pesos_norm = calcular_pesos_automaticos(state)
                    # salvar dentro dos ativos
                    for a in state["ativos"]:
                        a["peso"] = int(round(pesos_norm.get(a["ticker"], 0)))
                            
                    state["etapa"] = 3
                    st.rerun()
        # Salvar
        elif etapa == 3:
            if st.button("💾 Salvar Planejamento"):
                with st.spinner("Salvando configurações na carteira..."):
                    try:
                        # 1. Converte/Garante a estrutura exigida pelo Pydantic do backend
                        payload = [
                            {
                                "fk_ativo": item["fk_ativo"],
                                "grupo": item["grupo"],
                                "subgrupo": item["subgrupo"],
                                "nota": float(item.get("nota", 0)),
                                "peso": float(item.get("peso", 0)),
                            }
                            for item in state["preview_ativos"]
                        ]
                        if not payload:
                            st.warning("Não tem tados para ser enviado")
                            return
                        # 2. Dispara a requisição para a API
                        res = executar_requisicao_atualizar_planejamento_carteira(payload)

                        if not isinstance(res, dict):
                            st.warning("A resposta da API veio em um formato inesperado.")
                            return
                        
                        if st.session_state.get("fez_planejamento", True) == False:
                            executar_requisicao_atualizar_configuracoes(payload={"fez_planejamento": True})
                            
                        # 3. Atualiza o estado local e notifica o usuário
                        state["ativos"] = list(state["preview_ativos"])
                        state["etapa"] = 4
                        state["modo_wizard"] = False

                        st.session_state["toast_pendente"] = {
                                                                "mensagem": "✅ Planejamento salvo com sucesso!",
                                                                "icone": "🎉",
                                                            }
                        st.rerun()

                    except ApiRequestError as exc:
                        st.error(str(exc))

# ============================================================
# CHAMADA FINAL
# ============================================================
executar_wizard(state)
