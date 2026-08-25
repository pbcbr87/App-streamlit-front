import json
import pandas as pd
import streamlit as st

from Pages.utils.components import componente_buscador_ativo, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_ativo_visual

from Pages.utils.form_edit import renderizar_layout_edit_evento, renderizar_layout_importacao_tabela

from Pages.utils.request_api import (
    executar_requisicao_listar_eventos_corporativos,
    executar_requisicao_obter_evento_corporativo,
    executar_requisicao_inserir_pacote_eventos_corporativos,
    executar_requisicao_criar_evento_corporativo,
    executar_requisicao_atualizar_evento_corporativo,
    executar_requisicao_excluir_eventos_corporativos_lote,
)

# ====================================================================
# Configs da tela e mapeamento de colunas (USANDO O SEU MODEL)
# ====================================================================
PAGE_KEY = "page_eventos_corporativos"

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

CONFIG_COLUNAS_IMPORTACAO_EVENTOS = {
    "fk_ativo_base": {"titulo": "🏷️ Ativo Base", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("fk_ativo_base"))},
    "fk_ativo_gerado": {"titulo": "🏷️ Ativo Gerado", "tipo": "text", "funcao_map": lambda r: formatar_ativo_visual(r.get("fk_ativo_gerado"))},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "data_aprov": {"titulo": "📅 Aprov.", "tipo": "date"},
    "data_com": {"titulo": "📅 Data COM", "tipo": "date"},
    "data_pag": {"titulo": "📅 Data PAG", "tipo": "date"},
    "instrucoes": {"titulo": "🧾 Instruções", "tipo": "text", "funcao_map": resumo_instrucoes},
}

CONFIG_ERRO = {
    "Motivo do Erro": {"titulo": "🚨 Detalhe do Erro", "tipo": "text"},
    **CONFIG_COLUNAS_IMPORTACAO_EVENTOS,
}

COLUNAS_RESUMIDAS_EVENTOS = ["fk_ativo_base", "tipo", "data_com", "data_pag", "instrucoes"]

# ====================================================================
# Estado da página
# ====================================================================
def inicializar_estado():
    if PAGE_KEY not in st.session_state:
        st.session_state[PAGE_KEY] = {}

    state = st.session_state[PAGE_KEY]
    state.setdefault("item_selecionado", None)
    state.setdefault("modo_tela", "listagem")  # listagem, editar, inserir, inserir_pacote
    state.setdefault("dados", [])
    state.setdefault("filtro_busca", "Selecionar Ativo")
    state.setdefault("carregar_tudo", False)
    state.setdefault("ultimo_filtro_carregado", None)
    state.setdefault("ultimo_carregar_tudo", False)
    state.setdefault("reset_buscador_count", 0)
    state.setdefault("form_key_count", 0)

    return state

# ====================================================================
# Estilo opcional da tabela
# ====================================================================
def aplicar_estilo_tabela(dataframe_da_tela: pd.DataFrame, dados_originais) -> pd.DataFrame:
    estilo = pd.DataFrame("", index=dataframe_da_tela.index, columns=dataframe_da_tela.columns)
    for idx in dataframe_da_tela.index:
        if idx < len(dados_originais):
            registro = dados_originais[idx]
            # destaque para eventos sem data_pag (exemplo de regra visual)
            if not registro.get("data_pag"):
                estilo.loc[idx] = "color: #856404; background-color: #fff3cd; font-style: italic;"
    return estilo

# ====================================================================
# Integração com a API (usando seus clients em request_api.py)
# ====================================================================
def buscar_dados_api(filtro=None):
    try:
        if filtro and filtro != "Selecionar Ativo":
            return executar_requisicao_listar_eventos_corporativos(ativo_id=filtro)
        return executar_requisicao_listar_eventos_corporativos(ativo_id=None)
    except Exception:
        raise

def inserir_pacote_api(payload):
    return executar_requisicao_inserir_pacote_eventos_corporativos(payload)

def obter_evento_api(evento_id):
    return executar_requisicao_obter_evento_corporativo(evento_id)

# ====================================================================
# Callbacks
# ====================================================================
def acao_editar(registro):
    state = st.session_state[PAGE_KEY]
    try:
        evento_id = registro.get("id")
        if not evento_id:
            st.warning("ID inválido para edição.")
            return
        with st.spinner("Buscando dados do evento..."):
            dados = obter_evento_api(int(evento_id))
        state["item_selecionado"] = dados
        state["modo_tela"] = "editar"
        state["form_key_count"] += 1
    except Exception as e:
        st.toast(f"Não foi possível abrir a edição: {e}", icon="❌")

def acao_deletar(registros):
    state = st.session_state[PAGE_KEY]
    ids_validos = [r.get("id") for r in registros if r.get("id") is not None]
    if not ids_validos:
        st.warning("Nenhum registro válido selecionado.")
        return

    # Aqui você pode abrir modal_confirmar_delecao; para simplicidade executa direto:
    try:
        sucesso = executar_requisicao_excluir_eventos_corporativos_lote(ids_validos)
        if sucesso:
            st.session_state["toast_pendente"]  = {"mensagem": f"{len(ids_validos)} registro(s) excluído(s).", "icone": "✅"}

            # Invalida cache local da página para forçar recarregamento na listagem
            state["ultimo_ativo_carregado"] = None
            state["ultimo_filtro_carregado"] = None
            state["ultimo_carregar_tudo"] = False
            state["modo_tela"] = "listagem"

    except Exception as e:
       st.session_state["erro_pendente"] = f"❌ Erro ao processar exclusão: {str(e)}"

# ====================================================================
# Cache / sincronização
# ====================================================================
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
            with st.spinner("Carregando todos os eventos..."):
                state["dados"] = buscar_dados_api(filtro=None)
                state["ultimo_carregar_tudo"] = True
                state["ultimo_filtro_carregado"] = None

        elif filtro_atual != "Selecionar Ativo":
            precisa = filtro_atual != state.get("ultimo_filtro_carregado") or state.get("ultimo_carregar_tudo")
            if precisa:
                with st.spinner(f"Buscando eventos para {filtro_atual}..."):
                    state["dados"] = buscar_dados_api(filtro=filtro_atual)
                    state["ultimo_filtro_carregado"] = filtro_atual
                    state["ultimo_carregar_tudo"] = False

    except Exception as exc:
        state["dados"] = []
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        st.error(f"Erro ao carregar dados do servidor: {exc}")


# ====================================================================
# Filtros adicionais para a listagem de eventos (tipo, ativo base, ativo gerado)
# ====================================================================

def aplicar_filtros_eventos(dados_para_exibir):
    # Divisão do layout em 2 colunas para Tipo e Ativo (Base/Gerado)
    col_tipo, col_ativo = st.columns(2)

    tipos_disponiveis = sorted({e.get("tipo", "") for e in dados_para_exibir if e.get("tipo")})
    
    # Unificação das opções únicas de fk_ativo_base e fk_ativo_gerado via união de sets (|)
    ativos_base = {e.get("fk_ativo_base") for e in dados_para_exibir if e.get("fk_ativo_base")}
    ativos_gerados = {e.get("fk_ativo_gerado") for e in dados_para_exibir if e.get("fk_ativo_gerado")}
    ativos_disponiveis = sorted(ativos_base | ativos_gerados)

    with col_tipo:
        tipos_sel = st.multiselect(
            "Filtrar por Tipo",
            options=tipos_disponiveis,
            key="filtro_tipo_eventos"
        )

    with col_ativo:
        # Seletor único de ativos
        ativos_sel = st.multiselect(
            "Filtrar por Ativo (Base ou Gerado)",
            options=ativos_disponiveis,
            key="filtro_ativo_eventos"
        )

    dados_filtrados = dados_para_exibir

    if tipos_sel:
        dados_filtrados = [e for e in dados_filtrados if e.get("tipo") in tipos_sel]

    # Lógica 'OR' para validar se o ativo selecionado é o base OU o gerado
    if ativos_sel:
        dados_filtrados = [
            e for e in dados_filtrados
            if e.get("fk_ativo_base") in ativos_sel or e.get("fk_ativo_gerado") in ativos_sel
        ]

    return dados_filtrados

# ====================================================================
# Renderização da página
# ====================================================================
state = inicializar_estado()

if state["modo_tela"] == "listagem":
    col_titulo, col_btn_novo, col_btn_pacote = st.columns([4, 1, 1], vertical_alignment="center")
    with col_titulo:
        st.title("🎁 Gestão de Eventos Corporativos Cadastrados [ADMIN]")
        st.caption("Visualize, edite, crie e remova eventos corporativos.")

    with col_btn_novo:
        if st.button("➕ Criar Novo", type="primary", width="stretch"):
            state["item_selecionado"] = None
            state["modo_tela"] = "inserir"
            state["form_key_count"] += 1
            st.rerun()

    with col_btn_pacote:
        if st.button("📦 Inserir Pacote Tabela", width="stretch"):
            state["item_selecionado"] = None
            state["modo_tela"] = "inserir_table"
            state["form_key_count"] += 1
            st.rerun()

    c1, c2, c3 = st.columns([1.5, 2.5, 1.5], vertical_alignment="bottom")
    with c1:
        if st.button("👁️ Carregar Tudo", width="stretch"):
            state["carregar_tudo"] = True
            state["filtro_busca"] = "Selecionar Ativo"
            state["reset_buscador_count"] += 1
            st.rerun()
    with c2:
        sufixo = f"evt_{state['reset_buscador_count']}"
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
        st.warning("Nenhum evento encontrado.")
    else:
        st.caption(f"Exibindo {len(dados_para_exibir)} evento(s):")

        dados_filtrados = aplicar_filtros_eventos(dados_para_exibir)
        exibir_tabela_generica(
            dados=dados_filtrados,
            config_colunas=CONFIG_COLUNAS_EVENTOS,
            colunas_resumidas=COLUNAS_RESUMIDAS_EVENTOS,
            callback_edit=acao_editar,
            callback_deletar=acao_deletar,
            callback_estilo=aplicar_estilo_tabela,
            chave_tabela="tabela_eventos_principal",
            suporta_moeda=False,
        )

# Formulário: criar / editar
elif state["modo_tela"] in ["inserir", "editar", "inserir_table"]:
    if st.button("⬅️ Voltar para a Listagem", key="btn_voltar_eventos"):
        state["modo_tela"] = "listagem"
        st.rerun()

    def ir_para_listagem_limpo():
        state["ultimo_filtro_carregado"] = None
        state["ultimo_carregar_tudo"] = False
        state["modo_tela"] = "listagem"
        st.rerun()

    if state["modo_tela"] in ["inserir", "editar"]:
        titulo_form = "➕ Criar Evento Corporativo" if state["modo_tela"] == "inserir" else "✏️ Editar Evento Corporativo"
        st.title(titulo_form)

        key_form = f"form_evento_{state.get('form_key_count', 0)}"
        
        try:
            item = state.get("item_selecionado") or {}
            evento_id = item.get("id")
            dados_origem = {k: v for k, v in item.items() if k != "id"}
            modo_inserir = state.get("modo_tela") == "inserir"

            renderizar_layout_edit_evento(
                    registro_selecionado={"dados_origem": dados_origem},
                    key_estado_dinamico=key_form,
                    origin_config={
                        "callback_request_api": (
                            (lambda payload: executar_requisicao_criar_evento_corporativo(payload))
                            if modo_inserir
                            else (lambda payload: executar_requisicao_atualizar_evento_corporativo(evento_id=evento_id, payload=payload))
                        ),
                        "label_btn_gravar": "🚀 Criar Evento" if modo_inserir else "💾 Gravar Evento",
                        "modo_insert": "MANUAL INSERT" if modo_inserir else "MANUAL EDIT"
                    },
                    on_sucesso=ir_para_listagem_limpo
                )

        except Exception:
            with st.form(key=key_form):
                st.info("Formulário de evento aqui (substitua pelo seu componente real).")
                btn = st.form_submit_button("Salvar")
                if btn:
                    st.toast("Implementar salvamento no renderizador real.", icon="ℹ️")
                    ir_para_listagem_limpo()

    if state["modo_tela"] == "inserir_table":
        renderizar_layout_importacao_tabela(
            titulo="📥 Importação de Eventos por Tabela [ADMIN]",
            funcao_envio_api=executar_requisicao_inserir_pacote_eventos_corporativos,
            config_colunas=CONFIG_COLUNAS_IMPORTACAO_EVENTOS,
            modelos_planilha=[
                {"nome": "Modelo Padrão Eventos", "path": "resources/Eventos.xlsx", "file_name": "Eventos.xlsx"}
            ],
            config_colunas_erro=CONFIG_ERRO,
            on_sucesso=ir_para_listagem_limpo,
            key_estado_dinamico="importacao_eventos_tab"
        )

else:
    st.warning(f"Modo desconhecido: {state['modo_tela']}")