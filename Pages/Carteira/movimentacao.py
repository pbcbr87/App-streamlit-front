import streamlit as st
import pandas as pd
import io
from Pages.utils.components import componente_buscador_ativo, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_ativo_visual
from Pages.utils.form_edit import (renderizar_layout_edit_evento, 
                                   renderizar_layout_edit_ordem, 
                                   renderizar_layout_importacao_tabela)
from Pages.utils.request_api import (buscar_movimentacoes_api, listar_ordens_input_api,
                                     obter_detalhe_movimentacao_api,
                                     executar_requisicao_insert_evento,
                                     executar_requisicao_edit_movimentacoes,
                                     executar_requisicao_insert_ordens,
                                     buscar_ordens_pendentes_api)
from Pages.utils.modals import modal_confirmar_delecao, modal_confirmar_zerar_carteira



def render_botao_download_ordens_excel(ordens) -> None:
    """Busca as ordens input pendentes e gera Excel formatando datas para dd/mm/yyyy
    e números no padrão nativo PT-BR.
    """
    if not ordens:
        st.info("Nenhuma ordem encontrada para exportação.")
        return

    df = pd.DataFrame(ordens)
    
    cols_para_remover = ["id", "fk_usuario"]
    df = df.drop(columns=[col for col in cols_para_remover if col in df.columns])

    # 1. Converte a coluna de data para o tipo Date do pandas
    if "data_operacao" in df.columns:
        df["data_operacao"] = pd.to_datetime(
            df["data_operacao"], errors="coerce"
        ).dt.date

    #  2. Garante que as colunas numéricas sejam float (para o Excel entender como número)
    colunas_decimais = ["custo_operacao", "taxas", "quant"]
    for col in colunas_decimais:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    output = io.BytesIO()

    # 🟡 3. Utiliza openpyxl para formatar exibições nativas (datas e números)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ordens Input")

        workbook = writer.book
        worksheet = writer.sheets["Ordens Input"]

        # Formatação da coluna de Data (dd/mm/yyyy)
        if "data_operacao" in df.columns:
            col_data_idx = df.columns.get_loc("data_operacao") + 1
            for row in range(2, len(df) + 2):
                cell = worksheet.cell(row=row, column=col_data_idx)
                cell.number_format = "dd/mm/yyyy"  #  Formato nativo de data

        #  Formatação das colunas numéricas (#,##0.00)
        col_indices_num = [
            df.columns.get_loc(col) + 1
            for col in colunas_decimais
            if col in df.columns
        ]

        for col_idx in col_indices_num:
            for row in range(2, len(df) + 2):
                cell = worksheet.cell(row=row, column=col_idx)
                cell.number_format = "#,##0.00"

    excel_data = output.getvalue()

    st.download_button(
        label="📥 Baixar Ordens (Excel)",
        data=excel_data,
        file_name="ordens_input.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_download_ordens_excel"
    )


# ==============================================================================
# 🎯 1. INICIALIZAÇÃO BLINDADA DOS ESTADOS DA SESSÃO (SESSION STATE)
# ==============================================================================
if 'page_movimentacao' not in st.session_state:
    st.session_state['page_movimentacao'] = {}

state = st.session_state['page_movimentacao']

# Inicialização limpa e padronizada das chaves de controle
state.setdefault('ativo_original', "Selecionar Ativo")
state.setdefault('reset_buscador_count', 0)
state.setdefault('carregar_tudo', False)
state.setdefault('movimentacao_selecionada', None)
state.setdefault('modo_tela', "listagem")
state.setdefault('dados', [])

# Chaves essenciais de controle de cache (impedem requests repetitivos à API)
state.setdefault('ultimo_ativo_carregado', None)
state.setdefault('ultimo_carregar_tudo', False)

if 'ordens_pendentes' not in state:
    state['ordens_pendentes'] = buscar_ordens_pendentes_api()


def colorir_linhas_status(dataframe_da_tela, dados_originais):
    # Cria a matriz de estilo em branco com as dimensões exatas da tela
    estilo = pd.DataFrame('', index=dataframe_da_tela.index, columns=dataframe_da_tela.columns)
    
    for idx, row in dataframe_da_tela.iterrows():
        # O 'idx' corresponde exatamente à posição do registro na sua lista original 'dados'
        registro_bruto = dados_originais[idx]
        
        # Agora você tem acesso a QUALQUER campo do dicionário original da sua query/banco
        fk_ord = registro_bruto.get("fk_ord_input")
        fk_evt = registro_bruto.get("fk_evento_usuario")
        
        # Aplica a mesma regra de negócio diretamente no dado raiz
        if pd.isna(fk_evt) and pd.isna(fk_ord):
            estilo.loc[idx] = 'background-color: #fff3cd; color: #856404; font-style: italic;'
            
    return estilo

def adicionar_badge_tipo(linha) -> str:
    """🛠️ Analisa o valor numérico de preco_contabil_brl e injeta o badge visual no tipo."""
    try:
        
        valor_raw = linha.get('preco_contabil_brl')
        quant = float(valor_raw) if valor_raw is not None else 0.0

        icone = "🟢" if quant > 0 else ("🔴" if quant < 0 else "⚪")

        tipo_texto = linha.get('tipo') or ''
        
        return f"{icone} {tipo_texto}".strip()
    except (ValueError, TypeError):
        # 🛠️ Fallback seguro em caso de falha de conversão no float
        return str(linha.get('tipo') or '')

def adicionar_status(fk_ord_input, fk_evento_usuario) -> str:
    """🛠️ Analisa os valores dos campos e injeta o status correto."""
    try:
        # 🛠️ Uso de is None em vez de pd.isna para dados nativos Python
        if fk_evento_usuario is None and fk_ord_input is None:
            return "UPDATE"
        return "OK"
    except Exception:
        return 'ERRO'

# Configuração declarativa de colunas da tabela de movimentações
CONFIG_MOVIMENTACOES = {
    "id":               {"titulo":"id", "tipo": "hide"},
    "fk_ativo_visual":  {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo"))},
    "status":           {"titulo": "Status", "tipo": "text", "funcao_map": lambda row: adicionar_status(row.get("fk_ord_input"), row.get("fk_evento_usuario"))},
    "seq":              {"titulo": "🔢 Seq", "tipo": "number", "precisao": 0},
    "data_op_pag":      {"titulo": "📅 Data Op", "tipo": "date"},
    "tipo":             {"titulo": "⚡ Tipo", "tipo": "text", "funcao_map": adicionar_badge_tipo},
    "quant_":           {"titulo": "📊 Qtd", "tipo": "number", "precisao": 6},
    "quant_acum":       {"titulo": "📈 Acum", "tipo": "number", "precisao": 6},
    "quant_fracao":     {"titulo": "🧩 Frac", "tipo": "number", "precisao": 6},
    "dolar_bc":         {"titulo": "💵 Dólar BC", "tipo": "currency", "multi_moeda": False, "precisao": 4},
    "preco_contabil":   {"titulo": "📐 Delta Custo", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "valor_financeiro": {"titulo": "💰 Valor Op", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "custo_acum":       {"titulo": "🛡️ Custo Acum", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "lucro":            {"titulo": "🏆 Lucro", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "rend_trib_excl":   {"titulo": "🏛️ Rend Trib", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "data_update":      {"titulo": "📅 Atualizado em", "tipo": "date"}
}

COLUNAS_RESUMIDAS = ["fk_ativo_visual", "data_op_pag", "tipo", "quant_","quant_acum", "preco_contabil","custo_acum", "lucro", "rend_trib_excl"]


def adicionar_preco_unit(quant, custo) -> float:
    """🛠️ Calcula o preço unitário (custo / quantidade) tratando nulos e divisão por zero."""
    try:
        # 🛠️ Conversão para float e tratamento de None em Python puro (sem pd.isna)
        q = float(quant) if quant is not None else 0.0
        c = float(custo) if custo is not None else 0.0

        # 🛠️ Validação de divisão por zero
        if q == 0.0:
            return 0.0

        return c / q
    except (ValueError, TypeError):
        return 0.0


CONFIG_ORDEM = {
    "Data do Negócio":       {"titulo":"📅 Data do Negócio", "tipo": "text"},
    "Tipo de Movimentação":  {"titulo": "⚡ Tipo", "tipo": "text"},
    "Mercado":               {"titulo": "🏬 Mercado", "tipo": "text"},
    "Instituição":           {"titulo": "🏛️ Instituição", "tipo": "text"},
    "Código de Negociação":  {"titulo": "🏷️ Código de Negociação", "tipo": "text"},
    "Quantidade":            {"titulo": "📊 Quantidade", "tipo": "text", "precisao": 6},
    "Preço":                 {"titulo": "💰 Preço Unitário", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "Valor":                 {"titulo": "🛡️ Valor Total", "tipo": "currency", "multi_moeda": False, "precisao": 2},

    "data_operacao":  {"titulo": "📅 Data do Negócio", "tipo": "text"},
    "codigo_ativo":   {"titulo": "🏷️ Ativo", "tipo": "text"},
    "categoria":      {"titulo": "📂 Categoria", "tipo": "text"},
    "c_v":            {"titulo": "⚡ Operação", "tipo": "text"},
    "quant":          {"titulo": "📊 Quantidade", "tipo": "number", "precisao": 6},
    "custo_operacao": {"titulo": "🛡️ Valor Total", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "preco_unit":     {"titulo": "💰 Preço Unitário", "tipo": "currency", "multi_moeda": False,"funcao_map": lambda row: adicionar_preco_unit(row.get("quant"), row.get("custo_operacao"))},
    "taxas":          {"titulo": "💸 Taxas", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "corretora":      {"titulo": "🏦 Corretora", "tipo": "text"},
    "comentario":     {"titulo": "💬 Comentário", "tipo": "text"}
}

CONFIG_ERRO = {
    "Motivo do Erro": {"titulo": "🚨 Detalhe do Erro", "tipo": "text"},
    "codigo_ativo":   {"titulo": "🏷️ Ativo", "tipo": "text"},
    "categoria":      {"titulo": "📂 Categoria", "tipo": "text"},
    "c_v":            {"titulo": "⚡ Operação", "tipo": "text"},
    "data_operacao":  {"titulo": "📅 Data do Negócio", "tipo": "text"},
    "quant":          {"titulo": "📊 Quantidade", "tipo": "number", "precisao": 6},
    "custo_operacao": {"titulo": "🛡️ Valor Total", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "taxas":          {"titulo": "💸 Taxas", "tipo": "currency", "multi_moeda": False, "precisao": 2},
    "corretora":      {"titulo": "🏦 Corretora", "tipo": "text"},
    "comentario":     {"titulo": "💬 Comentário", "tipo": "text"}
}



# ==============================================================================
# ⚙️ 2. CALLBACKS DE AÇÕES DA TABELA
# ==============================================================================
def acao_deletar(registros: list):
    """Callback disparado pela tabela para iniciar o fluxo de exclusão."""
    state_loc = st.session_state.get('page_movimentacao', {})
    
    ids_para_enviar = [reg.get('id') for reg in registros if reg.get('id') is not None]
    
    if not ids_para_enviar:
        st.warning("⚠️ Nenhum ID válido foi encontrado para exclusão.")
        return
    
    # Avalia se existe algum evento vinculado no lote selecionado
    # (Ajuste a chave se na sua tabela for 'fk_evento' ou 'fk_evento_usuario')
    tem_eventos = any(
        reg.get('fk_evento_usuario') is not None or reg.get('fk_evento') is not None 
        for reg in registros
    )
    
    # Salva os IDs e a flag no state
    state_loc['ids_deletar_pendentes'] = ids_para_enviar
    state_loc['deletar_tem_eventos'] = tem_eventos
    
    # Dispara a modal
    modal_confirmar_delecao()

def acao_edit(registro: dict):
    """Dispara a busca detalhada do registro e abre a tela de edição."""
    state_loc = st.session_state['page_movimentacao']
    try:
        movimentacao_id = registro.get('id')
        if not movimentacao_id:
            st.warning("⚠️ Nenhum ID válido foi encontrado desta movimentação.")
            return

        st.write("")
        with st.spinner("Buscando dados de origem no servidor..."):
            registro_completo = obter_detalhe_movimentacao_api(str(movimentacao_id))
        
        if "form_key_count" in state_loc:
            state_loc['form_key_count'] += 1
        else:
            state_loc['form_key_count'] = 0

        state_loc['movimentacao_selecionada'] = registro_completo
        state_loc['modo_tela'] = "editar"
    except Exception as e:
        st.toast(f"❌ Não foi possível abrir a edição: {str(e)}", icon="❌")

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
                    state['dados'] = buscar_movimentacoes_api(ativo_id=ativo_atual)
                    state['ultimo_ativo_carregado'] = ativo_atual
                    state['ultimo_carregar_tudo'] = False

        # Caso 3: Solicitação de Carga Completa (E ainda não está em cache)
        elif carregar_tudo:
            if not state.get('ultimo_carregar_tudo'):
                st.write("")
                with st.spinner("Buscando histórico completo..."):
                    state['dados'] = buscar_movimentacoes_api(ativo_id=None)
                    state['ultimo_carregar_tudo'] = True
                    state['ultimo_ativo_carregado'] = None

    except Exception as e:
        # Em caso de erro na API, limpa o cache preventivamente e exibe mensagem
        state['dados'] = []
        state['ultimo_ativo_carregado'] = None
        state['ultimo_carregar_tudo'] = False
        st.error(f"Erro ao carregar dados do servidor: {str(e)}")

# ==============================================================================
# 🏢 3. RENDERIZAÇÃO DAS TELAS (FLUXO DINÂMICO)
# ==============================================================================
if state['modo_tela'] == "listagem":    
    col_titulo, col_btn_cart, col_btn_zerar, col_btn_novo, col_btn_novo_evento, col_btn_download = st.columns([2.5, 1, 1, 1, 1, 1], vertical_alignment="center")
    
    with col_titulo:
        st.title("📜 Extrato de Movimentações")
        st.caption("Selecione um ativo específico ou carregue todo o histórico.")

    with col_btn_cart:
        if st.button("📊 Composição", type="primary", width='stretch'):
            st.switch_page('Pages/Carteira/dashboard_carteira.py')

    with col_btn_zerar:
        if st.button("🗑️ Zerar Carteira", type="secondary", width='stretch'):
            modal_confirmar_zerar_carteira()
 
    with col_btn_novo.popover("➕ Nova Ordem", width="stretch"):
        st.markdown("### Método de entrada")

        # OPÇÃO A: Upload de Arquivo/Excel (Faz tudo rápido direto no Popover)
        st.markdown("**1. Importar Tabela / Excel (B3)**")
        if st.button("🚀 Enviar Pacote de Ordens", width="stretch"):
            state['movimentacao_selecionada'] = None  # Indica que é um registro NOVO
            state['modo_tela'] = "inserir_table"
            state['form_key_count'] = state.get('form_key_count', 0) + 1
            st.rerun()

        # OPÇÃO B: Lançamento Manual (Redireciona para a tela limpa de formulário)
        st.markdown("**2. Lançamento Manual**")
        if st.button("📝 Preencher Formulário", width="stretch"):
            state['movimentacao_selecionada'] = None  # Indica que é um registro NOVO
            state['modo_tela'] = "inserir_manual_ordem"
            state['form_key_count'] = state.get('form_key_count', 0) + 1
            st.rerun()

    with col_btn_novo_evento.popover("🎁 Eventos", width="stretch"):
        st.markdown("**1. Ir a Pagina Gerenciar Eventos Corporativos**")
        if st.button("🎁 Gerenciar Eventos", width="stretch"):
            st.switch_page('Pages/Carteira/eventos_usuario.py')
            
        st.markdown("**2. Criar Eventos Corporativos**")
        # Lançamento Manual Evento (Redireciona para a tela limpa de formulário)
        if st.button("➕ Criar Evento Corporativo", width="stretch"):
            state['movimentacao_selecionada'] = None  # Indica que é um registro NOVO
            state['modo_tela'] = "inserir_manual_evento"
            state['form_key_count'] = state.get('form_key_count', 0) + 1
            st.rerun()

    with col_btn_download.popover("📤 Exportar", width="stretch", on_change=lambda: state.update({'ordens_input': listar_ordens_input_api()})):
        if "ordens_input" not in state:
            st.info("Carregando arquivo de ordens...")
        if "ordens_input" in state:          
            render_botao_download_ordens_excel(state['ordens_input'])

    if 'ordens_pendentes' in state and state['ordens_pendentes']:
        st.subheader("⚠️ Ordens Pendentes de Processamento")
        exibir_tabela_generica( dados=state['ordens_pendentes'],
                                config_colunas=CONFIG_ORDEM,
                                colunas_resumidas=None,                                
                                chave_tabela="movimentacoes_pendentes",
                                suporta_moeda=False
                                )
        st.warning(f"⚠️ Existem {len(state['ordens_pendentes'])} ordens pendentes de processamento. Aguarde o motor calcular")
        st.divider()
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
        st.caption(f"Exibindo {len(dados_para_exibir)} lançamentos contábeis:")

        # Filtros de Refinamento Visual (Front-end)
        fc1, fc2 = st.columns(2)
        with fc1:
            opcoes_tipos = list(set([mov.get('tipo', '') for mov in dados_para_exibir if mov.get('tipo')]))
            tipos_selecionados = st.multiselect("Filtrar por Tipo", options=opcoes_tipos, key="filtro_tipo")

        with fc2:
            opcoes_ativos = list(set([mov.get('fk_ativo', '') for mov in dados_para_exibir if mov.get('fk_ativo')]))
            ativos_selecionados = st.multiselect("Filtrar por Ativo", options=opcoes_ativos, format_func=formatar_ativo_visual, key="filtro_ativo")

        # Aplicação dos filtros rápidos sobre os dados carregados
        dados_filtrados = dados_para_exibir
        if tipos_selecionados:
            dados_filtrados = [m for m in dados_filtrados if m.get('tipo') in tipos_selecionados]
        if ativos_selecionados:
            dados_filtrados = [m for m in dados_filtrados if m.get('fk_ativo') in ativos_selecionados]

        # Exibição do Grid Contábil
        exibir_tabela_generica(
            dados=dados_filtrados,
            config_colunas=CONFIG_MOVIMENTACOES,
            colunas_resumidas=COLUNAS_RESUMIDAS,
            callback_edit=acao_edit,
            callback_deletar=acao_deletar,
            callback_estilo=colorir_linhas_status,
            chave_tabela="movimentacoes_principal",
            suporta_moeda=True
        )

elif state['modo_tela'] in ["editar", "inserir_manual_ordem", "inserir_table", "inserir_manual_evento"]:
    if st.button("⬅️ Voltar para a Listagem", key="btn_voltar_extrato"):
        state["modo_tela"] = "listagem"
        st.rerun()

    def ir_para_listagem_limpo():
        if 'page_eventos' in st.session_state:
            st.session_state['page_eventos']["ultimo_ativo_carregado"] = None
            st.session_state['page_eventos']["ultimo_carregar_tudo"] = False
            st.session_state['page_eventos']["modo_tela"] = "listagem"
        state['ordens_pendentes'] = None
        state['ultimo_ativo_carregado'] = None
        state['ultimo_carregar_tudo'] = False
        state["modo_tela"] = "listagem"
        st.rerun()

    key_from = state.get('form_key_count', 0)

    # INSERÇÃO MANUAL
    if state['modo_tela'] == "inserir_manual_ordem":
        st.title("➕ Nova Ordem de Compra / Venda")
        
        renderizar_layout_edit_ordem(
            registro_selecionado=None,
            on_sucesso=ir_para_listagem_limpo,
            key_estado_dinamico=f"form_nova_ordem_{key_from}",
            eh_insercao=True
        )
    elif state['modo_tela'] == "inserir_manual_evento":
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
        
    # 🔵 FLUXO DE EDIÇÃO EXISTENTE
    elif state['modo_tela'] == "editar":
        
        movimentacao_atual = state.get('movimentacao_selecionada', {})
        origem = movimentacao_atual.get('origem_registro')

        # Roteamento baseado na origem do registro
        if origem == "eventos":
            st.title("✏️ Editar Evento Corporativo")
            mov_id = movimentacao_atual.get("movimentacao_id", "evento")
            renderizar_layout_edit_evento(
                registro_selecionado=movimentacao_atual,
                on_sucesso=ir_para_listagem_limpo,
                origin_config={
                                "callback_request_api": lambda payload: executar_requisicao_edit_movimentacoes(mov_id=mov_id, payload=payload),
                                "label_btn_gravar": "💾 Gravar Evento",
                                "modo_insert": "MANUAL EDIT"
                                },
                key_estado_dinamico=f"form_{origem}_{mov_id}_{key_from}"
            )          

        elif origem == "ordens":
            st.title("✏️ Editar Ordem de Compra / Venda")
            mov_id = movimentacao_atual.get("movimentacao_id", "nova_ordem")
            # Injeta a chave dinâmica que você planejou
            renderizar_layout_edit_ordem(
                registro_selecionado=movimentacao_atual,
                on_sucesso=ir_para_listagem_limpo,
                key_estado_dinamico=f"form_{origem}_{mov_id}_{key_from}"
            )

        elif origem == "update":
            # 🔄 Texto aprimorado com ícone de sincronização e progresso
            st.info("🔄 **Recálculo em Andamento:** Os saldos e a contabilidade deste ativo estão sendo atualizados pelo sistema. Por favor, aguarde alguns instantes. **Não é possível editar ou modificar os dados deste registro no momento.** ")

    elif state['modo_tela'] == "inserir_table":
        renderizar_layout_importacao_tabela(
                                            titulo="📥 Importação de Ordens por Tabela",
                                            funcao_envio_api=lambda payload: executar_requisicao_insert_ordens(payload=payload, modo_insert="TABELA"),
                                            config_colunas=CONFIG_ORDEM,
                                            modelos_planilha=[
                                                {"nome": "Modelo Padrão App", "path": "resources/Operacao.xlsx", "file_name": "Operacao.xlsx"},
                                                {"nome": "Modelo B3", "path": "resources/Operacao_b3.xlsx", "file_name": "Operacao_b3.xlsx"}
                                            ],
                                            config_colunas_erro=CONFIG_ERRO,
                                            on_sucesso=ir_para_listagem_limpo,
                                            key_estado_dinamico="importacao_ordens_tab"
                                        )
    else:
        st.warning(f"⚠️ Formulário para a origem '{state['modo_tela']}' não foi desenvolvido ainda.")