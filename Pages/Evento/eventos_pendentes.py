import json
import pandas as pd
import streamlit as st

from Pages.utils.components import componente_buscador_ativo, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_ativo_visual
from Pages.utils.form_edit import renderizar_layout_edit_evento

from Pages.utils.request_api import (
    listar_eventos_pendentes_api,
    atualizar_status_evento_pendente_api,
    deletar_eventos_pendentes_em_lote_api,
    executar_requisicao_pesquisar_eventos_corporativos,
    executar_requisicao_criar_evento_corporativo,
)

# ====================================================================
# Configurações e Mapeamentos
# ====================================================================
PAGE_KEY = "page_eventos_pendentes"


CONFIG_COLUNAS_PENDENTES = {
    "id": {"titulo": "ID", "tipo": "hide"},
    "status": {"titulo": "📌 Status", "tipo": "text"},
    "fk_ativo": {"titulo": "🏷️ Ativo Base", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("fk_ativo") or r.get("fk_ativo_base"))},
    "ativo_gerado": {"titulo": "🏷️ Ativo Gerado", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("ativo_gerado") or r.get("fk_ativo_gerado"))},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "data_aprov": {"titulo": "📅 Aprov.", "tipo": "date"},
    "data_com": {"titulo": "📅 Data COM", "tipo": "date"},
    "data_pag": {"titulo": "📅 Data PAG", "tipo": "date"},
    "proporcao": {"titulo": "📊 Proporção", "tipo": "decimal"},
    "operacao": {"titulo": "🧾 Operação / Instruções", "tipo": "text"},
}


def resumo_instrucoes(row):
    """Retorna uma string curta/legível a partir do campo 'instrucoes' (JSON armazenado em texto)."""
    instr = row.get("instrucoes")
    if not instr:
        return ""
    try:
        # Se já é dict/list
        if isinstance(instr, (dict, list)):
            texto = json.dumps(instr, ensure_ascii=False)
        else:
            # tenta desserializar se for string JSON
            texto = instr
            # se for JSON válido, pretty-print reduzido
            try:
                obj = json.loads(instr)
                texto = json.dumps(obj, ensure_ascii=False)
            except Exception:
                # mantém string tal qual
                texto = instr
        
        return texto
    except Exception:
        return str(instr)[:120]


CONFIG_COLUNAS_EVENTOS = {
    "id": {"titulo": "ID", "tipo": "hide"},
    "fk_ativo_base": {"titulo": "🏷️ Ativo Base", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("fk_ativo_base"))},
    "fk_ativo_gerado": {"titulo": "🏷️ Ativo Gerado", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("fk_ativo_gerado"))},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "data_aprov": {"titulo": "📅 Aprov.", "tipo": "date"},
    "data_com": {"titulo": "📅 Data COM", "tipo": "date"},
    "data_pag": {"titulo": "📅 Data PAG", "tipo": "date"},
    "instrucoes": {"titulo": "🧾 Instruções", "tipo": "text", "funcao_map": resumo_instrucoes},
}

# ====================================================================
# Gestão de Estado
# ====================================================================
def inicializar_estado():
    if PAGE_KEY not in st.session_state:
        st.session_state[PAGE_KEY] = {}

    state = st.session_state[PAGE_KEY]
    state.setdefault("item_selecionado", None)
    state.setdefault("modo_tela", "listagem")  # listagem | simular
    state.setdefault("dados", [])
    state.setdefault("filtro_busca", "Selecionar Ativo")
    state.setdefault("carregar_tudo", False)
    state.setdefault("ultimo_filtro_carregado", None)
    state.setdefault("ultimo_carregar_tudo", False)
    state.setdefault("reset_buscador_count", 0)
    state.setdefault("form_key_count", 0)
    state.setdefault("eventos_existentes", [])

    return state


def aplicar_estilo_tabela(dataframe_da_tela: pd.DataFrame, dados_originais) -> pd.DataFrame:
    estilo = pd.DataFrame("", index=dataframe_da_tela.index, columns=dataframe_da_tela.columns)
    for idx in dataframe_da_tela.index:
        if idx < len(dados_originais):
            registro = dados_originais[idx]
            status = registro.get("status")
            if status == "PENDENTE":
                estilo.loc[idx] = "color: #856404; background-color: #fff3cd; font-style: italic;"
            elif status == "EM ANDAMENTO":
                estilo.loc[idx] = "color: #0c5460; background-color: #d1ecf1;"
            elif status == "IMPLEMENTADO":
                estilo.loc[idx] = "color: #155724; background-color: #d4edda;"
    return estilo


def sincronizar_cache_dados(state):
    filtro_atual = state.get("filtro_busca")
    carregar_tudo = state.get("carregar_tudo", False)

    if filtro_atual == "Selecionar Ativo" and not carregar_tudo:
        state["dados"] = []
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        return

    try:
        if carregar_tudo and not state.get("ultimo_carregar_tudo"):
            with st.spinner("Carregando eventos pendentes..."):
                state["dados"] = listar_eventos_pendentes_api(ativo_id=None)
                state["ultimo_carregar_tudo"] = True
                state["ultimo_filtro_carregado"] = None

        elif filtro_atual != "Selecionar Ativo":
            precisa = filtro_atual != state.get("ultimo_filtro_carregado") or state.get("ultimo_carregar_tudo")
            if precisa:
                with st.spinner(f"Buscando eventos pendentes para {filtro_atual}..."):
                    state["dados"] = listar_eventos_pendentes_api(ativo_id=filtro_atual)
                    state["ultimo_filtro_carregado"] = filtro_atual
                    state["ultimo_carregar_tudo"] = False

    except Exception as exc:
        state["dados"] = []
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        st.error(f"Erro ao carregar dados do servidor: {exc}")


def preparar_evento_para_formulario(registro: dict) -> dict:
    evento = dict(registro)
    evento["fk_ativo_base"] = evento.get("fk_ativo_base") or evento.get("fk_ativo")
    evento["fk_ativo_gerado"] = evento.get("fk_ativo_gerado") or evento.get("ativo_gerado")
    evento.setdefault("instrucoes", evento.get("operacao") or [])
    return evento


# ====================================================================
# Callbacks de Ações
# ====================================================================
def acao_alterar_status(registro: dict, novo_status: str):
    evento_id = registro.get("id")
    if not evento_id:
        st.warning("Registro sem ID válido.")
        return

    try:
        atualizar_status_evento_pendente_api(int(evento_id), status=novo_status)
        st.session_state["toast_pendente"] = {"mensagem": f"Status alterado para '{novo_status}'.", "icone": "✅"}
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
    except Exception as exc:
        st.session_state["erro_pendente"] = f"Erro ao atualizar status: {exc}"


def acao_simular(registro: dict):
    state = st.session_state[PAGE_KEY]
    evento_id = registro.get("id")
    if not evento_id:
        st.warning("ID inválido para simulação.")
        return

    try:
        atualizar_status_evento_pendente_api(int(evento_id), status="EM ANDAMENTO")
        st.session_state["toast_pendente"] = {"mensagem": f"Status alterado para EM ANDAMENTO.", "icone": "✅"}
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        state["item_selecionado"] = registro
        state["modo_tela"] = "simular"
        state["form_key_count"] += 1
    except Exception as exc:
        st.session_state["erro_pendente"] = f"Erro ao iniciar simulação: {exc}"


def acao_deletar(registros: list):
    state = st.session_state[PAGE_KEY]
    ids_validos = [r.get("id") for r in registros if r.get("id") is not None]
    if not ids_validos:
        st.warning("Nenhum registro selecionado para exclusão.")
        return

    try:
        res = deletar_eventos_pendentes_em_lote_api(ids_validos)
        total_excluidos = res.get("total_excluidos", len(ids_validos))
        st.session_state["toast_pendente"] = {"mensagem": f"{total_excluidos} evento(s) pendente(s) excluído(s).", "icone": "✅"}
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
    except Exception as e:
        st.session_state["erro_pendente"] = f"Erro ao excluir evento(s): {e}"


def aplicar_filtros_locais(dados):
    c1, c2 = st.columns(2)
    with c1:
        status_sel = st.pills("Filtrar por Status", options=["PENDENTE", "EM ANDAMENTO", "IMPLEMENTADO"], selection_mode="multi")
    with c2:
        tipos_disponiveis = sorted({e.get("tipo", "") for e in dados if e.get("tipo")})
        tipos_sel = st.multiselect("Filtrar por Tipo", options=tipos_disponiveis)

    dados_filtrados = dados
    if status_sel:
        dados_filtrados = [e for e in dados_filtrados if e.get("status") in status_sel]
    if tipos_sel:
        dados_filtrados = [e for e in dados_filtrados if e.get("tipo") in tipos_sel]

    return dados_filtrados


# ====================================================================
# Renderização do Layout
# ====================================================================
state = inicializar_estado()

if state["modo_tela"] == "listagem":
    st.title("⏳ Eventos Pendentes de Implementação")
    st.caption("Acompanhe, simule e altere o status dos eventos pendentes do robô/sistema.")

    c1, c2, c3 = st.columns([1.5, 2.5, 1.5], vertical_alignment="bottom")
    with c1:
        if st.button("👁️ Carregar Tudo", width="stretch"):
            state["carregar_tudo"] = True
            state["filtro_busca"] = "Selecionar Ativo"
            state["reset_buscador_count"] += 1
            st.rerun()
    with c2:
        sufixo = f"evt_pend_{state['reset_buscador_count']}"
        componente_buscador_ativo(state, "filtro_busca", sufixo_key=sufixo)
    with c3:
        if state["filtro_busca"] != "Selecionar Ativo" or state["carregar_tudo"]:
            if st.button("🧹 Limpar Filtros", width="stretch"):
                state["filtro_busca"] = "Selecionar Ativo"
                state["reset_buscador_count"] += 1
                state["carregar_tudo"] = False
                state["dados"] = []
                state["ultimo_filtro_carregado"] = None
                state["ultimo_carregar_tudo"] = False
                st.rerun()

    sincronizar_cache_dados(state)
    dados_para_exibir = state.get("dados", [])

    if state["filtro_busca"] == "Selecionar Ativo" and not state["carregar_tudo"]:
        st.info("💡 Selecione um filtro ou clique em Carregar Tudo.")
    elif not dados_para_exibir:
        st.warning("Nenhum evento pendente encontrado.")
    else:
        st.caption(f"Exibindo {len(dados_para_exibir)} registro(s):")
        dados_filtrados = aplicar_filtros_locais(dados_para_exibir)

        acoes_customizadas = [
            {"help": "🧪 Simular", "icone": "🧪", "callback": acao_simular, "somente_unico": True},
            {"help": "🎯 Implementado", "icone": "🎯", "callback": lambda registro: acao_alterar_status(registro, "IMPLEMENTADO"), "somente_unico": True},
            {"help": "♻️ Em Andamento", "icone": "♻️", "callback": lambda registro: acao_alterar_status(registro, "EM ANDAMENTO"), "somente_unico": True},
            {"help": "⏳ Pendente", "icone": "⏳", "callback": lambda registro: acao_alterar_status(registro, "PENDENTE"), "somente_unico": True},
        ]

        exibir_tabela_generica(
            dados=dados_filtrados,
            config_colunas=CONFIG_COLUNAS_PENDENTES,
            colunas_resumidas=None,
            callback_deletar=acao_deletar,
            callback_estilo=aplicar_estilo_tabela,
            botoes_acao=acoes_customizadas,
            chave_tabela="tabela_eventos_pendentes",            
            suporta_moeda=False,
        )

        linha_ref = st.session_state.get(f"registros_selecionados_chave_tabela_tabela_eventos_pendentes", None)
        if linha_ref:
            ativo_ref = linha_ref[0].get("fk_ativo")
            st.divider()
            st.subheader(f"Eventos Corporativos Existentes ({ativo_ref})")
            try:
                eventos_existentes = executar_requisicao_pesquisar_eventos_corporativos(ativo_ref)
                if eventos_existentes:
                    exibir_tabela_generica(
                                            dados=eventos_existentes,
                                            config_colunas=CONFIG_COLUNAS_EVENTOS,
                                            colunas_resumidas=None,
                                            callback_edit=None,
                                            callback_deletar=None,
                                            callback_estilo=None,
                                            chave_tabela=f"eventos_cadastrados",
                                            suporta_moeda=False                     
                                        )
                else:
                    st.info(f"Nenhum evento cadastrado oficialmente para {ativo_ref}.")
            except Exception as e:
                st.error(f"Erro ao buscar histórico do ativo: {e}")

elif state["modo_tela"] == "simular":
    if st.button("⬅️ Voltar para Eventos Pendentes", key="btn_voltar_simulacao"):
        state["modo_tela"] = "listagem"
        st.rerun()

    st.title("🧪 Simular Evento Pendente")
    st.caption("Revise os parâmetros do evento antes de confirmar sua implementação.")

    def finalizar_simulacao():
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        state["modo_tela"] = "listagem"
        st.rerun()

    evento_pendente = preparar_evento_para_formulario(state.get("item_selecionado") or {})
    key_form = f"form_pendente_{state.get('form_key_count', 0)}"

    renderizar_layout_edit_evento(
        registro_selecionado={"dados_origem": evento_pendente},
        key_estado_dinamico=key_form,
        origin_config={
            "callback_request_api": lambda payload: executar_requisicao_criar_evento_corporativo(payload),
            "label_btn_gravar": "✅ Confirmar e Cadastrar Evento",
            "modo_insert": "MANUAL INSERT",
        },
        on_sucesso=finalizar_simulacao,
    )