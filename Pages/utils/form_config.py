import streamlit as st
from typing import Optional, Callable
from Pages.utils.components import st_number_input_custom
from Pages.utils.request_api import ( obter_configuracoes_usuario_api,
                                      executar_requisicao_atualizar_configuracoes,
                                      ApiRequestError )


def get_redutores_padrao() -> dict:
    """Retorna a estrutura padrão completa dos redutores de aporte."""
    return {
        "faixas_preco": [
            {"min_range": 0.0, "max_range": 20.0, "fator": 1.05},
            {"min_range": 60.0, "max_range": 70.0, "fator": 0.98},
            {"min_range": 70.0, "max_range": 80.0, "fator": 0.95},
            {"min_range": 80.0, "max_range": 90.0, "fator": 0.90},
            {"min_range": 90.0, "max_range": 95.0, "fator": 0.85},
            {"min_range": 95.0, "max_range": 100.0, "fator": 0.80},
        ],
        "config_concentracao": {
            "percentual_bonus_sem_aporte": 0.01,
            "bonus_sem_aporte": 1.05,
            "multiplicador_alerta": 1.50,
            "fator_freio_leve": 0.80,
            "multiplicador_trava": 2.00,
            "fator_freio_medio": 0.50,
        },
    }


# ==============================================================================
# 🏢 LAYOUT DE EDIÇÃO DOS REDUTORES (FUNÇÃO PURA DE RENDERIZAÇÃO)
# ==============================================================================
def renderizar_layout_edit_redutores( dados_redutores: dict, on_sucesso: Optional[Callable] = None, user_id: Optional[int] = None,
    key_estado_dinamico: str = "redutores_default", ):
    """
    Renderiza os campos de formulário e trata as ações de salvar/resetar.
    """
    faixas = dados_redutores.get("faixas_preco", [])
    cfg_conc = dados_redutores.get("config_concentracao", {})

    st.caption("Ajuste os parâmetros de preço e concentração para os cálculos de aporte.")

    # -------------------------------------------------------------
    # 📉 1. REDUTOR DE PREÇO (% RANGE 12M)
    # -------------------------------------------------------------
    with st.expander("REDUTOR DE PREÇO (% RANGE 12M)"):
        st.markdown("#### 📉 Redutor de Preço (% Range 12m)")

        faixas_atualizadas = []
        indices_para_remover = []

        for idx, faixa in enumerate(faixas):
            with st.container(border=True):
                col_range, col_fator, col_del = st.columns([3, 1.5, 0.5], vertical_alignment="center")

                with col_range:
                    range_val = st.slider( f"Faixa {idx + 1} (% Range)", min_value=0.0, max_value=100.0,
                        value=(float(faixa["min_range"]), float(faixa["max_range"])),
                        step=1.0, format="%.0f%%", key=f"{key_estado_dinamico}_range_{idx}", )

                with col_fator:
                    fator_val = st_number_input_custom( "Fator Redutor", value=float(faixa["fator"]), key=f"{key_estado_dinamico}_fator_{idx}", )

                with col_del:
                    st.write("")
                    if st.button("🗑️", key=f"{key_estado_dinamico}_del_{idx}", help="Excluir faixa"):
                        indices_para_remover.append(idx)

                faixas_atualizadas.append(
                    {
                        "min_range": float(range_val[0]),
                        "max_range": float(range_val[1]),
                        "fator": float(fator_val),
                    }
                )

        # Processa exclusão de faixas
        if indices_para_remover:
            for i in reversed(indices_para_remover):
                faixas_atualizadas.pop(i)
            dados_redutores["faixas_preco"] = faixas_atualizadas
            st.session_state["componente_redutores"]["form_key_count"] += 1
            st.rerun()

        # Adicionar nova faixa
        if st.button("➕ Adicionar Faixa de Preço", key=f"{key_estado_dinamico}_add_faixa"):
            faixas_atualizadas.append({"min_range": 0.0, "max_range": 100.0, "fator": 1.0})
            dados_redutores["faixas_preco"] = faixas_atualizadas
            st.session_state["componente_redutores"]["form_key_count"] += 1
            st.rerun()

        st.markdown("---")

    # -------------------------------------------------------------
    # 🛡️ 2. REDUTOR DE CONCENTRAÇÃO
    # -------------------------------------------------------------
    with st.expander("REDUTOR DE CONCENTRAÇÃO"):
        st.markdown("#### 🛡️ Configuração do Redutor de Concentração")

        val_perc_bonus = float(cfg_conc.get("percentual_bonus_sem_aporte", 0.01))
        val_perc_bonus_input = val_perc_bonus * 100.0 if val_perc_bonus <= 1.0 else val_perc_bonus

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True):
                perc_bonus = st_number_input_custom(
                    "Bônus Sem Aporte (%) 12m",
                    value=val_perc_bonus_input,
                    key=f"{key_estado_dinamico}_perc_bonus",
                    help="Até este % de participação em 12m, ganha bônus por falta de aportes.",
                )
                bonus = st_number_input_custom(
                    "Fator Bônus Sem Aporte",
                    value=float(cfg_conc.get("bonus_sem_aporte", 1.05)),
                    key=f"{key_estado_dinamico}_bonus",
                )

        with col2:
            with st.container(border=True):
                mult_alerta = st_number_input_custom(
                    "Multiplicador Alerta",
                    value=float(cfg_conc.get("multiplicador_alerta", 1.50)),
                    key=f"{key_estado_dinamico}_mult_alerta",
                )
                freio_leve = st_number_input_custom(
                    "Fator Freio Leve",
                    value=float(cfg_conc.get("fator_freio_leve", 0.80)),
                    key=f"{key_estado_dinamico}_freio_leve",
                )

        with col3:
            with st.container(border=True):
                mult_trava = st_number_input_custom(
                    "Multiplicador Trava Total",
                    value=float(cfg_conc.get("multiplicador_trava", 2.00)),
                    key=f"{key_estado_dinamico}_mult_trava",
                )
                freio_medio = st_number_input_custom(
                    "Fator Freio Médio",
                    value=float(cfg_conc.get("fator_freio_medio", 0.50)),
                    key=f"{key_estado_dinamico}_freio_medio",
                )

        st.write("")

    # -------------------------------------------------------------
    # 💾 3. AÇÕES (RESETAR E SALVAR)
    # -------------------------------------------------------------
    col_reset, col_salvar = st.columns([1, 2])

    with col_reset:
        if st.button("🔄 Reset to Default", key=f"{key_estado_dinamico}_btn_reset", width='stretch'):
            st.session_state["componente_redutores"]["dados"] = get_redutores_padrao()
            st.session_state["componente_redutores"]["form_key_count"] += 1
            st.toast("Restaurado para os valores padrões!", icon="ℹ️")
            st.rerun()

    with col_salvar:
        if st.button("💾 Salvar Configurações", type="primary", key=f"{key_estado_dinamico}_btn_salvar", width='stretch'):
            concentracao_payload = {
                "percentual_bonus_sem_aporte": float(perc_bonus) / 100.0,
                "bonus_sem_aporte": float(bonus),
                "multiplicador_alerta": float(mult_alerta),
                "fator_freio_leve": float(freio_leve),
                "multiplicador_trava": float(mult_trava),
                "fator_freio_medio": float(freio_medio),
            }

            payload_final = {
                "redutores_aporte": {
                    "faixas_preco": faixas_atualizadas,
                    "config_concentracao": concentracao_payload,
                }
            }

            try:
                resposta = executar_requisicao_atualizar_configuracoes(
                    payload=payload_final,
                    user_id=user_id,
                )

                if resposta and resposta.get("status") == "sucesso":
                    if "configuracoes" in st.session_state:
                        st.session_state["configuracoes"]["redutores_aporte"] = payload_final["redutores_aporte"]

                    st.toast("✅ Configurações dos redutores salvas com sucesso!", icon="✅")

                    if on_sucesso:
                        on_sucesso()
                    else:
                        st.rerun()
                else:
                    st.warning("⚠️ Resposta inesperada do servidor. Verifique as configurações.")

            except ApiRequestError as err:
                st.error(f"❌ Erro ao salvar: {err.message}", icon="🚫")


# ==============================================================================
# 🎯 COMPONENTE REUTILIZÁVEL (FUNÇÃO DE INTERFACE)
# ==============================================================================
def componente_config_redutores(user_id: Optional[int] = None, on_sucesso: Optional[Callable] = None):
    """
    Componente reutilizável para renderização direta em qualquer página ou container.
    """
    # 1. INICIALIZAÇÃO DO ESTADO DA SESSÃO
    if "componente_redutores" not in st.session_state:
        st.session_state["componente_redutores"] = {}

    state = st.session_state["componente_redutores"]
    state.setdefault("dados", None)
    state.setdefault("form_key_count", 0)

    # 2. CARREGAMENTO EM CACHE
    if state["dados"] is None:
        try:
            config_user = obter_configuracoes_usuario_api(user_id=user_id) or {}
            redutores_api = config_user.get("redutores_aporte")
            if not redutores_api:
                redutores_api = get_redutores_padrao()
            state["dados"] = redutores_api
        except ApiRequestError as err:
            # Se falhar ao carregar config, usa padrão e exibe erro
            st.warning(f"⚠️ Não foi possível carregar suas configurações: {err.message}")
            state["dados"] = get_redutores_padrao()

    key_from = state["form_key_count"]

    # 3. RENDERIZAÇÃO DIRETA NO LAYOUT DA PÁGINA
    renderizar_layout_edit_redutores( dados_redutores=state["dados"], on_sucesso=on_sucesso, user_id=user_id, key_estado_dinamico=f"comp_redutores_{key_from}", )