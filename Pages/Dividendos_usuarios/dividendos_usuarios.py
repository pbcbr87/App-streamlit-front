from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from Pages.utils.components import exibir_tabela_generica, componente_buscador_ativo
from Pages.utils.form_dividendos import renderizar_formulario_dividendo
from Pages.utils.form_edit import renderizar_layout_importacao_tabela
from Pages.utils.ferramentas import formatar_ativo_visual
from Pages.utils.request_api import (
                                        alterar_status_dividendo_api,
                                        editar_dividendo_api,
                                        excluir_dividendo_api,
                                        inserir_dividendo_api,
                                        listar_dividendos_usuarios_api,
                                    )

PAGE_KEY = "page_dividendos"

st.session_state.setdefault(PAGE_KEY, {})
state: Dict[str, Any] = st.session_state[PAGE_KEY]

# Inicialização limpa e padronizada das chaves de controle
state.setdefault('ativo_original', "Selecionar Ativo")
state.setdefault('reset_buscador_count', 0)
state.setdefault('carregar_tudo', False)
state.setdefault('movimentacao_selecionada', None)
state.setdefault('modo_tela', "listagem")
state.setdefault('dados', [])


def formatar_status(row: Dict[str, Any]) -> str:
    return "✔️ Ativo" if row.get("aceito") else "⚪ Inativo"

def colorir_linhas(dataframe: pd.DataFrame, dados_originais: List[Dict[str, Any]]) -> pd.DataFrame:
    estilo = pd.DataFrame("", index=dataframe.index, columns=dataframe.columns)
    for idx, registro in enumerate(dados_originais):
        if not registro.get("aceito"):
            estilo.loc[idx] = "color: #856404; background-color: #fff3cd; font-style: italic;"
    return estilo

CONFIG_DIVIDENDOS = {
    "id": {"titulo": "ID", "tipo": "hide"},
    "aceito": {"titulo": "⚙️ Status", "tipo": "text", "funcao_map": formatar_status},
    "fk_ativo": {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo"))},
    "tipo": {"titulo": "⚡ Tipo", "tipo": "text"},
    "valor_bruto": {"titulo": "💰 Bruto", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "imposto": {"titulo": "🏛️ Imposto", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "valor_liq": {"titulo": "💵 Líquido", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "data_aprov": {"titulo": "📅 Aprovação", "tipo": "date"},
    "data_com": {"titulo": "📅 Data Com", "tipo": "date"},
    "data_pag": {"titulo": "📅 Pagamento", "tipo": "date"},
    "ano_calendario_ir": {"titulo": "📅 Ano IR", "tipo": "number", "precisao": 0},
    "data_insert": {"titulo": "🕒 Cadastro", "tipo": "date"},
    "modo_insert": {"titulo": "📥 Origem", "tipo": "text"},
}

TIPOS_DIVIDENDO = [
    "DIVIDENDO", "JCP", "REND. TRIBUTADO", "RENDIMENTO",
    "RENDIMENTO EXT", "AMORTIZAÇÃO", "AGENCY PROC. FEE",
]

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
    state["registro_selecionado"] = registro
    state["modo_tela"] = "editar"
    state["form_key_count"] = state.get("form_key_count", 0) + 1


def acao_excluir(registros: List[Dict[str, Any]]) -> None:
    try:
        for registro in registros:
            excluir_dividendo_api(registro["id"])
        st.session_state["toast_pendente"] = {"mensagem": f"✅ {len(registros)} dividendo(s) excluído(s).", "icone": "🗑️"}
        state["dados"] = []
    except Exception as erro:
        st.error(f"❌ Erro ao excluir dividendos: {erro}")


def acao_status(registros: List[Dict[str, Any]]) -> None:
    try:
        for registro in registros:
            alterar_status_dividendo_api(registro["id"], not bool(registro.get("aceito")))
        state["dados"] = []
        st.session_state["toast_pendente"] = {"mensagem": "✅ Status atualizado.", "icone": "🔄"}
    except Exception as erro:
        st.error(f"❌ Erro ao alterar status: {erro}")


def salvar_dividendo(payload: Dict[str, Any], editando: bool) -> bool:
    dados = dict(payload)
    dividendo_id = dados.pop("id", None)
    if editando:
        return editar_dividendo_api(dividendo_id, dados)
    return inserir_dividendo_api({"dados": [dados]}, modo_insert="MANUAL")


def voltar_listagem() -> None:
    state["modo_tela"] = "listagem"
    state["registro_selecionado"] = None
    state["dados"] = []
    st.rerun()


def garantir_dados_em_cache(state: dict):
    """
    Gerenciador Inteligente de Cache para chamadas de API.
    
    Analisa o estado atual dos filtros e só faz a requisição para a API se os 
    parâmetros de busca tiverem mudado. Caso contrário, mantém os dados em memória.
    """
    ativo_atual = state.get('ativo_original')
    carregar_tudo = state.get('carregar_tudo')

    # Caso 1: Filtro vazio e sem comando de "Carregar Tudo" -> Reseta e sai
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
                with st.spinner(f"Buscando movimentações de {ativo_atual}..."):
                    state['dados'] = listar_dividendos_usuarios_api(ativo_id=ativo_atual, sem_data_corte=state.get('sem_data_corte', False))
                    state['ultimo_ativo_carregado'] = ativo_atual
                    state['ultimo_carregar_tudo'] = False

        # Caso 3: Solicitação de Carga Completa (E ainda não está em cache)
        elif carregar_tudo:
            if not state.get('ultimo_carregar_tudo'):
                st.write("")
                with st.spinner("Buscando histórico completo..."):
                    state['dados'] = listar_dividendos_usuarios_api(ativo_id=None, sem_data_corte=state.get('sem_data_corte', False))
                    state['ultimo_carregar_tudo'] = True
                    state['ultimo_ativo_carregado'] = None

    except Exception as e:
        # Em caso de erro na API, limpa o cache preventivamente e exibe mensagem
        state['dados'] = []
        state['ultimo_ativo_carregado'] = None
        state['ultimo_carregar_tudo'] = False
        st.error(f"Erro ao carregar dados do servidor: {str(e)}")

if state["modo_tela"] == "listagem":
    titulo, btn_novo, btn_importar = st.columns([6, 1, 1], vertical_alignment="center")
    titulo.title("💰 Dividendos Cadastrados")
    if btn_novo.button("➕ Novo", type="primary", width="stretch"):
        state["modo_tela"] = "inserir"
        state["form_key_count"] = state.get("form_key_count", 0) + 1
        st.rerun()
    if btn_importar.button("📥 Importar", width="stretch"):
        state["modo_tela"] = "importar"
        state["form_key_count"] = state.get("form_key_count", 0) + 1
        st.rerun()
    
    # 1. Grid de Filtros de Entrada
    c1, c2, c3, c4 = st.columns([1.5, 2.5, 1.5, 0.5], vertical_alignment="bottom")
    with c4:
        state['sem_data_corte'] = st.checkbox("📅 Todos", key="mais_de_um_mes")
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
        sufixo_dinamico = f"o_{state['reset_buscador_count']}"
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

    # 2. Executa o gerenciador de cache de forma transparente 🧠
    garantir_dados_em_cache(state)

    # 3. Define fonte de dados após validação do cache
    dados_para_exibir = state['dados']
    # 4. Renderização Condicional da Interface
    if state['ativo_original'] == "Selecionar Ativo" and not state['carregar_tudo']:
        st.info("💡 Escolha um ativo no menu acima ou clique em **Carregar Tudo**.")        
    elif not dados_para_exibir:
        st.warning("Nenhuma movimentação encontrada.")        
    else:        
        f1, f2 = st.columns(2)

        opcoes_tipos = list(set([mov.get('tipo', '') for mov in dados_para_exibir if mov.get('tipo')]))
        tipos_selecionados = f1.multiselect("Filtrar por Tipo", options=opcoes_tipos, key="filtro_tipo")
        
        opcoes_ativos = list(set([mov.get('fk_ativo', '') for mov in dados_para_exibir if mov.get('fk_ativo')]))
        ativos_selecionados = f2.multiselect("Filtrar por Ativo", options=opcoes_ativos, format_func=formatar_ativo_visual, key="filtro_ativo")

        if tipos_selecionados:
            dados_para_exibir = [item for item in dados_para_exibir if item.get("tipo") in tipos_selecionados]
        if ativos_selecionados:
            dados_para_exibir = [item for item in dados_para_exibir if item.get("fk_ativo", "") in ativos_selecionados]

        if not dados_para_exibir:
            st.info("💡 Nenhum dividendo encontrado para os filtros atuais.")
        else:
            exibir_tabela_generica(
                dados=dados_para_exibir,
                config_colunas=CONFIG_DIVIDENDOS,
                colunas_resumidas=["aceito", "fk_ativo", "tipo", "valor_bruto", "imposto", "valor_liq", "data_com", "data_pag"],
                callback_edit=acao_editar,
                callback_deletar=acao_excluir,
                callback_estilo=colorir_linhas,
                botoes_acao=[{"icone": "🔄", "callback": acao_status, "somente_unico": False, "help": "Alternar status"}],
                chave_tabela="dividendos_principal",
                suporta_moeda=True,
            )

else:
    if st.button("⬅️ Voltar para a Listagem", key="voltar_dividendos"):
        voltar_listagem()

    key_form = f"dividendo_{state.get('form_key_count', 0)}"
    if state["modo_tela"] == "importar":
        renderizar_layout_importacao_tabela(
            titulo="📥 Importação de Dividendos por Tabela",
            funcao_envio_api=lambda payload: inserir_dividendo_api(payload, modo_insert="TABELA"),
            config_colunas=CONFIG_IMPORTACAO_DIVIDENDOS,
            config_colunas_erro=CONFIG_ERRO_IMPORTACAO_DIVIDENDOS,
            on_sucesso=voltar_listagem,
            key_estado_dinamico=key_form,
            modelos_planilha=[
                {"nome": "Modelo Padrão Dividendos", "path": "resources/Dividendos.xlsx", "file_name": "Dividendos.xlsx"}
            ]
        )
    else:
        st.title("✏️ Editar Dividendo" if state["modo_tela"] == "editar" else "➕ Novo Dividendo")
        renderizar_formulario_dividendo(
            registro=state.get("registro_selecionado"),
            moeda=state["moeda"],
            on_salvar=salvar_dividendo,
            on_sucesso=voltar_listagem,
            key_estado_dinamico=key_form,
        )
