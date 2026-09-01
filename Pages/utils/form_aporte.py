import streamlit as st
import pandas as pd
from plotly import graph_objects as go
from Pages.utils.components import st_number_input_custom
from Pages.utils.ferramentas import formatar_numero_para_br_str



def converter_limpo_series(series):
    """Vetorizado: Converte Series do Pandas contendo strings formatadas para float puros."""
    if series.dtype in ['float64', 'int64']:
        return series.astype(float)
    
    s = series.astype(str).str.replace(r'[%\$R\s]', '', regex=True)
    # Se contém ponto e vírgula -> padrão BR (1.000,50 -> 1000.50)
    has_both = s.str.contains(',') & s.str.contains(r'\.')
    s = s.where(~has_both, s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False))
    # Se contém apenas vírgula (1000,50 -> 1000.50)
    has_comma_only = s.str.contains(',') & ~s.str.contains(r'\.')
    s = s.where(~has_comma_only, s.str.replace(',', '.', regex=False))
    
    return pd.to_numeric(s, errors='coerce').fillna(0.0)

# --- WIDGETS DE INTERFACE ---

def widget_aporte_global():
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2])
        with c1:
            v_aporte = st_number_input_custom("Aporte", value="10.000", key="val_final")
        with c2:
            moeda = st.radio('Moeda', ['BRL', 'USD'], horizontal=True)
        with c3:
            st.write("") 
            with st.popover("➕ Criar Grupo", width='stretch'):
                sel_cats = st.pills(
                    "Selecione Categorias", 
                    selection_mode="multi", 
                    options=st.session_state['page_aportes']['categorias_disponiveis']
                )
                if st.button("Confirmar Agrupamento", width='stretch'):
                    if sel_cats:
                        nova_lista = []
                        for g in st.session_state['page_aportes']['lista_grupos']:
                            cats_restantes = [c for c in g['cats'] if c not in sel_cats]
                            if cats_restantes:
                                nova_lista.append({"cats": cats_restantes, "min": g['min'], "max": g['max']})
                        
                        nova_lista.append({"cats": sel_cats, "min": "5,00", "max": "50,00"})
                        st.session_state['page_aportes']['lista_grupos'] = nova_lista
                        st.rerun()
    return v_aporte, moeda

def widget_config_categorias(v_aporte, moeda):
    st.write("### 🛠️ Configuração de Limites do Aporte")
    state = st.session_state['page_aportes']
    configuracoes_grupos = []

    if state.get('lista_grupos'):
        cols = st.columns(len(state['lista_grupos']))

        for idx, grupo in enumerate(state['lista_grupos']):
            with cols[idx]:
                with st.container(border=True):
                    c_tit, c_del = st.columns([4, 1])
                    c_tit.markdown(f"**{' + '.join(grupo['cats'])}**")
                    
                    if c_del.button("✕", key=f"del_grp_{idx}", help="Remover grupo"):
                        state['lista_grupos'].pop(idx)
                        st.rerun()

                    c_min, c_max = st.columns(2)
                    with c_min:
                        v_min_float = st_number_input_custom("% Mín", value=grupo['min'], key=f"min_in_{idx}")
                        state['lista_grupos'][idx]['min_f'] = v_min_float
                    
                    with c_max:
                        v_max_float = st_number_input_custom("% Máx", value=grupo['max'], key=f"max_in_{idx}")
                        state['lista_grupos'][idx]['max_f'] = v_max_float

                    configuracoes_grupos.append({
                        "categorias": grupo['cats'],
                        "margem_minima": v_min_float,
                        "margem_maxima": v_max_float
                    })

    return {
        "valor_total_aporte": v_aporte,
        "moeda": moeda,
        "configuracao_grupos": configuracoes_grupos
    }

def widget_resultado_grupo(dados):
    if not dados:
        return
    
    # Vetorização do parsing de dados para velocidade
    df = pd.DataFrame(dados)
    
    df_clean = pd.DataFrame({
        "Grupo": df["grupo"],
        "Meta": converter_limpo_series(df["meta_estrategica"]) / 100,
        "Atual %": converter_limpo_series(df["percentual_atual"]) / 100,
        "Defasagem %": converter_limpo_series(df["percentual_defasagem"]) / 100,
        "Valor Planejado": converter_limpo_series(df["brl"].apply(lambda x: x["valor_objetivo"])),
        "Valor Atual": converter_limpo_series(df["brl"].apply(lambda x: x["valor_atual"])),
        "Defasagem Financeira": converter_limpo_series(df["brl"].apply(lambda x: x["defasagem_financeira"])),
        "Valor Aporte": converter_limpo_series(df["brl"].apply(lambda x: x["valor_aporte"])),
        "Aporte %": converter_limpo_series(df["percentual_no_aporte"]) / 100,
    })
    
    df_clean = df_clean.sort_values(by="Aporte %", ascending=False)
    
    # --- 1. Gráfico de Barras ---
    st.subheader("📊 Comparativo Visual: Atual vs Planejado")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_clean["Grupo"], y=df_clean["Valor Atual"], name='Atual (BRL)', marker_color='#1E88E5'))
    fig.add_trace(go.Bar(x=df_clean["Grupo"], y=df_clean["Valor Planejado"], name='Planejado (BRL)', marker_color='#FFA000'))
    fig.update_layout(barmode='group', height=350, template="plotly_white", margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig, width='stretch')

    # --- 2. Tabela Detalhada ---
    st.subheader("📋 Detalhamento da Estratégia")

    def aplicar_cores_estrategia(row):
        cor_defasagem = 'color: #D32F2F' if row['Defasagem Financeira'] < 0 else 'color: #388E3C'
        cor_defasagem_per = 'color: #D32F2F' if row['Defasagem %'] < 0 else 'color: #388E3C'
        bg_aporte = 'background-color: rgba(0, 255, 0, 0.1); font-weight: bold' if row['Valor Aporte'] > 0 else ''
        
        estilos = [''] * len(row)
        estilos[df_clean.columns.get_loc('Defasagem %')] = cor_defasagem_per
        estilos[df_clean.columns.get_loc('Defasagem Financeira')] = cor_defasagem
        estilos[df_clean.columns.get_loc('Valor Aporte')] = bg_aporte
        return estilos

    df_styled = (
        df_clean.style.apply(aplicar_cores_estrategia, axis=1)
        .format({
            "Meta": "{:.2%}",
            "Atual %": "{:.2%}",
            "Defasagem %": "{:+.2%}",
            "Valor Planejado": "R$ {:,.2f}",
            "Valor Atual": "R$ {:,.2f}",
            "Defasagem Financeira": "R$ {:,.2f}",
            "Valor Aporte": "R$ {:,.2f}",
            "Aporte %": "{:.2%}"
        }, decimal=',', thousands='.')
    )

    st.table(df_styled)

def widget_config_ativos(dist, moeda_padrao="BRL"):
    st.write("### ⚙️ Aportes por Grupo")
    state = st.session_state['page_aportes']
    
    if not state.get('moedas_por_grupo'):
        state['moedas_por_grupo'] = {item['grupo']: moeda_padrao.upper() for item in dist}

    payload_etapa2_dist = []
    
    if dist:
        cols = st.columns(len(dist))

        for idx, item in enumerate(dist):
            nome_exibicao = item.get("grupo")
            
            with cols[idx]:
                with st.container(border=True):
                    c_tit, c_moeda = st.columns([3, 3])
                    c_tit.markdown(f"**{nome_exibicao}**")
                    
                    moeda_salva = state['moedas_por_grupo'].get(nome_exibicao, moeda_padrao.upper())
                    chave_moeda = f"sel_moeda_{nome_exibicao}"
                    
                    if chave_moeda not in st.session_state:
                        st.session_state[chave_moeda] = moeda_salva

                    moeda_atual = c_moeda.radio(
                        "Moeda", ["BRL", "USD"],
                        horizontal=True,
                        key=chave_moeda,
                        label_visibility="collapsed"
                    )
                    state['moedas_por_grupo'][nome_exibicao] = moeda_atual
                    
                    sugestao_dinamica = item.get(moeda_atual.lower(), {}).get("valor_aporte", 0.0)
                    chave_valor = f"val_etapa2_{nome_exibicao}_{moeda_atual}"
                    
                    if chave_valor not in st.session_state:
                        st.session_state[chave_valor] = f"{float(sugestao_dinamica):.2f}".replace(".", ",")

                    c_val, c_max = st.columns(2)
                    with c_val:
                        valor_ajustado = st_number_input_custom(f"Valor ({moeda_atual})", key=chave_valor)
                    
                    with c_max:
                        porc_max = st_number_input_custom("% Máx/Ativo", value="20,00", key=f"max_input_{nome_exibicao}")
                    
                    lista_categorias = [cat.strip() for cat in nome_exibicao.split("+")]
                    payload_etapa2_dist.append({
                        "grupo": lista_categorias,
                        "valor_aporte": float(valor_ajustado) if valor_ajustado is not None else 0.0,
                        "moeda": moeda_atual,
                        "percentual_max_ativo": float(porc_max) if porc_max is not None else 20.0
                    })

    return payload_etapa2_dist

def widget_resultado_ativos(dist: list, qtd_select=None, key_estado_dinamico: str = "resultado_ativos") -> dict:
    """Exibe a tabela de sugestão de ativos por grupo usando seleção de linhas do st.dataframe.

    Retorna um dicionário {nome_grupo: df_com_selecao} mantendo a
    compatibilidade.
    """
    editores_retorno = {}

    key_alterado = f"alterado_{key_estado_dinamico}"
    if key_alterado not in st.session_state:
        st.session_state[key_alterado] = 0

    for item in dist:
        nome_grupo = " + ".join(item["grupo"])
        moeda = item["moeda"]

        key_widget = f"df_widget_{nome_grupo}_{key_estado_dinamico}"

        with st.expander( f"📂 {nome_grupo} | Alocado: {moeda} {item['valor_alocado']:.2f}", expanded=False):
            df = pd.DataFrame(item["ativos"])

            if df.empty:
                st.info("Nenhum ativo disponível neste grupo.")
                continue

            colunas_exibicao = {
                "ticker": "Ticker",
                "nome": "Nome",
                "preco_atual": "Preço Atual",
                "preco_min_12m": "Mín 12m",
                "posicao_range_12m": "% Range 12m",
                "preco_max_12m": "Máx 12m",
                "propor_aporte_12m": "% Aporte 12m",
                "aporte_12m": "Aporte 12m",
                "gap_original_financeiro": "Gap Orig.",
                "gap_ajustado_financeiro": "Gap Adj.",
                "redutor_preco": "Redutor Preço",
                "redutor_concentracao": "Redutor Conc.",
                "peso_original": "Peso Orig.",
                "peso_ajustado": "Peso Adj.",
                "sugestao_aporte": "Sugestão Aporte",
                "motivo_ajuste": "Status/Motivo",
            }

            colunas_presentes = [ col for col in colunas_exibicao.keys() if col in df.columns ]
            df_display = df[colunas_presentes].rename(columns=colunas_exibicao)

            formatacao_brasileira = {
                "Preço Atual": "{:,.2f}",
                "Mín 12m": "{:,.2f}",
                "Máx 12m": "{:,.2f}",
                "% Aporte 12m": "{:.2%}",
                "Aporte 12m": "{:,.2f}",
                "Gap Orig.": "{:,.2f}",
                "Gap Adj.": "{:,.2f}",
                "Redutor Preço": "{:,.2f}",
                "Redutor Conc.": "{:,.2f}",
                "Peso Orig.": "{:,.2f}",
                "Peso Adj.": "{:,.2f}",
                "Sugestão Aporte": "{:,.2f}",
            }

            configuracao_colunas = {
                "Ticker": st.column_config.TextColumn("Ticker"),
                "Preço Atual": st.column_config.NumberColumn(
                    f"Preço Atual ({moeda})"
                ),
                "% Range 12m": st.column_config.ProgressColumn(
                    "% Range 12m", format="%d%%", min_value=0, max_value=100
                ),
                "Sugestão Aporte": st.column_config.NumberColumn(
                    "Sugestão Aporte", format=f"{moeda} %.2f"
                ),
                "Status/Motivo": st.column_config.TextColumn("📌 Status/Motivo"),
            }

            colunas_visivel = [
                "Ticker",
                "Sugestão Aporte",
                "Preço Atual",
                "% Range 12m",
                "% Aporte 12m",
                "Status/Motivo",
                "Gap Orig.",
            ]
            colunas_visivel_validas = [ col for col in colunas_visivel if col in df_display.columns ]

            if qtd_select:
                if key_widget not in st.session_state:
                    st.session_state[key_widget] = { "selection": { "rows": list(range(min(qtd_select, len(df_display)))), "columns": [], "cells": [] } }
            # Renderização com st.dataframe e seleção de múltiplas linhas
            def houve_alteracao():
                st.session_state[key_alterado] += 1

            evento_selecao = st.dataframe( df_display.style.format(formatacao_brasileira, decimal=",", thousands="." )
                                          .map( lambda val: "background-color: rgba(0, 255, 0, 0.1)" if val > 0 else "", subset=["Sugestão Aporte"], ),
                                        width="stretch",
                                        hide_index=True,
                                        column_order=colunas_visivel_validas,
                                        column_config=configuracao_colunas,
                                        selection_mode="multi-row",
                                        key=key_widget,
                                        on_select=houve_alteracao)
            
            # Extrai os índices das linhas selecionadas
            linhas_selecionadas = evento_selecao.get("selection", {}).get( "rows", [] )

            # Retorna apenas o DataFrame filtrado com as linhas marcadas pelo usuário
            if linhas_selecionadas:
                editores_retorno[nome_grupo] = df_display.iloc[linhas_selecionadas].copy()
            else:
                editores_retorno[nome_grupo] = pd.DataFrame(columns=df_display.columns)

            c1, c2, c3 = st.columns(3)
            total_sugerido = (
                df["sugestao_aporte"].sum()
                if "sugestao_aporte" in df.columns
                else 0.0
            )
            c1.metric("Total Sugerido", f"{moeda} {formatar_numero_para_br_str(total_sugerido, 2)}")
            c2.metric("Ativos no Grupo", len(df))
            c3.metric("Moeda", moeda)

    return editores_retorno, st.session_state[key_alterado]

def widget_aporte_final(sugestao_grupos: list, data_editors: dict, key_estado_dinamico: str = "aporte_final") -> dict:   
    """
    Exibe a etapa de ajuste manual filtrando pelos checkboxes.
    Retorna um dicionário {grupo: df_ajustado} com os novos cálculos.
    """
    
    def widget_ajuste_manual_dinamico(df: pd.DataFrame, valor_total_aporte: float, moeda: str, key_estado_dinamico: str = "ajuste_manual",) -> pd.DataFrame:
        """
        Componente puro de ajuste manual.
        Recebe um DataFrame de ativos e retorna um novo DataFrame com as alocações ajustadas.
        """
        novos_dados = []
        soma_sugestoes = df['Sugestão Aporte'].sum() if 'Sugestão Aporte' in df.columns else 0.0

        st.markdown("""
            <div style="background-color: #f0f2f6; padding: 8px 12px; border-radius: 5px; margin-bottom: 8px; font-weight: bold; font-size: 14px; color: #31333F;">
                <div style="display: grid; grid-template-columns: 1fr 1.5fr 1fr 1fr 2fr 1.5fr; gap: 10px; align-items: center;">
                    <div>Ticker</div><div>Valor Aporte</div><div>Qtd. Aprox.</div><div>Preço Unit.</div><div>Alocação (%)</div><div>Sugestão</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        for _, row in df.iterrows():
            ticker = row['Ticker']
            sugestao = row.get('Sugestão Aporte', 0.0)
            preco_unitario = row.get('Preço Atual', 0.0)
            
            perc_sugerido = (sugestao / soma_sugestoes * 100) if soma_sugestoes > 0 else 0.0
  
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 1, 1, 2, 1.5])
                
                c1.markdown(f"**{ticker}**")

                # Chave única isolada no slider
                slider_key = f"perc_{ticker}_{key_estado_dinamico}"
                novo_percentual = c5.slider( f"% {ticker}", value=float(perc_sugerido), min_value=0.0, max_value=100.0, step=0.1, label_visibility="collapsed", key=slider_key )
                
                # 2. Cálculos baseados no valor do slider da renderização atual
                valor_financeiro = (novo_percentual / 100) * valor_total_aporte
                quantidade_ativos = int(valor_financeiro // preco_unitario) if preco_unitario > 0 else 0
                cor_aporte = "#24a148" if valor_financeiro > 0 else "#31333F"
                
                c2.markdown(f"<span style='color: {cor_aporte}; font-weight: bold;'>{moeda} {formatar_numero_para_br_str(valor_financeiro)}</span>", unsafe_allow_html=True)
                c3.markdown(f"<span style='color: #0068c9; font-weight: bold; font-size: 16px;'>{quantidade_ativos}</span>", unsafe_allow_html=True)
                c4.write(f"{moeda} {formatar_numero_para_br_str(preco_unitario)}")
                
                valor_sug_original = perc_sugerido * valor_total_aporte / 100
                c6.write(f"{moeda} {formatar_numero_para_br_str(valor_sug_original)} / {formatar_numero_para_br_str(perc_sugerido)}%")

            row_atualizada = row.to_dict()
            row_atualizada.update({
                'Ajuste %': novo_percentual,
                f'Novo Aporte {moeda}': valor_financeiro,
                'Quantidade': quantidade_ativos
            })
            novos_dados.append(row_atualizada)

        df_res = pd.DataFrame(novos_dados)
        
        # Métricas de resumo
        total_percentual_atual = df_res['Ajuste %'].sum()
        total_efetivo = df_res[f'Novo Aporte {moeda}'].sum()
        sobra = valor_total_aporte - total_efetivo

        m1, m2, m3 = st.columns(3)
        m1.metric(
            "Total Alocado", f"{formatar_numero_para_br_str(total_percentual_atual, 2)}%", 
            delta=f"{formatar_numero_para_br_str(total_percentual_atual - 100, 2)}%" if abs(total_percentual_atual - 100) > 0.01 else None,
            delta_color="inverse" if total_percentual_atual > 100.01 else "normal"
        )
        m2.metric("Total Efetivo", f"{moeda} {formatar_numero_para_br_str(total_efetivo, 2)}")
        m3.metric("Sobra em Caixa", f"{moeda} {formatar_numero_para_br_str(sobra, 2)}")

        if total_percentual_atual > 100.01:
            st.error(f"⚠️ Distribuição acima de 100%. Reduza {formatar_numero_para_br_str(total_percentual_atual - 100, 2)}%.")

        return df_res

    if not data_editors:
        return {}

    mapa_valores_grupos = {
        " + ".join(item["grupo"]): {
            "valor_alocado": float(item.get("valor_alocado", 0.0)),
            "moeda": item.get("moeda", "BRL")
        }
        for item in sugestao_grupos
    }

    st.header("🚀 Aporte por Ativo - Ajuste Manual")
    resultados_finais = {}

    for grupo, df_selecionado in data_editors.items():
        # Se o DataFrame já veio filtrado e não estiver vazio, segue o fluxo
        if df_selecionado is None or df_selecionado.empty:
            continue

        info_grupo = mapa_valores_grupos.get(grupo)

        if info_grupo:
            valor_total = info_grupo["valor_alocado"]
            moeda = info_grupo["moeda"]

            titulo_expander = f"📌 Ajuste Manual: {grupo} - Aporte: {moeda} {formatar_numero_para_br_str(valor_total, 2)}"
            with st.expander(titulo_expander, expanded=True):
                # Passa o df_selecionado diretamente
                df_ajustado = widget_ajuste_manual_dinamico( df_selecionado, valor_total, moeda, key_estado_dinamico=f"{key_estado_dinamico}_{grupo}",)
                resultados_finais[grupo] = df_ajustado
        else:
            st.warning(f"Valor de aporte não encontrado para o grupo: **{grupo}**")

    return resultados_finais