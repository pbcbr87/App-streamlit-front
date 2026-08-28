import streamlit as st
import pandas as pd
from Pages.utils.ferramentas import formatar_data_segura, formatar_ativo_visual, formatar_numero_para_br_str, converter_para_float
from Pages.utils.request_api import checar_status_processamento_api, pesquisar_ativos_api
from typing import List, Dict, Any, Optional, Union


@st.fragment(run_every=50)
def renderizar_status_motor_sidebar(user_id: int):
    container = st.container(border=True)

    with container:
        st.caption("👤 USUÁRIO LOGADO")
        st.markdown(f"**{st.session_state.get('nome', 'Usuário')}**")
        st.caption(f"User: `{st.session_state.get('user', user_id)}`")

        # 🛑 Se o monitoramento não estiver ativo, não realiza chamadas HTTP
        if not st.session_state.get("motor_em_andamento", False):
            st.badge("🟢 Sistema Atualizado", icon="✅")
            return

        # 📡 Checa o status diretamente via client
        try:
            calculando = checar_status_processamento_api(user_id)
        except Exception as e:
            # Exibe status de erro visual quando a API falha
            with st.status("❌ Erro no Sistema", expanded=True, state="error"):
                st.error(
                    "⚠️ **Falha ao verificar status do cálculo**\n\n"
                    "O motor de cálculo pode estar travado ou indisponível. "
                    "Tente recarregar a página ou contate o suporte se o problema persistir.",
                    icon="🚫"
                )
                st.session_state.motor_em_andamento = "ERRO"
            return

        if calculando:
            with st.status("🔄 Calculando...", expanded=False):
                st.caption("Recalculando posições contábeis e proventos...")
                st.info( "💡 Você pode navegar e usar o sistema normalmente.", icon="ℹ️",)
        else:
            st.session_state.motor_em_andamento = False

            # Expurgo das chaves de cache acumuladas na lista_para_update
            for caminho in st.session_state.get("lista_para_update", []):
                partes = caminho.split(".")
                if len(partes) == 1:
                    if partes[0] in st.session_state:
                        del st.session_state[partes[0]]
                    continue

                obj = st.session_state
                for parte in partes[:-1]:
                    if obj is not None and parte in obj:
                        obj = obj[parte]
                    else:
                        obj = None
                        break

                if obj is not None and isinstance(obj, dict):
                    ultima_chave = partes[-1]
                    if ultima_chave in obj:
                        del obj[ultima_chave]

            if "lista_para_update" in st.session_state:
                del st.session_state["lista_para_update"]

            st.rerun()

def processar_notificacoes_pendentes() -> None:
    """Exibe mensagens pendentes acumuladas antes ou depois do rerun."""
    # Resgate direto e seguro do toast (pop evita exceção se a chave não existir)
    toast = st.session_state.pop("toast_pendente", None)
    if toast and isinstance(toast, dict):
        st.toast(toast.get("mensagem", ""), icon=toast.get("icone"))

    # Resgate independente do erro direto do session_state (evita AttributeError)
    erro = st.session_state.pop("erro_pendente", None)
    if erro:
        st.error(erro)

def exibir_tabela_generica(dados: list, config_colunas: dict,colunas_resumidas: list, chave_tabela: str,
    botoes_acao: Optional[List[Dict[str, Any]]] = None,
    callback_edit=None,      
    callback_deletar=None,
    callback_estilo=None,
    suporta_moeda: bool = False,
    formato_data_input: str = "ISO"):
    """
    Renderizador universal de tabelas para o Streamlit.
    Suporta mapeamentos dinâmicos por linha, Modo Cópia regionalizado (PT-BR) via st.code,
    e isolamento de estado por chave única.
    """
    if not dados:
        st.warning("Nenhum registro encontrado para exibição.")
        return

    # 0. NORMALIZAÇÃO DOS BOTÕES (Garante retrocompatibilidade com callback_edit ecallback_deletar)
    lista_botoes = list(botoes_acao) if botoes_acao else []

    if callback_edit and not any(b.get("id") == "edit" for b in lista_botoes):
        lista_botoes.insert(
            0,
            {
                "id": "edit",
                "label": None,
                "icone": "✏️",
                "callback": callback_edit,
                "somente_unico": True,
                "help": "Editar registro selecionado",
            },
        )

    if callback_deletar and not any(b.get("id") == "del" for b in lista_botoes):
        lista_botoes.append(
            {
                "id": "del",
                "label": None,
                "icone": "🗑️",
                "callback": callback_deletar,
                "somente_unico": False,
                "help": "Deletar registro(s) selecionado(s)",
            }
        )

    # --------------------------------------------------------------------------
    # 🎛️ 1. CONTROLES DE INTERFACE & AÇÕES (MESMA LINHA E ALINHADOS À ESQUERDA)
    # --------------------------------------------------------------------------
    # Descobre dinamicamente quais elementos existirão na barra de ferramentas
    tem_botoes = bool(lista_botoes)
    tem_expandir = bool(colunas_resumidas)
    tem_moeda = suporta_moeda

    larguras = []

    if tem_botoes:
        # Reserva 0.6 de largura na barra para cada botão ativo
        larguras.extend([0.6] * len(lista_botoes))
    if tem_expandir:
        larguras.append(2)
    larguras.append(2)
    if tem_moeda:
        larguras.append(2)

    larguras.append(6)  # Mola flexível para empurrar tudo para a esquerda

    cols = st.columns(larguras)
    idx = 0

    # 1. Containers dinâmicos reservando espaço para os botões no topo
    containers_botoes: List[Any] = []
    if tem_botoes:
        for _ in lista_botoes:
            containers_botoes.append(cols[idx])
            idx += 1

    # 2. Toggle Expandir
    ver_detalhes = True
    if tem_expandir:
        with cols[idx]:
            ver_detalhes = st.toggle("🔍 Expandir", value=False, key=f"toggle_expandir_{chave_tabela}")
        idx += 1

    # 3. Toggle Modo Cópia
    with cols[idx]:
        modo_copy = st.toggle("📋 Modo Cópia", value=False, key=f"toggle_copy_{chave_tabela}")
    idx += 1

    # 4. Radio Moeda
    simbolo_moeda = "R$"
    sufixo = ""
    if tem_moeda:
        with cols[idx]:
            moeda_valores = st.radio(
                "Moeda",
                ["BRL", "USD"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"radio_moeda_{chave_tabela}",
            )
        sufixo = "_brl" if moeda_valores == "BRL" else "_usd"
        simbolo_moeda = "R$" if moeda_valores == "BRL" else "$"

    # --------------------------------------------------------------------------
    # 📊 2. PROCESSAMENTO E CUSTOMIZAÇÃO DINÂMICA (PANDAS)
    # --------------------------------------------------------------------------
    # MOTOR DINÂMICO PRÉ-PANDAS: Executa 'funcao_map' nos dicionários nativos.
    # Preserva 'None' como 'None' (evita coerção precoce para np.nan) e ganha performance.
    dados_processados = []
    for registro in dados:
        linha = registro.copy()
        for col_base, cfg in config_colunas.items():
            if "funcao_map" in cfg:
                try:
                    # Passa o dicionário Python nativo onde 'row.get("col") is None' funciona perfeitamente
                    linha[col_base] = cfg["funcao_map"](linha)
                except Exception:
                    pass
        dados_processados.append(linha)

    # Criação do DataFrame a partir dos dados já pré-processados
    df = pd.DataFrame(dados_processados)

    if df.empty:
        st.warning("Nenhum registro encontrado para exibição.")
        return

    # Determina quais colunas estruturais devem ser exibidas
    if ver_detalhes:
        colunas_visiveis = [c for c in config_colunas.keys() if c in df.columns or f"{c}{sufixo}" in df.columns]
    else:
        colunas_visiveis = colunas_resumidas
    # Resolve os nomes físicos reais das colunas tratando chaves com sufixos monetários (_brl/_usd)
    colunas_reais = []
    mapeamento_sufixos = {}
    for col in colunas_visiveis:
        if col in config_colunas and config_colunas[col].get('multi_moeda') and suporta_moeda:
            nome_com_sufixo = f"{col}{sufixo}"
            colunas_reais.append(nome_com_sufixo)
            mapeamento_sufixos[nome_com_sufixo] = col
        else:
            colunas_reais.append(col)

    # Corta o dataframe para conter apenas as colunas resolvidas que existem de fato
    df_exibicao = df[[c for c in colunas_reais if c in df.columns]].copy()
    # --------------------------------------------------------------------------
    # ⚙️ 3. MAPEAMENTO DE CONFIGURAÇÕES NATIVAS DO STREAMLIT & STYLER
    # --------------------------------------------------------------------------
    st_column_config = {}
    formatadores_pandas = {}

    for col_real in df_exibicao.columns:        
        col_base = mapeamento_sufixos.get(col_real, col_real)
        cfg = config_colunas.get(col_base, {})
        titulo = cfg.get("titulo", col_real)
        tipo = cfg.get("tipo", "text")
        precisao = cfg.get("precisao", 2)

        if tipo == "date":
            pass
            # 1. Se o formato esperado for no padrão brasileiro, priorizamos o dia (dayfirst=True)
            # Isso evita inverter dia e mês em "01/03/2023", mas NÃO quebra se vier ISO "2023-05-02"
            is_br = str(formato_data_input).upper() == "BR"
            df_exibicao[col_real] = pd.to_datetime(df_exibicao[col_real], 
                                                    dayfirst=is_br,
                                                    errors='coerce')
            
            st_column_config[col_real] = st.column_config.DateColumn(titulo,format="DD/MM/YYYY")

        elif tipo == "number":
            df_exibicao[col_real] = pd.to_numeric(df_exibicao[col_real], errors='coerce')
            st_column_config[col_real] = st.column_config.NumberColumn(titulo)
            # 💡 Remove zeros à direita e a vírgula/ponto residual se o número for inteiro
            if int(precisao) != 0:
                formatadores_pandas[col_real] = lambda x, p=int(precisao): ( f"{x:,.{p}f}".rstrip('0').rstrip('.') if pd.notnull(x) else "🔹" )
            else:
                formatadores_pandas[col_real] = lambda x, p=int(precisao): ( f"{x:,.{p}f}" if pd.notnull(x) else "🔹" )

        elif tipo == "currency":
            df_exibicao[col_real] = pd.to_numeric(df_exibicao[col_real], errors='coerce')
            st_column_config[col_real] = st.column_config.NumberColumn(titulo)
            simbolo = simbolo_moeda if cfg.get('multi_moeda') else cfg.get('simbolo_fixo', '')

            # 💡 Se for moeda e quiser manter no mínimo 2 casas mas limpar zeros excedentes acima de 2 (ex: cotações/cripto):
            formatadores_pandas[col_real] = lambda x, p=int(precisao), s=simbolo: (f"{s} {x:,.{p}f}" if pd.notnull(x) else "🔹")

        elif tipo == "percent":
                    df_exibicao[col_real] = pd.to_numeric(df_exibicao[col_real], errors='coerce')
                    st_column_config[col_real] = st.column_config.NumberColumn(titulo)
                    formatadores_pandas[col_real] = "{:," + f".{precisao}%" + "}" 

        elif tipo == "hide":            
            st_column_config[col_real] = None

        else:
            st_column_config[col_real] = st.column_config.TextColumn(titulo)

    # --------------------------------------------------------------------------
    # 🚀 4. RENDERIZAÇÃO: MODO INTERATIVO OU MODO CÓPIA (EXCEL PT-BR)
    # --------------------------------------------------------------------------      
    # Se NÃO suporta edição NEM deleção, desativamos o checkbox de seleção da tabela
    permite_selecao = "multi-row" if tem_botoes else "none"

    if modo_copy:
        df_copy = df_exibicao.copy()
        
        # Remove colunas estruturais brutas para limpar a área de transferência
        colunas_limpar = []
        
        # Formata os dados virando string estrita no padrão regional brasileiro (PT-BR)
        for col_real in df_copy.columns:
            col_base = mapeamento_sufixos.get(col_real, col_real)
            cfg = config_colunas.get(col_base, {})
            tipo = cfg.get("tipo", "text")
            precisao = cfg.get("precisao", 2)
            
            if tipo == "date":
                # Assume a existência da sua função global 'formatar_data_segura'
                df_copy[col_real] = df_copy[col_real].map(
                    lambda x: formatar_data_segura(x).strftime('%d/%m/%Y') if pd.notnull(x) else "🔹"
                )
            elif tipo == "currency":
                simbolo = simbolo_moeda if cfg.get('multi_moeda') else cfg.get('simbolo_fixo', 'R$')
                df_copy[col_real] = df_copy[col_real].map(
                    lambda x, p=int(precisao): f"{simbolo} {x:,.{p}f}".replace(",", "X").replace(".", ",").replace("X", ".") 
                    if pd.notnull(x) else "🔹"
                )
            elif tipo == "number":
                df_copy[col_real] = df_copy[col_real].map(
                    lambda x, p=int(precisao): f"{x:,.{p}f}".replace(",", "X").replace(".", ",").replace("X", ".") 
                    if pd.notnull(x) else "🔹"
                )
            elif tipo == "percent":
                df_copy[col_real] = df_copy[col_real].map(
                    lambda x, p=int(precisao): f"{x:,.{p}%}".replace(",", "X").replace(".", ",").replace("X", ".") 
                    if pd.notnull(x) else "🔹"
                )

            elif tipo =="hide":
                colunas_limpar.append(col_real)
        
        df_copy = df_copy.drop(columns=[c for c in colunas_limpar if c in df_copy.columns])
        
        # Renomeia os cabeçalhos das colunas para os títulos limpos com emojis
        titulos_copia = {}
        for c in df_copy.columns:
            c_base = mapeamento_sufixos.get(c, c)
            titulos_copia[c] = config_colunas.get(c_base, {}).get("titulo", c)
        df_copy = df_copy.rename(columns=titulos_copia)
        
        # Converte em String usando TABULAÇÃO (\t), que o Excel separa perfeitamente em células
        texto_copia = df_copy.to_csv(sep="\t", index=False)
        
        st.info("📋 Clique no botão de cópia à direita do bloco e cole direto na sua planilha:")
        st.code(texto_copia, language="text")
        sl_row = {}
    else:
        df_style = df_exibicao.style.format(formatadores_pandas, decimal=',', thousands='.', na_rep='🔹')
        
        # 🎨 CONFIGURAÇÃO DO ESTILO 100% GENÉRICA:
        if callback_estilo is not None:
            try:
                # O Pandas permite passar argumentos extras para o seu callback usando 'kwargs'
                # Passamos a lista original de 'dados' para que o callback use se quiser!
                df_style = df_style.apply(callback_estilo, axis=None, dados_originais=dados)
            except Exception as e:
                st.error(f"Erro ao aplicar estilo na tabela: {e}")

        sl_row = st.dataframe(
                                df_style,
                                column_config=st_column_config,
                                hide_index=True,
                                width="stretch",
                                # 🔧 CORREÇÃO AQUI: Mudamos de None para "ignore" quando não houver seleção
                                on_select="rerun" if permite_selecao != "none" else "ignore",
                                selection_mode=permite_selecao
                            )

    # --------------------------------------------------------------------------
    # ✏️ 5. BOTÕES DE AÇÃO CONDICIONAIS
    # --------------------------------------------------------------------------
    if ( permite_selecao != "none" and "selection" in sl_row and "rows" in sl_row["selection"] and len(sl_row["selection"]["rows"]) > 0):
        indices_selecionados = sl_row["selection"]["rows"]
        registros_selecionados = [dados[i] for i in indices_selecionados]
        qtd_selecionados = len(registros_selecionados)

        for idx_botao, btn in enumerate(lista_botoes):
            callback = btn.get("callback")
            if not callback:
                continue

            somente_unico = btn.get("somente_unico", False)

            # Se a ação exige seleção única e há mais de um item selecionado, oculta o botão
            if somente_unico and qtd_selecionados != 1:
                continue

            icone = btn.get("icone", "")
            label = btn.get("label", "")
            label_final = f"{icone} {label}".strip() if label else icone
            help_text = btn.get("help", label or "Ação")

            # Se 'somente_unico' for True, envia o item isolado (registro); se False, envia a lista (registros)
            kwargs_callback = {"registro": registros_selecionados[0]} if somente_unico else {"registros": registros_selecionados}
            
            key_botao = f"btn_tbl_{idx_botao}_{chave_tabela}"

            # Renderiza o botão no container correspondente
            containers_botoes[idx_botao].button(
                label_final,
                on_click=callback,
                kwargs=kwargs_callback,
                help=help_text,
                key=key_botao,
                width="stretch",
            )

def st_number_input_custom(label, value=None, key=None, placeholder="0,00", disabled=False ,help=None, on_change=None):
    """Componente numérico pt-BR com formatação automática ao mudar o valor (on_change).

    Gerencia o estado via st.session_state para formatar dinamicamente o texto
    exibido para o padrão "1.234,56" e retorna o valor numérico (float).
    """
    # Callback executada imediatamente quando o usuário altera o campo
    def alterar():
        valor_atual = st.session_state[key]
        st.session_state[key] = formatar_numero_para_br_str(valor_atual)
            
        entrada = st.session_state[key]
        valor_numerico = converter_para_float(entrada)
        st.session_state[f"{key}_return"] = valor_numerico
        if entrada and valor_numerico is None:
            st.session_state[key] = "0,00"
            st.toast("⚠️ Inválido (ex: 1.250,50).")
            st.session_state[f"{key}_return"] = 0
        else:
            if on_change:
                on_change()
            
    # Inicializa a chave no session_state apenas na primeira execução
    if not key:
        key = f"input_custom_{label}"

    if f"{key}_return" not in st.session_state:
        st.session_state[f"{key}_return"] = 0.0
        
    if key not in st.session_state:
        st.session_state[key] = formatar_numero_para_br_str(value)
        alterar()

    
    st.text_input(label, key=key, placeholder=placeholder, disabled=disabled, on_change=alterar, help=help)    
    return st.session_state[f"{key}_return"]

def componente_buscador_ativo(state_dict: dict, sub_chave_destino: str | None = None, sufixo_key: str | None = None, titulo: str | None = None,
                                sub_chave_dados: str | None = None ):
    """
    Componente global de Popover + Pills para busca de ativos na API.
    
    :param state_dict: O dicionário de estado da página (ex: st.session_state['page_movimentacao'])
    :param sub_chave_destino: A string da chave dentro do state onde o ID do ativo será salvo (ex: 'ativo_original')
    :param sufixo_key: Um sufixo único para os widgets não conflitarem (ex: 'o', 'ordens', 'aportes')
    """
    chave_destino = sub_chave_destino or sufixo_key
    sufixo_final = sufixo_key or sub_chave_destino

    if not chave_destino or not sufixo_final:
        raise ValueError("Informe ao menos 'sub_chave_destino' ou 'sufixo_key'.")
    
    # Definição explícita ou automática da chave onde o dicionário completo da API será armazenado
    chave_dados = sub_chave_dados or f"dados_{chave_destino}"

    # Define chaves únicas para os widgets baseadas no sufixo passado
    input_key = f'busca_ativo_{sufixo_key}'
    pills_key = f'sl_ativo_{sufixo_key}'
    sugestoes_key = f'lista_sugeridos_{sufixo_key}'

    # Armazena os dicionários completos retornados pela API
    objetos_sugeridos_key = f'lista_objetos_sugeridos_{sufixo_key}' 

    if sugestoes_key not in st.session_state:
        st.session_state[sugestoes_key] = []
    if objetos_sugeridos_key not in st.session_state:
        st.session_state[objetos_sugeridos_key] = []
   # Garante inicialização das chaves
    if chave_destino not in state_dict or state_dict[chave_destino] is None:
        state_dict[chave_destino] = "Selecionar Ativo"
    if chave_dados not in state_dict:
        state_dict[chave_dados] = None


    # ⚙️ Callbacks internos
    def _buscar_ativos_callback():
        termo_busca = st.session_state.get(input_key, "")

        if not termo_busca:
            st.session_state[sugestoes_key] = []
            st.session_state[objetos_sugeridos_key] = []
            return

        try:
            dados_api = pesquisar_ativos_api(termo_busca, limite=5)

            # Salva os dicionários completos
            st.session_state[objetos_sugeridos_key] = dados_api
            # Salva apenas os rótulos (ativo_cat) para exibir no st.pills
            st.session_state[sugestoes_key] = [ item.get("ativo_cat", item.get("ticker", "")) for item in dados_api]
        except Exception as e:
            # Em componentes com autocompletar, em caso de erro exibimos um toast discreto
            st.toast( f"❌ Erro ao buscar ativos: {str(e)}", )
            st.session_state[sugestoes_key] = []
            st.session_state[objetos_sugeridos_key] = []

    def _definir_ativo_callback():
        ativo_escolhido = st.session_state.get(pills_key)
        if ativo_escolhido:
            state_dict[chave_destino] = ativo_escolhido
                        
            # 🎯 Localiza o dicionário completo do ativo selecionado
            lista_objetos = st.session_state.get(objetos_sugeridos_key, [])
            dict_completo = next( (item for item in lista_objetos if item.get('ativo_cat') == ativo_escolhido), {} )
            
            # Salva o dicionário completo no estado
            state_dict[chave_dados] = dict_completo
            
            if 'carregar_tudo' in state_dict:
                state_dict['carregar_tudo'] = False
        else:
            state_dict[chave_destino] = "Selecionar Ativo"
            state_dict[chave_dados] = None

    if titulo:
        st.markdown(f"<div style='padding-top: 0px;'><p style='font-size: 13.1px; margin-bottom: 0.4rem; padding-top: 0px;'>{titulo}</p></div>", unsafe_allow_html=True)
    # 🏢 Renderização do Componente Visual
    if state_dict.get(chave_destino, "Selecionar Ativo") == None:
        state_dict[chave_destino] = "Selecionar Ativo"
        
    label_popover = formatar_ativo_visual(state_dict.get(chave_destino, "Selecionar Ativo"))

    with st.popover(label_popover, width='stretch'):
        st.text_input( "Buscar Ativo",  key=input_key,  on_change=_buscar_ativos_callback )  
        
        st.pills( "Selecionar",  key=pills_key,  options=st.session_state[sugestoes_key], 
            selection_mode='single',  on_change=_definir_ativo_callback, format_func=formatar_ativo_visual)

def componente_seletor_categorias(dados_categorias: Union[List[str], List[dict], object],
    chave_session: str = "Key_SL_Cat",
    label: str = "Categorias",
    callback_sl= None
) -> List[str]:
    """Componente reutilizável para seleção múltipla de categorias em UPPERCASE.

    MANTÉM A ORDEM: AÇÕES, FII, STOCK, REIT, ETF-US, BDR e o restante alfabético.

    :param dados_categorias: Pode ser uma lista de strings, lista de dicts (ex:
    [{'categoria': 'FII'}]), ou um DataFrame contendo a coluna 'categoria'.
    :param chave_session: Chave única do session_state para evitar conflitos de
    widgets.
    :param label: Rótulo opcional para o campo (útil para acessibilidade/help).
    :return: Lista das categorias selecionadas.
    """
    ORDEM_PRIORITARIA = ["AÇÕES", "FII", "BDR", "ETF", "STOCK", "REIT", "ETF-US"]

    # 1. Extração genérica para lista de strings simples (Sem depender de Pandas)
    brutas = []

    if isinstance(dados_categorias, list):
        for item in dados_categorias:
            if isinstance(item, str):
                brutas.append(item)
            elif isinstance(item, dict) and "categoria" in item:
                brutas.append(item["categoria"])
    elif hasattr(dados_categorias, "columns") and "categoria" in dados_categorias.columns:  # Suporte a DataFrame se fornecido
        brutas = dados_categorias["categoria"].dropna().tolist()

    # 2. Padronização em UPPERCASE + tratamento de duplicatas
    categorias_brutas = [
        str(c).strip().upper() for c in brutas if c and str(c).strip()
    ]

    # Remove duplicatas preservando a primeira ocorrência
    categorias_unicas = list(dict.fromkeys(categorias_brutas))

    # 3. Ordenação Inteligente (Prioritárias + Restante ordenado)
    prioritarias_presentes = [
        c for c in ORDEM_PRIORITARIA if c in categorias_unicas
    ]
    outras_categorias = sorted(
        [c for c in categorias_unicas if c not in ORDEM_PRIORITARIA]
    )

    lista_opcoes = prioritarias_presentes + outras_categorias

    # 4. Callbacks de ação rápida
    def _selecionar_tudo():
        st.session_state[chave_session] = lista_opcoes

    def _desmarcar_tudo():
        st.session_state[chave_session] = []

    # 5. Inicialização da Session State
    if chave_session not in st.session_state:
        st.session_state[chave_session] = lista_opcoes

    # 6. Interface Visual
    with st.container(horizontal=True, horizontal_alignment="left"):
        st.button(
            "",
            icon=":material/checklist_rtl:",
            type="tertiary",
            help="Selecionar tudo",
            key=f"btn_select_all_{chave_session}",
            on_click=_selecionar_tudo,
        )
        st.button(
            "",
            icon=":material/cancel:",
            type="tertiary",
            help="Desmarcar tudo",
            key=f"btn_clear_all_{chave_session}",
            on_click=_desmarcar_tudo,
        )
        categorias_selecionadas = st.pills(
            label=label,
            options=lista_opcoes,
            key=chave_session,
            selection_mode="multi",
            label_visibility="collapsed",
            on_change=callback_sl
        )

    return categorias_selecionadas or []