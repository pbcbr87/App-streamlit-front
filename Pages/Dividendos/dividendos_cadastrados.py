from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from Pages.utils.components import exibir_tabela_generica, componente_buscador_ativo
from Pages.utils.form_dividendos import renderizar_formulario_dividendo
from Pages.utils.form_edit import renderizar_layout_importacao_tabela
from Pages.utils.ferramentas import formatar_ativo_visual
from Pages.utils.request_api import (
    listar_dividendos_global_api,
    obter_dividendo_global_por_id_api,
    atualizar_dividendo_global_api,
    excluir_dividendos_globais_em_lote_api,
    inserir_pacote_dividendos_global_api,
    auditar_dividendos_globais_em_lote_api
)

PAGE_KEY = "page_dividendos_cadastrados"

st.session_state.setdefault(PAGE_KEY, {})
state: Dict[str, Any] = st.session_state[PAGE_KEY]

# Inicialização limpa e padronizada das chaves de controle
state.setdefault('ativo_original', "Selecionar Ativo")
state.setdefault('reset_buscador_count', 0)
state.setdefault('carregar_tudo', False)
state.setdefault('modo_tela', "listagem")
state.setdefault('dados', [])


def formatar_status_auditado(row: Dict[str, Any]) -> str:
    """ Formata a indicação visual de auditoria do dividendo de mercado."""
    return "✅ Auditado" if row.get("auditado") or row.get("aceito") else "⬜ Pendente"


def colorir_linhas_auditadas(dataframe: pd.DataFrame, dados_originais: List[Dict[str, Any]]) -> pd.DataFrame:
    """ Aplica estilo destacado para dividendos pendentes de auditoria/confirmação."""
    estilo = pd.DataFrame("", index=dataframe.index, columns=dataframe.columns)
    for idx, registro in enumerate(dados_originais):
        if not (registro.get("auditado") or registro.get("aceito")):
            estilo.loc[idx] = "color: #856404; background-color: #fff3cd; font-style: italic;"
    return estilo


CONFIG_DIVIDENDOS_GLOBAIS = {
    "id": {"titulo": "ID", "tipo": "hide"},
    "auditado": {"titulo": "⚙️ Auditado", "tipo": "text", "funcao_map": formatar_status_auditado},
    "conflito": {"titulo": "⚠️ Conflito", "tipo": "text"},
    "fk_ativo": {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo"))},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "valor_bruto": {"titulo": "💰 Bruto", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "valor_liq": {"titulo": "💵 Líquido", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "data_aprov": {"titulo": "📅 Aprovação", "tipo": "date"},
    "data_com": {"titulo": "📅 Data Com", "tipo": "date"},
    "data_pag": {"titulo": "📅 Pagamento", "tipo": "date"},
    "ano_calendario_ir": {"titulo": "📅 Ano IR", "tipo": "number", "precisao": 0},
    "origem_dado": {"titulo": "📤 Origem", "tipo": "text"},
    "data_insert": {"titulo": "🕒 Cadastro", "tipo": "date"},
    "modo_insert": {"titulo": "📥 Origem", "tipo": "text"},
}

CONFIG_IMPORTACAO_DIVIDENDOS = {
    "fk_ativo": {"titulo": "🏷️ Ativo", "tipo": "text"},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "valor_bruto": {"titulo": "💰 Bruto", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "valor_liq": {"titulo": "💸 Líquido", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "data_aprov": {"titulo": "📅 Aprovação", "tipo": "date"},
    "data_com": {"titulo": "📅 Data Com", "tipo": "date"},
    "data_pag": {"titulo": "📅 Pagamento", "tipo": "date"},
    "ano_calendario_ir": {"titulo": "📅 Ano IR", "tipo": "number", "precisao": 0},
}

CONFIG_ERRO_IMPORTACAO_DIVIDENDOS = {
    **CONFIG_IMPORTACAO_DIVIDENDOS,
    "Motivo do Erro": {"titulo": "🚨 Motivo do Erro", "tipo": "text"},
}


def acao_editar(registro: Dict[str, Any]) -> None:
    """ Prepara a tela para edição do registro de mercado selecionado."""
    state_loc = st.session_state[PAGE_KEY]
    try:
        dividendo_id = registro.get('id')
        if not dividendo_id:
            st.warning("⚠️ Nenhum ID válido foi encontrado deste dividendo.")
            return

        st.write("")
        with st.spinner("Buscando dados de origem no servidor..."):
            registro_completo = obter_dividendo_global_por_id_api(dividendo_id)

        state_loc["registro_selecionado"] = registro_completo
        state_loc["modo_tela"] = "editar"
        state_loc["form_key_count"] = state_loc.get("form_key_count", 0) + 1
    except Exception as e:
        st.toast(f"❌ Não foi possível abrir a edição: {str(e)}", icon="❌")


def acao_excluir(registros: List[Dict[str, Any]]) -> None:
    """ Processa a exclusão de dividendos no cadastro de mercado."""
    state_loc = st.session_state[PAGE_KEY]
    try:
        ids = [registro["id"] for registro in registros]
        excluir_dividendos_globais_em_lote_api(ids=ids)
        st.session_state["toast_pendente"] = {
            "mensagem": f"✅ {len(registros)} dividendo(s) global(is) excluído(s).",
            "icone": "🗑️"
        }
        state_loc["dados"] = []
        state_loc["modo_tela"] = "listagem"
        state_loc['ultimo_ativo_carregado'] = None
        state_loc['ultimo_carregar_tudo'] = False
    except Exception as erro:
        st.error(f"❌ Erro ao excluir dividendos do cadastro geral: {erro}")


def acao_alternar_auditoria(registros: List[Dict[str, Any]]) -> None:
    """ Altera o status de auditoria/aprovação do dividendo global."""
    state_loc = st.session_state[PAGE_KEY]
    try:
        ids = [registro["id"] for registro in registros]
        auditar_dividendos_globais_em_lote_api(ids=ids)
        state_loc["dados"] = []
        state_loc["modo_tela"] = "listagem"
        state_loc['ultimo_ativo_carregado'] = None
        state_loc['ultimo_carregar_tudo'] = False
        
    except Exception as erro:
        st.error(f"❌ Erro ao alterar status de auditoria: {erro}")


def salvar_dividendo(payload: Dict[str, Any], editando: bool) -> bool:
    """ Salva inserção ou edição utilizando as rotas de API globais/admin."""
    dados = dict(payload)
    dividendo_id = dados.pop("id", None)
    if editando:
        return bool(atualizar_dividendo_global_api(dividendo_id, dados))
    return bool(inserir_pacote_dividendos_global_api({"dados": [dados]}, modo_insert="MANUAL"))


def voltar_listagem() -> None:
    """ Reseta os estados temporários do formulário e retorna para a listagem."""
    state = st.session_state[PAGE_KEY]
    state["modo_tela"] = "listagem"
    state['ultimo_ativo_carregado'] = None
    state['ultimo_carregar_tudo'] = False
    st.rerun()


def garantir_dados_em_cache(state: dict):
    """ Gerenciador Inteligente de Cache para a API Admin de Dividendos Globais.
    
    Analisa os filtros ativos e atualiza a memória somente se os parâmetros tiverem mudado.
    """
    ativo_atual = state.get('ativo_original')
    carregar_tudo = state.get('carregar_tudo')

    # Caso 1: Filtro vazio e sem instrução de carregar tudo
    if ativo_atual == "Selecionar Ativo" and not carregar_tudo:
        state['dados'] = []
        state['ultimo_ativo_carregado'] = None
        state['ultimo_carregar_tudo'] = False
        return

    try:
        # Caso 2: Filtro por Ativo Selecionado (Diferente do que está em cache)
        if ativo_atual != "Selecionar Ativo":
            if ativo_atual != state.get('ultimo_ativo_carregado'):
                st.write("")
                with st.spinner(f"Buscando dividendos globais de {ativo_atual}..."):
                    state['dados'] = listar_dividendos_global_api(ativo_id=ativo_atual)
                    state['ultimo_ativo_carregado'] = ativo_atual
                    state['ultimo_carregar_tudo'] = False

        # Caso 3: Solicitação de Carga Completa
        elif carregar_tudo:
            if not state.get('ultimo_carregar_tudo'):
                st.write("")
                with st.spinner("Buscando cadastro completo de dividendos globais..."):
                    state['dados'] = listar_dividendos_global_api(ativo_id=None)
                    state['ultimo_carregar_tudo'] = True
                    state['ultimo_ativo_carregado'] = None

    except Exception as e:
        state['dados'] = []
        state['ultimo_ativo_carregado'] = None
        state['ultimo_carregar_tudo'] = False
        st.error(f"Erro ao carregar dados do servidor: {str(e)}")


# ==============================================================================
# RENDERIZAÇÃO DA PÁGINA
# ==============================================================================

if state["modo_tela"] == "listagem":
    titulo, btn_novo, btn_importar = st.columns([6, 1, 1], vertical_alignment="center")
    titulo.title("🏛️ Cadastro Global de Dividendos 🛡️")
    
    if btn_novo.button("➕ Novo", type="primary", width="stretch"):
        state["modo_tela"] = "inserir"
        state["form_key_count"] = state.get("form_key_count", 0) + 1
        st.rerun()
        
    if btn_importar.button("📥 Importar", width="stretch"):
        state["modo_tela"] = "importar"
        state["form_key_count"] = state.get("form_key_count", 0) + 1
        st.rerun()
    
    # 1. Grid de Filtros de Entrada
    c1, c2, c3 = st.columns([1.5, 2.5, 1.5], vertical_alignment="bottom")
    with c1:
        if st.button("👁️ Carregar Tudo", width="stretch"):
            state['carregar_tudo'] = True
            state['ativo_original'] = "Selecionar Ativo"
            state['reset_buscador_count'] += 1
            state['dados'] = []
            state['ultimo_ativo_carregado'] = None
            state['ultimo_carregar_tudo'] = False
            st.rerun()

    with c2:
        sufixo_dinamico = f"cadastrados_{state['reset_buscador_count']}"
        componente_buscador_ativo(state, 'ativo_original', sufixo_key=sufixo_dinamico)

    with c3:
        if state['ativo_original'] != "Selecionar Ativo" or state['carregar_tudo']:
            if st.button("🧹 Limpar Filtros", width="stretch"):
                state['ativo_original'] = "Selecionar Ativo"
                state['reset_buscador_count'] += 1
                state['carregar_tudo'] = False
                state['dados'] = []
                state['ultimo_ativo_carregado'] = None
                state['ultimo_carregar_tudo'] = False
                st.rerun()

    # 2. Executa o gerenciador de cache
    garantir_dados_em_cache(state)

    # 3. Define fonte de dados após validação do cache
    dados_para_exibir = state['dados']
    
    # 4. Renderização Condicional da Tabela e Filtros Internos
    if state['ativo_original'] == "Selecionar Ativo" and not state['carregar_tudo']:
        st.info("💡 Escolha um ativo no menu acima ou clique em **Carregar Tudo** para visualizar os registros de mercado.")        
    elif not dados_para_exibir:
        st.warning("Nenhum dividendo global cadastrado encontrado.")        
    else:        
        f1, f2 = st.columns(2)

        opcoes_tipos = list(set([mov.get('tipo', '') for mov in dados_para_exibir if mov.get('tipo')]))
        tipos_selecionados = f1.multiselect("Filtrar por Tipo", options=opcoes_tipos, key="filtro_tipo_admin")
        
        opcoes_ativos = list(set([mov.get('fk_ativo', '') for mov in dados_para_exibir if mov.get('fk_ativo')]))
        ativos_selecionados = f2.multiselect("Filtrar por Ativo", options=opcoes_ativos, format_func=formatar_ativo_visual, key="filtro_ativo_admin")

        if tipos_selecionados:
            dados_para_exibir = [item for item in dados_para_exibir if item.get("tipo") in tipos_selecionados]
        if ativos_selecionados:
            dados_para_exibir = [item for item in dados_para_exibir if item.get("fk_ativo", "") in ativos_selecionados]

        if not dados_para_exibir:
            st.info("💡 Nenhum dividendo encontrado para os filtros selecionados.")
        else:
            exibir_tabela_generica(
                dados=dados_para_exibir,
                config_colunas=CONFIG_DIVIDENDOS_GLOBAIS,
                colunas_resumidas=["auditado", "fk_ativo", "tipo", "valor_bruto", "imposto", "valor_liq", "data_com", "data_pag"],
                callback_edit=acao_editar,
                callback_deletar=acao_excluir,
                callback_estilo=colorir_linhas_auditadas,
                botoes_acao=[{"icone": "🔄", "callback": acao_alternar_auditoria, "somente_unico": False, "help": "Alternar Auditoria/Status"}],
                chave_tabela="dividendos_globais_admin",
                suporta_moeda=True,
            )

else:
    if st.button("⬅️ Voltar para a Listagem", key="voltar_dividendos_cadastrados"):
        voltar_listagem()

    key_form = f"dividendo_admin_{state.get('form_key_count', 0)}"
    if state["modo_tela"] == "importar":
        renderizar_layout_importacao_tabela(
            titulo="📥 Importação em Lote de Dividendos Globais 🛡️",
            funcao_envio_api=lambda payload: inserir_pacote_dividendos_global_api(payload, modo_insert="TABELA"),
            config_colunas=CONFIG_IMPORTACAO_DIVIDENDOS,
            config_colunas_erro=CONFIG_ERRO_IMPORTACAO_DIVIDENDOS,
            on_sucesso=voltar_listagem,
            key_estado_dinamico=key_form,
            modelos_planilha=[
                {"nome": "Modelo Padrão Dividendos", "path": "resources/Dividendos.xlsx", "file_name": "Dividendos.xlsx"}
            ]
        )
    else:
        st.title("✏️ Editar Dividendo Global 🛡️" if state["modo_tela"] == "editar" else "➕ Novo Dividendo Global 🛡️")
        renderizar_formulario_dividendo(
                                            registro=state.get("registro_selecionado") if state["modo_tela"] == "editar" else None,
                                            on_salvar=salvar_dividendo,
                                            on_sucesso=voltar_listagem,
                                            key_estado_dinamico=key_form,
                                            dado_global=True
                                        )