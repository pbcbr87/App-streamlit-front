import pandas as pd
import streamlit as st
from typing import Any, Dict, List, Optional
from Pages.utils.components import componente_buscador_ativo, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_ativo_visual
from Pages.utils.form_edit import renderizar_layout_edit_evento
from Pages.utils.modals import modal_confirmar_delecao_eventos
from Pages.utils.request_api import listar_eventos_api, executar_requisicao_alterar_status_evento, executar_requisicao_insert_evento, executar_requisicao_editar_evento


# ==============================================================================    
# 🎯 1. INICIALIZAÇÃO DOS ESTADOS DA SESSÃO (SESSION STATE)
# ==============================================================================
PAGE_KEY = "page_eventos"
if PAGE_KEY not in st.session_state:
    st.session_state[PAGE_KEY] = {}

state: Dict[str, Any] = st.session_state[PAGE_KEY]

# Inicialização padronizada do dicionário de estado da tela
state.setdefault("ativo_original", "Selecionar Ativo")
state.setdefault("reset_buscador_count", 0)
state.setdefault("carregar_tudo", False)
state.setdefault("evento_selecionado", None)
state.setdefault("modo_tela", "listagem")
state.setdefault("dados", [])

# Controle de Cache de requisições
state.setdefault("ultimo_ativo_carregado", None)
state.setdefault("ultimo_carregar_tudo", False)

# ==============================================================================
# 2. MAPPERS E FORMATAÇÕES DE COLUNA
# ==============================================================================
def formatar_status_aplicado(row: Dict[str, Any]) -> str:
    """ Retorna badge indicando se o evento foi integrado à carteira."""
    return "🙋‍♂️ Sim" if row.get("foi_aplicado") else "🛌 Não"


def formatar_status_aceito(row: Dict[str, Any]) -> str:
    """ Retorna badge indicando se o evento está ativado ou desativado."""
    return "✔️ Ativo" if row.get("aceito") else "⚪ Inativo"


def colorir_linhas_eventos(dataframe_da_tela: pd.DataFrame, dados_originais: List[Dict[str, Any]]) -> pd.DataFrame:
    """ Destaca visualmente eventos inativos ou não integrados."""
    estilo = pd.DataFrame("", index=dataframe_da_tela.index, columns=dataframe_da_tela.columns)
    
    for idx, _ in dataframe_da_tela.iterrows():
        registro = dados_originais[idx]
        if not registro.get("aceito"):
            estilo.loc[idx] = "color: #856404; background-color: #fff3cd; font-style: italic;"
            
    return estilo


#  Configuração declarativa de colunas alinhada ao componente genérico
CONFIG_EVENTOS: Dict[str, Dict[str, Any]] = {
    "id": {"titulo": "ID", "tipo": "hide"},
    "aceito": {"titulo": "⚙️ Status", "tipo": "text", "funcao_map": formatar_status_aceito},
    "foi_aplicado": {"titulo": "🔄 Integrado", "tipo": "text", "funcao_map": formatar_status_aplicado},
    "modo_insert": {"titulo": "📥 Modo", "tipo": "text"},
    "tipo": {"titulo": "⚡ Tipo Evento", "tipo": "text"},
    "fk_ativo_base": {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo_base"))},
    "fk_ativo_gerado": {"titulo": "🎯 Ativo Gerado", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo_gerado"))},
    "data_aprov": {"titulo": "📅 Aprovado", "tipo": "date"},
    "data_com": {"titulo": "📅 Data Com", "tipo": "date"},
    "data_pag": {"titulo": "📅 Data Pag", "tipo": "date"},
    "proporcao": {"titulo": "📐 Proporção", "tipo": "number", "precisao": 6},
    "valor_base": {"titulo": "💰 Valor Base", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "data_insert": {"titulo": "🕒 Cadastrado em", "tipo": "date"}
}

COLUNAS_RESUMIDAS: List[str] = [
    "aceito", "foi_aplicado", "tipo", "fk_ativo_base", "fk_ativo_gerado", 
    "data_com", "data_pag", "proporcao", "valor_base"
]


# ==============================================================================
# ⚙️ 3. CALLBACKS E GERENCIADOR DE CACHE
# ==============================================================================
def ir_para_listagem_limpo() -> None:
    """ Limpa estado de cache ao salvar para forçar atualização."""
    print("🔄 Retornando para listagem e limpando cache de eventos...")
    if 'page_movimentacao' in st.session_state:
        st.session_state['page_movimentacao']["ultimo_ativo_carregado"] = None
        st.session_state['page_movimentacao']["ultimo_carregar_tudo"] = False
        st.session_state['page_movimentacao']["modo_tela"] = "listagem"
        st.session_state['page_movimentacao']["ordens_pendentes"] = None
    state["ultimo_ativo_carregado"] = None
    state["ultimo_carregar_tudo"] = False
    state["modo_tela"] = "listagem"
    st.rerun()

def acao_deletar(registros: List[Dict[str, Any]]) -> None:
    """ Callback disparado pela tabela para iniciar o fluxo de exclusão/inativação de eventos."""
    state = st.session_state.get(PAGE_KEY, {})
    
    # Extração e filtragem dos IDs válidos
    ids_para_enviar = [reg.get("id") for reg in registros if reg.get("id") is not None]
    
    if not ids_para_enviar:
        st.warning("⚠️ Nenhum ID válido foi encontrado para exclusão.")
        return
    
    # Verifica se há eventos de sistema no lote (onde fk_evento não é None)
    tem_eventos_sistema = any(reg.get("fk_evento") is not None for reg in registros)
    
    # Salva variáveis necessárias para o modal
    state["ids_deletar_pendentes"] = ids_para_enviar
    state["tem_eventos_sistema"] = tem_eventos_sistema
    
    # Dispara o modal dinâmico
    modal_confirmar_delecao_eventos()


def acao_edit(registro: Dict[str, Any]) -> None:
    """ Transiciona para a tela de edição do evento selecionado."""
    state = st.session_state.get(PAGE_KEY, {})
    state["evento_selecionado"] = registro
    state["modo_tela"] = "editar"
    state["form_key_count"] = state.get("form_key_count", 0) + 1


def alternar_status_lote(registros: List[Dict[str, Any]]) -> None:
    """Alterna o status dos eventos em lote acumulando resultados em listas."""

    if not registros:
        return

    # Uso de listas simples para armazenar os IDs processados
    sucessos = []
    erros = []

    for reg in registros:
        id_evento = reg.get("id")

        if id_evento is None or "aceito" not in reg:
            continue

        novo_status = not bool(reg.get("aceito"))

        try:
            executar_requisicao_alterar_status_evento(id_evento=id_evento, aceito=novo_status)
            #  Append simples do ID com sucesso
            sucessos.append(id_evento)
        except Exception:
            # Append simples do ID que falhou (sem uso de logger)
            erros.append(id_evento)

    # Montagem de mensagens para a sessão utilizando o tamanho das listas (len)
    if sucessos:
        ir_para_listagem_limpo()
        st.session_state["toast_pendente"] = {
            "mensagem": f"Status de {len(sucessos)} evento(s) alterado com sucesso!",
            "icone": "✅",
        }

    if erros:
        st.session_state["erro_pendente"] = f"Falha ao alterar os eventos IDs: {erros}"

    #  Atualização do estado do Streamlit
    state = st.session_state.get(PAGE_KEY, {})
    state["ultimo_ativo_carregado"] = None
    state["ultimo_carregar_tudo"] = False


def garantir_dados_em_cache(state_dict: Dict[str, Any]) -> None:
    """
    Gerenciador Inteligente de Cache.
    Evita chamadas repetidas à API quando a tela faz re-runs no Streamlit.
    """
    ativo_atual = state_dict.get("ativo_original")
    carregar_tudo = state_dict.get("carregar_tudo", False)

    # 1. Caso base: Nenhum ativo selecionado e "Carregar Tudo" desativado -> Limpa dados
    if ativo_atual == "Selecionar Ativo" and not carregar_tudo:
        state_dict["dados"] = []
        state_dict["ultimo_ativo_carregado"] = None
        state_dict["ultimo_carregar_tudo"] = False
        return

    try:
        # 2. Modo "Carregar Tudo": Executa se ativado e ainda não carregou o lote completo
        if carregar_tudo:
            if not state_dict.get("ultimo_carregar_tudo"):
                with st.spinner("Buscando todos os eventos corporativos..."):
                    state_dict["dados"] = listar_eventos_api()
                    state_dict["ultimo_carregar_tudo"] = True
                    state_dict["ultimo_ativo_carregado"] = None  # Reseta controle por ativo

        #  3. Modo Ativo Específico: Executa se mudou o ativo OU se "Carregar Tudo" acabou de ser desativado
        elif ativo_atual != "Selecionar Ativo":
            precisa_recarregar = ativo_atual != state_dict.get("ultimo_ativo_carregado") or state_dict.get("ultimo_carregar_tudo")
                        
            if precisa_recarregar:
                with st.spinner(f"Buscando eventos de {ativo_atual}..."):
                    # Atribuição direta do retorno da API e sincronização do estado de cache
                    state_dict["dados"] = listar_eventos_api(ativo_id=ativo_atual)
                    state_dict["ultimo_ativo_carregado"] = ativo_atual
                    state_dict["ultimo_carregar_tudo"] = False

    except Exception as e:
        state_dict["dados"] = []
        state_dict["ultimo_ativo_carregado"] = None
        state_dict["ultimo_carregar_tudo"] = False
        st.error(f"Erro ao atualizar cache de dados: {str(e)}")


# ==============================================================================
# 🏢 4. RENDERIZAÇÃO DAS TELAS (FLUXO DINÂMICO)
# ==============================================================================
if state["modo_tela"] == "listagem":
    col_titulo, col_btn_cart, col_btn_mov, col_btn_novo = st.columns([3, 1, 1, 1], vertical_alignment="center")

    with col_titulo:
        st.title("🧐 Eventos Corporativos na Carteira")
        st.caption("Gerencie desdobramentos, bonificações, proventos e agrupamentos.")

    with col_btn_cart:
        if st.button("📊 Composição", type="secondary", width="stretch"):
            st.switch_page("Pages/Carteira/dashboard_carteira.py")

    with col_btn_mov:
        if st.button("📜 Extrato de Movimentações", type="secondary", width="stretch"):
            st.switch_page("Pages/Carteira/movimentacao.py")
    

    with col_btn_novo:
        if st.button("➕ Criar Evento Corporativo", type="primary", width="stretch"):
            state["evento_selecionado"] = None
            state["modo_tela"] = "inserir_manual_evento"
            state["form_key_count"] = state.get("form_key_count", 0) + 1
            st.rerun()

    # Grid de Filtros Superiores
    c1, c2, c3 = st.columns([1.5, 2.5, 1.5], vertical_alignment="bottom")
    with c1:
        if st.button("👁️ Carregar Tudo", width="stretch"):
            state["carregar_tudo"] = True
            state["ultimo_carregar_tudo"] = False
            state["ativo_original"] = "Selecionar Ativo"
            state["reset_buscador_count"] += 1
            st.rerun()

    with c2:
        sufixo_dinamico = f"evt_{state['reset_buscador_count']}"
        componente_buscador_ativo(state, "ativo_original", sufixo_key=sufixo_dinamico)

    with c3:
        if state["ativo_original"] != "Selecionar Ativo" or state["carregar_tudo"]:
            if st.button("🧹 Limpar Filtros", width="stretch"):
                state["ativo_original"] = "Selecionar Ativo"
                state["reset_buscador_count"] += 1
                state["carregar_tudo"] = False
                state["dados"] = []
                state["ultimo_ativo_carregado"] = None
                state["ultimo_carregar_tudo"] = False
                st.rerun()

    # Atualização Transparente do Cache
    garantir_dados_em_cache(state)
    dados_para_exibir = state.get("dados", [])

    if state["ativo_original"] == "Selecionar Ativo" and not state["carregar_tudo"]:
        st.info("💡 Selecione um ativo no menu ou clique em **Carregar Tudo** para visualizar os eventos.")
    elif not dados_para_exibir:
        st.warning("Nenhum evento corporativo encontrado.")
    else:
        st.caption(f"Exibindo {len(dados_para_exibir)} eventos cadastrados:")

        #  Filtros Visuais no Frontend (Multiselect)
        fc1, fc2 = st.columns(2)
        with fc1:
            tipos_disponiveis = list(set([e.get("tipo", "") for e in dados_para_exibir if e.get("tipo")]))
            tipos_selecionados = st.multiselect("Filtrar por Tipo de Evento", options=tipos_disponiveis, key="filtro_tipo_evt")

        with fc2:
            ativos_disponiveis = list(set([e.get("fk_ativo_base", "") for e in dados_para_exibir if e.get("fk_ativo_base")]))
            ativos_selecionados = st.multiselect(
                "Filtrar por Ativo",
                options=ativos_disponiveis,
                format_func=formatar_ativo_visual,
                key="filtro_ativo_evt"
            )

        # Aplicação dos filtros em memória
        dados_filtrados = dados_para_exibir
        if tipos_selecionados:
            dados_filtrados = [e for e in dados_filtrados if e.get("tipo") in tipos_selecionados]
        if ativos_selecionados:
            dados_filtrados = [e for e in dados_filtrados if e.get("fk_ativo_base") in ativos_selecionados]

        #  Exibição da Tabela Padronizada
        exibir_tabela_generica(
            dados=dados_filtrados,
            config_colunas=CONFIG_EVENTOS,
            colunas_resumidas=COLUNAS_RESUMIDAS,
            callback_edit=acao_edit,
            callback_deletar=acao_deletar,
            callback_estilo=colorir_linhas_eventos,
            botoes_acao=[{
                            "label": "",
                            "icone": "🔄",
                            "callback": alternar_status_lote,
                            "somente_unico": False,  # Permite alternar 1 ou vários registros de uma vez
                            "help": "Alternar status (Ativo / Inativo) do(s) registro(s) selecionado(s)"
                        }],
            chave_tabela="eventos_principal",
            suporta_moeda=True
        )

elif state["modo_tela"] in ["editar", "inserir_manual_evento"]:
    if st.button("⬅️ Voltar para a Listagem", key="btn_voltar_eventos"):
        state["modo_tela"] = "listagem"
        st.rerun()

    key_from = state.get("form_key_count", 0)

    if state["modo_tela"] == "inserir_manual_evento":
        st.title("➕ Criar Novo Evento Corporativo")
        renderizar_layout_edit_evento(
            registro_selecionado=None,
            key_estado_dinamico=f"form_novo_evento_{key_from}",
            origin_config={
                            "callback_request_api": lambda payload: executar_requisicao_insert_evento(payload=payload),
                            "label_btn_gravar": "🚀 Criar Evento",
                            "modo_insert": "MANUAL INSERT"
                            },
            on_sucesso=ir_para_listagem_limpo
        )

    elif state["modo_tela"] == "editar":
        st.title("✏️ Editar Evento Corporativo")
        evento_atual = state.get("evento_selecionado", {})
        evt_id = evento_atual.get("id")
        dados_selecionado = {"dados_origem": evento_atual}

        renderizar_layout_edit_evento(
            registro_selecionado=dados_selecionado,
            key_estado_dinamico=f"form_edit_evento_{evt_id}_{key_from}",
            origin_config={
                            "callback_request_api": lambda payload: executar_requisicao_editar_evento(id_evento=evt_id, payload=payload),
                            "label_btn_gravar": "💾 Gravar Evento",
                            "modo_insert": "MANUAL EDIT"
                            },
            on_sucesso=ir_para_listagem_limpo
        )
