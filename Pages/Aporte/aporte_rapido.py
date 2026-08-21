import pandas as pd
import streamlit as st
from Pages.utils.components import st_number_input_custom
from Pages.utils.form_aporte import widget_aporte_final, widget_resultado_ativos
from Pages.utils.form_config import componente_config_redutores, get_redutores_padrao
from Pages.utils.request_api import (ApiRequestError,
                                     buscar_carteira_api, 
                                     obter_configuracoes_usuario_api, 
                                     executar_requisicao_aporte_etapa2, )



def get_categorias_usuario():
    if "dados_carteira_cache" not in st.session_state:
        try:
            st.session_state["dados_carteira_cache"] = buscar_carteira_api()
        except ApiRequestError as exc:
            st.session_state["dados_carteira_cache"] = []
            st.warning("Não foi possível carregar a carteira.")

    dados = st.session_state.get("dados_carteira_cache", [])

    if not dados:
        return []

    categorias = {
                item.get("categoria")
                for item in dados
                if isinstance(item, dict)
                and item.get("categoria")
                and item.get("categoria") != "SUBS"
            }

    return sorted(categorias)

def carregar_configuracoes_iniciais(state):
    """Busca as configurações via GET na API e salva no Session State."""
    if "configuracoes" not in st.session_state:
        try:
            st.session_state["configuracoes"] = obter_configuracoes_usuario_api()
        except ApiRequestError as exc:
            st.session_state["configuracoes"] = {}
            st.warning("Não foi possível carregar as configurações.")
        
    config_api = st.session_state['configuracoes']

    if config_api and "redutores_aporte" in config_api:
        redutores = config_api["redutores_aporte"]
        state["faixas_preco"] = redutores.get("faixas_preco", [])
        state["config_concentracao"] = redutores.get("config_concentracao", {})
    else:
        redutores_padrao = get_redutores_padrao()        
        # Fallback de segurança caso a API falhe ou venha vazia
        state["faixas_preco"] = redutores_padrao["faixas_preco"]
        state["config_concentracao"] = redutores_padrao["config_concentracao"]

# --- INICIALIZAÇÃO CONTROLADA DO ESTADO ---
if "page_aporte_rapido" not in st.session_state:
    st.session_state["page_aporte_rapido"] = {
        "config_redutor": False,
    }

state = st.session_state["page_aporte_rapido"]

# Carrega as configurações da API se ainda não existirem no estado
if "faixas_preco" not in state or "config_concentracao" not in state:
    carregar_configuracoes_iniciais(state)


# --- CONTROLE DE NAVEGAÇÃO DE CONFIGURAÇÃO ---
if state["config_redutor"]:
    col_t, _, col_b = st.columns([2, 0.1, 1], vertical_alignment="center")
    col_t.title("⚙️ Configurações dos Redutores de Aporte")
    if col_b.container(horizontal=True, horizontal_alignment="right").button(" Sair", width="content"):
        state["config_redutor"] = False
        st.rerun()

    componente_config_redutores()

else:
    # Cabeçalho Principal
    col_t, _, col_b = st.columns([1, 0.1, 1])
    col_t.title("🫗 Aporte Rápido por Grupo")
    col_t.caption( "Aporte direto por grupo com parametrização dinâmica de redutores." )

    with col_b.container(horizontal=True):
        if st.button("Aporte Macro", width="stretch"):
            st.switch_page("Pages/Aporte/aporte_grupo.py")
        if st.button("Objetivos", width="stretch"):
            st.switch_page("Pages/Aporte/planejar_guiado.py")
        if st.button("⚙️ Configurações", width="stretch"):
            state["config_redutor"] = True
            st.rerun()

    # --- FORMULÁRIO DE SELEÇÃO E SUBMISSÃO ---
    categorias_disponiveis = get_categorias_usuario()

    with st.expander("🫳🫘 Configuração do Aporte", expanded=True).container(border=True):
        c_cat, c_val, c_moeda, c_max, c_qtd = st.columns( [2.5, 1.5, 1, 1.2, 1.2] )

        cats_selecionadas = c_cat.multiselect( "Categorias do Grupo", options=categorias_disponiveis, default=categorias_disponiveis )

        # Retornado ao componente customizado original
        with c_val:
            valor_aporte = st_number_input_custom("Valor do Aporte", value="5000,00",key="rapido_valor" )

        moeda = c_moeda.radio( "Moeda", ["BRL", "USD"], horizontal=True, key="rapido_moeda" )

        perc_max_ativo = c_max.slider( "% Máx/Ativo", value=20, max_value=100, min_value=0, key="rapido_perc_max", )

        qtd_ativos = c_qtd.number_input("Qtd de ativos", value=2,step=1, min_value=1, key="rapido_qtd_ativos" )

        if st.button( "🌱 Calcular Aporte por Ativo", type="primary", width="stretch", ):
            if not cats_selecionadas:
                st.error("Selecione pelo menos uma categoria para o grupo.")
            else:
                payload_etapa2 = {
                    "distribuicao": [
                        {
                            "grupo": cats_selecionadas,
                            "valor_aporte": float(valor_aporte),
                            "moeda": moeda,
                            "percentual_max_ativo": float(perc_max_ativo),
                            "qtd_ativos": int(qtd_ativos),
                        }
                    ],
                    "faixas_preco": state.get("faixas_preco", []),
                    "config_concentracao": state.get("config_concentracao", {}),
                }

                try:
                    resultado_ativos = executar_requisicao_aporte_etapa2(payload_etapa2)
                except ApiRequestError as exc:
                    st.error(str(exc))
                    resultado_ativos = None

                if isinstance(resultado_ativos, dict) and "sugestao_grupos" in resultado_ativos:
                    state["sugestao_grupos"] = resultado_ativos["sugestao_grupos"]
                    st.success("Cálculo realizado com sucesso!")

    layout_apostes = st.empty()
    # --- RENDERIZAÇÃO DOS RESULTADOS ---
    if "sugestao_grupos" in state:
        sugestoes = state.get("sugestao_grupos", [])

        versao_calculo = st.session_state.get("versao_calculo", 1)
        key_dinamica_pagina = f"page_aportes_rapido_v{versao_calculo}"

        editores_atualizados, alterado = widget_resultado_ativos(sugestoes, qtd_ativos, key_estado_dinamico=key_dinamica_pagina)
        if editores_atualizados:
            with layout_apostes:
                widget_aporte_final(sugestoes, editores_atualizados, key_estado_dinamico=f"final_{key_dinamica_pagina}_{alterado}")
