import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from plotly import graph_objects as go
from Pages.utils.request_api import ApiRequestError, executar_requisicao_aporte_etapa2, buscar_carteira_api, executar_requisicao_aporte_etapa1, obter_configuracoes_usuario_api
from Pages.utils.components import st_number_input_custom
from Pages.utils.ferramentas import formatar_numero_para_br_str
from Pages.utils.form_aporte import widget_resultado_grupo, widget_aporte_final, widget_config_ativos, widget_resultado_ativos, widget_config_categorias, widget_aporte_global
from Pages.utils.form_config import componente_config_redutores, get_redutores_padrao


# --- CACHE E AUXILIARES OPTIMIZADOS ---
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

# --- ESTRUTURA PRINCIPAL ---

if "page_aportes" not in st.session_state:
    cats = get_categorias_usuario()
    st.session_state["page_aportes"] = {
        "moedas_por_grupo": {},
        "categorias_disponiveis": cats,
        "lista_grupos": [{"cats": [cat], "min": "5,00", "max": "50,00"} for cat in cats],
        "ultimo_payload": None,
        "config_redutor": False,
    }

# --- INICIALIZAÇÃO CONTROLADA DO ESTADO ---

state = st.session_state["page_aportes"]

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
    col_t.title("🚿 Aporte Estratégico")

    with col_b.container(horizontal=True):
        if st.button("🫗 Aporte Rápido", width="stretch"):
            st.switch_page("Pages/Aporte/aporte_rapido.py")
        if st.button("🍎 Objetivos 🎯", width="stretch"):
            st.switch_page("Pages/Aporte/planejar_guiado.py")
        if st.button("⚙️ Configurações", width="stretch"):
            state["config_redutor"] = True
            st.rerun()

    with st.expander("📘 Instruções", expanded=False):
        st.markdown("""
        1. **Defina o valor total do aporte** e a moeda desejada.
        2. **Agrupe as categorias** de ativos conforme sua estratégia, definindo limites mínimos e máximos.
        3. **Distribuição sugerida** do aporte entre os grupos.
        4. **Ajuste os valores por grupo** e defina o percentual máximo por ativo.
        5. **Gere aporte por ativo** com base nas suas configurações.
        6. **Revise e selecione** quais ativos aportar via Checkbox.
        7. **Ajuste manual fino** altere individualmente a porcentagem alocada.
        """)

    with st.expander("📋 Formulário Grupo", expanded=True):
        v_aporte, moeda = widget_aporte_global()
        payload_resp = widget_config_categorias(v_aporte, moeda)

        st.write("")
        if st.button("🚀 Distribuir Aporte", type="primary", width='stretch'):
            try:
                resultado = executar_requisicao_aporte_etapa1(payload_resp)
            except ApiRequestError as exc:
                st.error(str(exc))
                st.warning("Não foi possível calcular o aporte.")
                resultado = None

            if resultado:
                keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("val_etapa2_", "sel_moeda_"))]
                for key in keys_to_clear:
                    del st.session_state[key]

                if "moedas_por_grupo" in state:
                    state["moedas_por_grupo"] = {}

                state["resultado_grupo_aporte"] = resultado.get("distribuicao", [])
                st.success("Cálculo realizado com sucesso!")

    if "resultado_grupo_aporte" in state:
        with st.expander("📊 Resultado da Distribuição Sugerida", expanded=True):
            dist = state["resultado_grupo_aporte"]

            if dist:
                with st.expander("📈 Análise da Distribuição Sugerida", expanded=False):
                    widget_resultado_grupo(dist)

                payload_etapa2_dist = widget_config_ativos(dist, moeda_padrao=moeda)

                st.write("")
                if st.button("🛒 Calcular Aporte por Ativo", width='stretch', type="primary"):
                    payload_final = {"distribuicao": payload_etapa2_dist}
                    try:
                        resultado_ativos = executar_requisicao_aporte_etapa2(payload_final)
                    except ApiRequestError as exc:
                        st.error(str(exc))
                        resultado_ativos = None
                    
                    if isinstance(resultado_ativos, dict) and "sugestao_grupos" in resultado_ativos:
                        state["resultado_ativos_aporte"] = resultado_ativos

    if state.get("resultado_ativos_aporte"):
        data = state["resultado_ativos_aporte"]

        versao_calculo = st.session_state.get("versao_calculo", 1)
        key_dinamica_pagina = f"page_aportes_v{versao_calculo}"

        with st.expander("📈 Detalhamento dos Ativos Sugeridos para Aporte", expanded=True):
            data_editor, alterado = widget_resultado_ativos(data["sugestao_grupos"], qtd_select=None, key_estado_dinamico=key_dinamica_pagina)
        if data_editor:
            widget_aporte_final(data["sugestao_grupos"], data_editor, key_estado_dinamico=f"final_{key_dinamica_pagina}_{alterado}")