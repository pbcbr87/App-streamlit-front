import json
import streamlit as st
import pandas as pd
from typing import Any, Callable, Dict, List, Optional
from Pages.utils.components import componente_buscador_ativo, st_number_input_custom, exibir_tabela_generica
from Pages.utils.ferramentas import formatar_data_segura, dividir_id_ativo, limpar_nans_dict, formatar_ativo_visual
from Pages.utils.request_api import executar_requisicao_simular_evento, executar_requisicao_edit_movimentacoes, executar_requisicao_insert_ordens, ApiRequestError
from Pages.utils.flowcharts import renderizar_fluxograma_evento
from datetime import date, datetime


def _exibir_erro_api(contexto: str, erro: Exception) -> None:
    """Exibe mensagens de erro padronizadas para falhas de API e validação."""
    if isinstance(erro, ApiRequestError):

        mensagem = getattr(erro, "message", str(erro))
        payload = getattr(erro, "payload", {}) or {}

        if isinstance(payload, dict):
            detalhe = payload.get("detail")
            if isinstance(detalhe, dict):
                mensagem = detalhe.get("message") or detalhe.get("detail") or mensagem
            elif isinstance(detalhe, str) and detalhe:
                mensagem = detalhe

        st.error(f"❌ {contexto}: {mensagem}")
        return

    st.error(f"❌ {contexto}: {str(erro)}")


# ==============================================================================
# 🗺️ MAPPERS OFICIAIS ISOLADOS (Evita qualquer colisão entre Ativo e Caixa)
# ==============================================================================
MAP_PROPORCAO = {
    "Proporção do Custo (%)": "proporcao_custo",
    "Valor Financeiro Bruto": "custo_delta"
    }

MAP_QTD = {
    "Fator de Conversão (%)": "qtd_fator_delta",
    "Quantidade Líquida": "qtd_delta"
    }

MAP_CUSTO_FILHO = {
    "Valor por cota Ativo Gerado": "valor_cota_op",
    "Valor por cota Ativo Original (Mãe)": "valor_cota_com",
    "Valor Financeiro Bruto": "valor"
    }

MAP_RECEBIMENTO_CAIXA = {
    "Valor por cota Ativo Original (Mãe)": "valor_caixa_cota_com",
    "Valor Bruto Recebido": "valor_caixa"
    }

MAP_REVERSO_LABELS = {
    # --- Chaves de Custo / Proporção ---
    "proporcao_custo": "Proporção do Custo (%)",
    "custo_delta": "Valor Financeiro Bruto",
    "valor": "Valor Financeiro Bruto",
    
    # --- Chaves de Quantidade ---
    "qtd_fator_delta": "Fator de Conversão (%)",
    "qtd_delta": "Quantidade Líquida",
    
    # --- Chaves de Custo Específicas (Filho) ---
    "valor_cota_op": "Valor por cota Ativo Gerado",
    "valor_cota_com": "Valor por cota Ativo Original (Mãe)",
    
    # --- Chaves de Caixa / Recebimento ---
    "valor_caixa_cota_com": "Valor por cota Ativo Original (Mãe)", 
    "valor_caixa": "Valor Bruto Recebido"
    }

# ==============================================================================
# 🗺️ Parametros exibir tabela
# ==============================================================================

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

CONFIG_MOVIMENTACOES = {
    "id":               {"titulo":"id", "tipo": "hide"},
    "fk_ativo_visual":  {"titulo": "🏷️ Ativo", "tipo": "text", "funcao_map": lambda row: formatar_ativo_visual(row.get("fk_ativo"))},
    "data_op_pag":      {"titulo": "📅 Data Op", "tipo": "date"},
    "tipo":             {"titulo": "⚡ Tipo", "tipo": "text", "funcao_map": adicionar_badge_tipo},
    "quant_":           {"titulo": "📊 Qtd", "tipo": "number", "precisao": 6},
    "quant_acum":       {"titulo": "📈 Acum", "tipo": "number", "precisao": 6},
    "quant_fracao":     {"titulo": "🧩 Frac", "tipo": "number", "precisao": 6},
    "preco_contabil":   {"titulo": "📐 Delta Custo", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "valor_financeiro": {"titulo": "💰 Valor Op", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "custo_acum":       {"titulo": "🛡️ Custo Acum", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "lucro":            {"titulo": "🏆 Lucro", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "rend_trib_excl":   {"titulo": "🏛️ Rend Trib", "tipo": "currency", "multi_moeda": True, "precisao": 2},
    "seq":              {"titulo": "🔢 Seq", "tipo": "number", "precisao": 0},
    "dolar_bc":         {"titulo": "💵 Dólar BC", "tipo": "currency", "multi_moeda": False, "precisao": 4}
}

COLUNAS_RESUMIDAS = ["fk_ativo_visual", "data_op_pag", "tipo", "quant_","quant_acum", "preco_contabil","custo_acum"]

# ==============================================================================
# 🎛️ GERENCIADOR CENTRAL DE LAYOUT
# ==============================================================================
def renderizar_layout_edit_ordem(registro_selecionado: dict = None,     
                                 on_sucesso=None, 
                                 key_estado_dinamico="form_default", 
                                 eh_insercao: bool = False) -> dict:
    """
    Componente reativo para Edição ou Inserção Manual de Ordens de Compra/Venda.
    
    :param registro_selecionado: Dict com a movimentação (se None, assume formulário em branco).
    :param on_sucesso: Callback de retorno para atualizar a tela principal.
    :param key_estado_dinamico: Chave isolada para controlar o estado no session_state.
    :param eh_insercao: Se True, faz POST /insert_ordem. Se False, faz PUT /editar/{id}.
    """

    reg_selecionado = registro_selecionado or {}
    mov_id = reg_selecionado.get("movimentacao_id")
    dados_origem = reg_selecionado.get("dados_origem", {})
    
    map_cv_tela = {"C": "Compra", "V": "Venda"}
    map_tela_cv = {"Compra": "C", "Venda": "V"}

    # 🔄 Inicialização do estado dinâmico isolado
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]

    # 📥 Inicializa o estado com o ID bruto unificado (ex: "PETR4_AÇÕES")
    if 'ativo_ordem' not in state:
        ativo_salvo = dados_origem.get("codigo_ativo", "")
        cat_salva = dados_origem.get("categoria", "")
        if cat_salva and ativo_salvo:
            state['ativo_ordem'] = f"{ativo_salvo}_{cat_salva}"
        else:
            state['ativo_ordem'] = "Selecionar Ativo"
    col_input, preview = st.columns([3, 2])
    input_form = col_input.container(border=True)
    
    # ==========================================
    # ETAPA 1: FORMULÁRIO
    # ==========================================
    def_data = formatar_data_segura(dados_origem.get("data_operacao")) or date.today()

    # Se for inserção manual, inicia com zerado/limpo em vez de tentar ler do dict vazio
    val_quant_default = "0,00" if eh_insercao else f"{dados_origem.get('quant', 0.0) or 0.0}".replace(".", ",")
    val_custo_default = "0,00" if eh_insercao else f"{dados_origem.get('custo_operacao', 0.0) or 0.0}".replace(".", ",")
    val_taxas_default = "0,00" if eh_insercao else f"{dados_origem.get('taxas', 0.0) or 0.0}".replace(".", ",")

    # ==========================================
    # ETAPA 2: GRID DE INPUTS
    # ==========================================
    g1, g2, g3 = input_form.columns(3)
    
    with g1:
        componente_buscador_ativo(state, 'ativo_ordem', sufixo_key=f'red_orig_{key_estado_dinamico}', titulo="🏷️ Ativo:")
        id_ativo_atual = state.get('ativo_ordem', "")
        codigo_ativo, categoria_ativo = dividir_id_ativo(id_ativo_atual)

    with g2:
        def_c_v_label = map_cv_tela.get(dados_origem.get("c_v", "C"), "Compra")
        opcao_selecionada = st.selectbox("⚡ Operação", 
                                         options=["Compra", "Venda"], 
                                         index=0 if def_c_v_label == "Compra" else 1, 
                                         key=f"sel_cv_{key_estado_dinamico}")
        c_v_salvar = map_tela_cv[opcao_selecionada] 

    with g3:
        data_operacao = st.date_input("📅 Data Operação", 
                                      max_value="today", 
                                      value=def_data, format="DD/MM/YYYY",
                                      key=f"data_op_{key_estado_dinamico}")
        
    g4, g5, g6 = input_form.columns(3)
    with g4:
        quant = st_number_input_custom("📊 Quantidade", value=val_quant_default, key=f"num_q_{key_estado_dinamico}")
    with g5:
        custo_operacao = st_number_input_custom("💰 Custo Total (Bruto)", value=val_custo_default, key=f"num_c_{key_estado_dinamico}")
    with g6:
        taxas = st_number_input_custom("🏛️ Taxas / Emolumentos", value=val_taxas_default, key=f"num_t_{key_estado_dinamico}")
    
    f1, f2 = input_form.columns(2)
    corretora = f1.text_input("🏢 Corretora", value=dados_origem.get("corretora", ""), key=f"txt_corr_{key_estado_dinamico}")

    comentario_origem = dados_origem.get("comentario")
    comentario_def = "" if comentario_origem is None else comentario_origem
    comentario = f2.text_area("📝 Notas da Operação", 
                              value=comentario_def, 
                              height=65, 
                              key=f"txt_com_{key_estado_dinamico}", 
                              placeholder="Digite seus comentários ou notas pessoais")

    v_quant = float(str(quant).replace(",", ".")) if isinstance(quant, str) else float(quant or 0)
    v_custo = float(str(custo_operacao).replace(",", ".")) if isinstance(custo_operacao, str) else float(custo_operacao or 0)
    v_taxas = float(str(taxas).replace(",", ".")) if isinstance(taxas, str) else float(taxas or 0)
    data_formatada_api = formatar_data_segura(data_operacao)

    payload_ordem = {
        "movimentacao_origem_id": mov_id,
        "data_operacao": data_formatada_api,
        "categoria": categoria_ativo,
        "codigo_ativo": codigo_ativo,
        "c_v": c_v_salvar,
        "quant": v_quant,
        "custo_operacao": v_custo,
        "taxas": v_taxas,
        "corretora": corretora.strip().upper() if corretora else "",
        "comentario": comentario,
        "modo_insert": "MANUAL INSERT" if eh_insercao else "MANUAL EDIT"
    }
    # ==========================================
    # ETAPA 3: REGRAS DE VALIDAÇÃO
    # ==========================================
    ativo_valido = bool(codigo_ativo and codigo_ativo != "Selecionar Ativo")
    quant_valida = v_quant > 0
    custo_valido = v_custo > 0
    corretora_valida = bool(corretora and corretora.strip())

    dados_validos = ativo_valido and quant_valida and custo_valido

    # ==========================================
    # ETAPA 4: PREVIEW REATIVO & AÇÕES
    # ==========================================
    if ativo_valido:        
        with preview.container(border=True):
            st.markdown("#### 🔍 Resumo da Ordem")
            c_badge = "🟢 COMPRA" if payload_ordem["c_v"] == "C" else "🔴 VENDA"
            
            # Cabeçalho com destaque discreto
            st.markdown(f"##### {c_badge} | {payload_ordem['codigo_ativo']}")
            st.caption(f"Categoria: {payload_ordem['categoria']} | Corretora: {corretora if corretora_valida else '-'}")
            
            # Tratamento da Data
            if isinstance(data_operacao, (date, datetime)):
                data_formatada_preview = data_operacao.strftime("%d/%m/%Y")
            else:
                data_formatada_preview = str(formatar_data_segura(payload_ordem["data_operacao"], formato_saida="%d/%m/%Y"))
            
            # 🧮 CÁLCULOS ADICIONAIS (Apenas para Visualização)
            v_total_sem_taxas = max(0.0, payload_ordem["custo_operacao"] - payload_ordem["taxas"])
            v_unitario_sem_taxas = (v_total_sem_taxas / payload_ordem["quant"]) if payload_ordem["quant"] > 0 else 0.0

            # Formatação de Strings
            str_qtd = f"{payload_ordem['quant']:,.6}".rstrip('0').rstrip('.').replace(",", "X").replace(".", ",").replace("X", ".")
            str_total = f"R$ {payload_ordem['custo_operacao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            str_taxas = f"R$ {payload_ordem['taxas']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            str_sem_taxas = f"R$ {v_total_sem_taxas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            str_unitario = f"R$ {v_unitario_sem_taxas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            # GRID COMPACTO EM HTML/CSS (Expandido para 3 linhas)
            html_preview = f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 5px; margin-bottom: 5px;">
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">📅 Data</small>
                    <strong style="font-size: 1.05rem;">{data_formatada_preview}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">📊 Qtd</small>
                    <strong style="font-size: 1.05rem;">{str_qtd}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">💰 Total Bruto</small>
                    <strong style="font-size: 1.05rem;">{str_total}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.08); padding: 8px; border-radius: 6px;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">🏛️ Taxas</small>
                    <strong style="font-size: 1.05rem;">{str_taxas}</strong>
                </div>
                <!-- 🆕 Novos campos calculados na terceira linha -->
                <div style="background-color: rgba(128, 128, 128, 0.12); padding: 8px; border-radius: 6px; border-left: 3px solid #2ecc71;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">💵 Total (Sem Taxa)</small>
                    <strong style="font-size: 1.05rem; color: #2ecc71;">{str_sem_taxas}</strong>
                </div>
                <div style="background-color: rgba(128, 128, 128, 0.12); padding: 8px; border-radius: 6px; border-left: 3px solid #3498db;">
                    <small style="color: gray; display: block; margin-bottom: 2px;">🏷️ Unitário (Sem Taxa)</small>
                    <strong style="font-size: 1.05rem; color: #3498db;">{str_unitario}</strong>
                </div>
            </div>
            """
            st.markdown(html_preview, unsafe_allow_html=True)

        if dados_validos:
            concordou = preview.checkbox("Os dados estão corretos", key=f"chk_agree_{key_estado_dinamico}")

            btn_label = "🚀 Inserir Ordem" if eh_insercao else "💾 Confirmar e Salvar"
            
            if preview.button(btn_label, type="primary", width='stretch', key=f"btn_salvar_ord_{key_estado_dinamico}", disabled=not concordou):
                with st.spinner("Enviando para o servidor..."):
                    try:
                        payload_salvar = {
                                            "data_operacao": data_formatada_api.strftime("%Y-%m-%d") if isinstance(data_formatada_api, (date, datetime)) else data_formatada_api,
                                            "categoria": categoria_ativo,
                                            "codigo_ativo": codigo_ativo,
                                            "c_v": c_v_salvar,
                                            "quant": v_quant,
                                            "custo_operacao": v_custo,
                                            "taxas": v_taxas,
                                            "corretora": corretora.strip().upper(),
                                            "comentario": comentario,
                                            "modo_insert": "MANUAL INSERT" if eh_insercao else dados_origem.get("modo_insert", "MANUAL EDIT")
                                        }
                        sucesso = False  
                        if eh_insercao:
                            # 🟢 INSERÇÃO: Pacote de 1 ordem -> POST /movimentacoes/insert_ordem
                            payload_envio = {"dados": [payload_salvar]}
                            sucesso = executar_requisicao_insert_ordens(payload=payload_envio, modo_insert="MANUAL")
                        else:
                            # 🔵 EDIÇÃO: Edição de 1 registro -> PUT /movimentacoes/editar/{id}
                            id_mov = payload_ordem.get("movimentacao_origem_id")                           
                            sucesso = executar_requisicao_edit_movimentacoes(mov_id=id_mov, payload=payload_salvar)

                        if sucesso:
                            if key_estado_dinamico in st.session_state:
                                del st.session_state[key_estado_dinamico]

                            st.session_state["toast_pendente"] = {
                                                                "mensagem": "✅ Operação realizada com sucesso!",
                                                                "icone": "🎉",
                                                                }
                            if on_sucesso: on_sucesso()
                            st.rerun()
                        else:
                            st.warning("⚠️ A operação não retornou sucesso do servidor. Tente novamente.")

                    except ApiRequestError as e:
                        _exibir_erro_api("Falha ao salvar a movimentação", e)
                    except ValueError as e:
                        _exibir_erro_api("Dados inválidos para salvar a movimentação", e)
                    except Exception as e:
                        _exibir_erro_api("Erro inesperado ao salvar a movimentação", e)
        else:
            erros = []
            if not quant_valida: erros.append("Qtd > 0")
            if not custo_valido: erros.append("Total > 0")
            if not corretora_valida: erros.append("Corretora vazia")
            
            preview.warning(f"⚠️ **Pendente:** {', '.join(erros)}.")
    else:
        preview.info("💡 Selecione um ativo válido para exibir o resumo e habilitar o salvamento.")

    return payload_ordem


def renderizar_layout_edit_evento(registro_selecionado: dict = None, on_sucesso=None, key_estado_dinamico="form_default",
                                  origin_config: dict | None = None) -> dict:
    """
    Componente PURO de Layout com Live Preview Lado a Lado e Alternância de Estados.
    Parâmetros:
    - registro_selecionado: dict com 'dados_origem' e possivelmente 'movimentacao_id'.
    - on_sucesso: callback executado após gravação bem-sucedida.
    - key_estado_dinamico: chave isolada no session_state para formular várias instâncias.
    - origin_config: dicionário com configuração mínima:
        - callback_request_api: callable(payload: dict) -> truthy em caso de sucesso.
                    Use lambda para vincular argumentos extras (ex: mov_id, evento_id).
        - label_btn_gravar: str (opcional) -> rótulo do botão de gravação
        - modo_insert: str (opcional) -> valor para payload['modo_insert']
    """
    reg_selecionado = registro_selecionado or {}
    mov_id = reg_selecionado.get("movimentacao_id")
    dados_origem = reg_selecionado.get("dados_origem", {})

    origin_config = origin_config or {}

    callback_request_api = origin_config.get("callback_request_api")
    override_label = origin_config.get("label_btn_gravar")
    override_modo_insert = origin_config.get("modo_insert")

    

    key_simulacao = f"simulacao_state_{key_estado_dinamico}"
    if key_simulacao not in st.session_state:
        st.session_state[key_simulacao] = None

    dados_simulados = st.session_state[key_simulacao]
    tem_dados_simulados = dados_simulados is not None
    # ==========================================
    # ETAPA 2: APENAS MOSTRAR O RESULTADO DA SIMULAÇÃO
    # ==========================================
    if tem_dados_simulados:                
        st.subheader("📊 Demonstrativo Detalhado de Lançamentos")
        st.info("💡 Revise os lançamentos abaixo. Se estiver tudo correto, clique em **Gravar na Carteira**.")
        
        r1, r2 = st.columns([3, 2])
        with r1:
            exibir_tabela_generica(
                dados=dados_simulados, 
                config_colunas=CONFIG_MOVIMENTACOES, 
                colunas_resumidas=COLUNAS_RESUMIDAS, 
                callback_edit=None, 
                callback_deletar=None, 
                chave_tabela=f"simulacao_{key_estado_dinamico}", 
                suporta_moeda=True
            )
        with r2.container(border=True):
            st.markdown("### 🔀 Fluxo de Distribuição de Ativos")
            # Recupera o payload estruturado salvo no estado para renderizar o gráfico final
            payload_recente = st.session_state.get(f"last_payload_{key_estado_dinamico}", {})
            renderizar_fluxograma_evento(
                payload_recente.get("tipo_evento"), 
                payload_recente, 
                resultado=dados_simulados
            )
            
        st.success("🚀 Cenário Simulado com Sucesso!")
        # Grid de Ações do Resultado
        col_voltar, col_salvar = st.columns(2)
        
        with col_voltar:
            if st.button("⬅️ Editar Parâmetros", width='stretch', type="secondary", key=f"btn_voltar_{key_estado_dinamico}"):
                st.session_state[key_simulacao] = None
                st.rerun()
                
        with col_salvar:
            label_btn_gravar = override_label
            botao_salvar = st.button(label_btn_gravar, type="primary", width='stretch', key=f"btn_salvar_{key_estado_dinamico}")
            if botao_salvar:
                payload_simulacao = st.session_state.get(f"last_payload_{key_estado_dinamico}")
                if payload_simulacao:
                                       
                    # 🔧 Traduzindo os campos do front para o Schema do Backend
                    payload_salvar = {                                        
                        "tipo": payload_simulacao.get("tipo_evento"),
                        "fk_ativo_base": payload_simulacao.get("fk_ativo_base"),
                        "fk_ativo_gerado": payload_simulacao.get("fk_ativo_gerado"),
                        "data_aprov": payload_simulacao.get("data_aprov"),
                        "data_com": payload_simulacao.get("data_com"),
                        "data_pag": payload_simulacao.get("data_pag"),
                        "instrucoes": payload_simulacao.get("instrucoes"),
                        "modo_insert": override_modo_insert
                    }                                
                    with st.spinner("Gravando alterações..."):
                        try:
                            if not callable(callback_request_api):
                                raise ValueError("É necessário fornecer origin_config['callback_request_api'] como callable.")

                            # Contrato único: callback(payload) — use lambda para vincular argumentos extras
                            resultado = callback_request_api(payload_salvar)
                            sucesso = bool(resultado)
                            
                            if sucesso:
                                # Limpeza completa dos estados no session_state após o sucesso
                                if key_simulacao in st.session_state:
                                    del st.session_state[key_simulacao]
                                if f"last_payload_{key_estado_dinamico}" in st.session_state:
                                    del st.session_state[f"last_payload_{key_estado_dinamico}"]
                                if key_estado_dinamico in st.session_state:
                                    del st.session_state[key_estado_dinamico]

                                st.session_state["toast_pendente"] = {
                                                                        "mensagem": "✅ Evento gravado com sucesso!",
                                                                        "icone": "🎉",
                                                                    }
                                if on_sucesso: 
                                    on_sucesso()
                                st.rerun()
                            else:
                                st.warning("⚠️ O servidor não confirmou a gravação do evento. Verifique os dados e tente novamente.")

                        except ApiRequestError as e:
                            _exibir_erro_api("Falha ao gravar o evento", e)
                        except ValueError as e:
                            _exibir_erro_api("Dados inválidos para gravar o evento", e)
                        except Exception as e:
                            _exibir_erro_api("Erro inesperado ao gravar o evento", e)
        # Retorna o payload que está em cache
        return st.session_state.get(f"last_payload_{key_estado_dinamico}", {})

    # ==========================================
    # ETAPA 1: CONFIGURAÇÃO / FORMULÁRIO ORIGINAL
    # ==========================================
    custo_acum_manual = None
    quant_acum_manual = None
    
    # Em caso de inserção manual (sem registro selecionado), libera os campos de acumulado manual
    with st.container(horizontal=True): 
        enviar_valores = st.toggle("Simular valores", key=f"tgl_simular_{key_estado_dinamico}")
        if enviar_valores:
            with st.expander("Simular Posição Atual", expanded=True):
                with st.container(horizontal=True): 
                    custo_acum_manual = st_number_input_custom("Custo Atual", key=f"custo_atual_from_edit_{key_estado_dinamico}")
                    quant_acum_manual = st_number_input_custom("Quantidade Atual", key=f"quant_atual_from_edit_{key_estado_dinamico}")

    default_tipo = dados_origem.get("tipo", "CISÃO")
    default_aprov = formatar_data_segura(dados_origem.get("data_aprov"))
    default_com = formatar_data_segura(dados_origem.get("data_com"))
    default_pag = formatar_data_segura(dados_origem.get("data_pag"))

    opcoes_tipos = [
        "CISÃO", "INCORPORAÇÃO", "BONIFICAÇÃO", "GRUPAMENTO", 
        "DESDOBRAMENTO", "GRUPAMENTO_DESDOBRAMENTO", "ATUALIZAÇÃO", 
        "OPA", "REDUÇÃO DE CAPITAL", "FRAÇÃO"
    ]
    try:
        index_tipo = opcoes_tipos.index(default_tipo)
    except ValueError:
        index_tipo = 0

    # 🏢 1. Grid Superior de Datas e Tipo de Evento
    f1, f2, f3, f4 = st.container(border=True).columns(4)
    with f1:
        tipo_evento = st.selectbox("Selecione o Tipo de Evento:", opcoes_tipos, index=index_tipo, key=f"sel_tipo_ev_{key_estado_dinamico}")
    with f2:
        data_aprov = st.date_input("Data Aprov.", value=default_aprov, format="DD/MM/YYYY", key=f"dt_aprov_{key_estado_dinamico}")
    with f3:
        data_com = st.date_input("Data Com.", value=default_com, format="DD/MM/YYYY", key=f"dt_com_{key_estado_dinamico}")
    with f4:
        data_pag = st.date_input("Data Pag.", value=default_pag, format="DD/MM/YYYY", key=f"dt_pag_{key_estado_dinamico}")

    st.write(" ")

    # 🏢 2. Grid de Edição Dinâmica (Roteador de Formulários)
    c1, c2 = st.columns([3, 2])
    form_state = {}
    
    instrucoes_salvas = []
    if "instrucoes" in dados_origem and dados_origem["instrucoes"]:
        try:
            instrucoes_salvas = json.loads(dados_origem['instrucoes']) if isinstance(dados_origem['instrucoes'], str) else dados_origem['instrucoes']
        except Exception:
            instrucoes_salvas = []

    with c1:
        if tipo_evento in ["CISÃO", "INCORPORAÇÃO"]:
            form_state = renderizar_formulario_cisao_incorporacao(tipo_evento, dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "BONIFICAÇÃO":
            form_state = renderizar_formulario_bonificacao(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento in ["GRUPAMENTO", "DESDOBRAMENTO"]:
            form_state = renderizar_formulario_grupamento_desdobramento(tipo_evento, dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "GRUPAMENTO_DESDOBRAMENTO":
            form_state = renderizar_formulario_grupamento_desdobramento_duplo(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "FRAÇÃO":
            form_state = renderizar_formulario_fracao(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "ATUALIZAÇÃO":
            form_state = renderizar_formulario_atualizacao(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "OPA":
            form_state = renderizar_formulario_opa(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        elif tipo_evento == "REDUÇÃO DE CAPITAL":
            form_state = renderizar_formulario_reducao_capital(dados_origem, instrucoes_salvas, key_estado_dinamico=key_estado_dinamico)
        else:
            st.text(f"Formulário para {tipo_evento} não desenvolvido ainda")
    
    form_state = form_state or {}

    # 🏢 3. Formata e empacota para o Pydantic
    payload_estruturado = {
        "movimentacao_origem_id": mov_id,
        "tipo_evento": tipo_evento,
        "fk_ativo_base": form_state.get("fk_ativo_base"),
        "fk_ativo_gerado": form_state.get("fk_ativo_gerado"),
        "data_aprov": data_aprov.strftime("%Y-%m-%d") if isinstance(data_aprov, (date, datetime)) else data_aprov,
        "data_com": data_com.strftime("%Y-%m-%d") if isinstance(data_com, (date, datetime)) else data_com,
        "data_pag": data_pag.strftime("%Y-%m-%d") if isinstance(data_pag, (date, datetime)) else data_pag,
        "instrucoes": form_state.get("instrucoes", []),
        "quant_acum_manual": quant_acum_manual,
        "custo_acum_manual": custo_acum_manual
    }

    # Live Preview Lado a Lado (Rascunho)
    with c2.container(border=True):
        st.markdown("### 🗺️ Preview do Fluxo Contábil")
        renderizar_fluxograma_evento(tipo_evento, payload_estruturado)

    # Botão de Simulação Único na base do formulário
    if st.button("🧪 Simular Cenário", width='stretch', type="primary", key=f"btn_sim_{key_estado_dinamico}"):
        with st.spinner("Calculando esteira contábil..."):
            try:
                res = executar_requisicao_simular_evento(payload_estruturado)

                if res is None or (isinstance(res, (list, dict)) and not res):
                    st.warning("⚠️ A simulação não retornou resultado válido. Verifique o payload enviado.")
                else:
                    # Salva o resultado e o payload que gerou esse resultado para o próximo ciclo
                    st.session_state[key_simulacao] = res
                    st.session_state[f"last_payload_{key_estado_dinamico}"] = payload_estruturado
                    st.rerun()
            except ApiRequestError as e:
                _exibir_erro_api("Falha ao simular o cenário", e)
            except ValueError as e:
                _exibir_erro_api("Payload inválido para simulação", e)
            except Exception as e:
                _exibir_erro_api("Erro inesperado ao simular o cenário", e)

    return payload_estruturado


def renderizar_layout_importacao_tabela( titulo: str, funcao_envio_api: Callable[[Dict[str, Any]], bool],
    config_colunas: Dict[str, Any], modelos_planilha: Optional[List[Dict[str, str]]] = None,
    config_colunas_erro: Optional[Dict[str, Any]] = None,
    on_sucesso: Optional[Callable[[], None]] = None,
    key_estado_dinamico: str = "form_import_table"
) -> None:
    """
    Layout dinâmico genérico por etapas para importação de dados por tabela (Excel/CSV).
    
    🛠️ Alteração: Função tornada 100% genérica via parâmetros reutilizáveis (eventos, ordens, proventos, etc.).
    
    Args:
        titulo: Título exibido no topo (ex: "📥 Importação de Eventos por Tabela")
        funcao_envio_api: Função responsável por disparar a requisição POST para a API.
        config_colunas: Dicionário com a configuração de colunas para o preview.
        payload_key: Chave do dicionário enviado para a API (ex: "eventos", "ordens").
        modelos_planilha: Lista de dicionários com os arquivos modelo [{'nome': '...', 'path': '...'}]
        config_colunas_erro: Configuração de colunas para exibição na tabela de erros.
        on_sucesso: Callback disparado após conclusão bem-sucedida.
        key_estado_dinamico: Chave única para isolamento dos estados na Session State.
    """
    st.title(titulo)  # 🛠️ Título parametrizado

    # Keys de controle na session_state isoladas por contexto
    key_etapa = f"etapa_{key_estado_dinamico}"
    key_dados = f"dados_{key_estado_dinamico}"
    key_erro = f"erro_{key_estado_dinamico}"

    # Inicializa os estados padrão
    if key_etapa not in st.session_state:
        st.session_state[key_etapa] = "UPLOAD"
    if key_dados not in st.session_state:
        st.session_state[key_dados] = None
    if key_erro not in st.session_state:
        st.session_state[key_erro] = None

    def resetar_importacao() -> None:
        """Helper interno para reiniciar o fluxo de importação."""
        st.session_state[key_etapa] = "UPLOAD"
        st.session_state[key_dados] = None
        st.session_state[key_erro] = None

    # =========================================================================
    # 🔴 ETAPA 3: EXIBIÇÃO EXCLUSIVA DE ERRO
    # =========================================================================
    if st.session_state[key_etapa] == "ERRO":
        renderizar_erro_api(erro_payload=st.session_state[key_erro], config_colunas_erro=config_colunas_erro, chave_estado_dinamico=key_estado_dinamico)

        if st.button("🔄 Corrigir e Tentar Novamente", type="primary", use_container_width=True, key=f"btn_retry_{key_estado_dinamico}"):
            resetar_importacao()
            st.rerun()

    # =========================================================================
    # 🟡 ETAPA 2: PRÉ-VISUALIZAÇÃO E CONFIRMAÇÃO
    # =========================================================================
    elif st.session_state[key_etapa] == "PREVIEW":
        list_dict_registros: List[Dict[str, Any]] = st.session_state[key_dados] or []
        with st.container(border=True):
            st.markdown(f"#### 📊 Aprovação do Pacote ({len(list_dict_registros)} registros)")
            st.caption("Confira os dados importados abaixo antes de processar.")
            exibir_tabela_generica(
                dados=list_dict_registros,
                config_colunas=config_colunas,
                colunas_resumidas=None,
                callback_edit=None,
                callback_deletar=None,
                callback_estilo=None,
                chave_tabela=f"preview_{key_estado_dinamico}",
                suporta_moeda=False
            )
            
            c_chk, c_btn, c_cancel = st.columns([2, 1, 1])
            with c_chk:
                concordou = st.checkbox("Confirmo que os dados estão corretos.", key=f"chk_tbl_{key_estado_dinamico}")
            
            with c_btn:
                btn_processar = st.button(
                    "🚀 Confirmar e Enviar", 
                    type="primary", 
                    use_container_width=True, 
                    disabled=not concordou, 
                    key=f"btn_send_{key_estado_dinamico}"
                )

            with c_cancel:
                if st.button("❌ Cancelar / Novo Arquivo", use_container_width=True, key=f"btn_cancel_{key_estado_dinamico}"):
                    resetar_importacao()
                    st.rerun()

            if btn_processar:
                with st.spinner("Enviando pacote para a API..."):
                    try:
                        # Monta o payload com a chave parametrizada (ex: {"eventos": [...]})
                        payload_envio = {"dados": list_dict_registros}
                        resultado = funcao_envio_api(payload=payload_envio)
                        
                        if resultado:                    
                            st.session_state["toast_pendente"] = {
                                                                "mensagem": f"✅ Pacote com {len(list_dict_registros)} registro(s) enviado com sucesso!",
                                                                "icone": "✅",
                                                                }
                            resetar_importacao()
                            if on_sucesso:
                                on_sucesso()
                            st.rerun()
                        else:
                            st.warning("⚠️ O servidor não confirmou o envio do pacote. Verifique os dados e tente novamente.")

                    except ApiRequestError as err:
                        st.session_state[key_erro] = err.payload if hasattr(err, "payload") and err.payload else {"error_type": "Generic Error", "message": str(err)}
                        st.session_state[key_etapa] = "ERRO"
                        st.rerun()
                    except ValueError as err:
                        _exibir_erro_api("Dados inválidos para importar o pacote", err)
                    except Exception as err:
                        _exibir_erro_api("Erro inesperado ao importar o pacote", err)

    # =========================================================================
    # 🟢 ETAPA 1: UPLOAD E DOWNLOAD DE MODELOS
    # =========================================================================
    else:
        # Se foram fornecidos modelos de planilha para download
        if modelos_planilha:
            with st.container(border=True):
                st.markdown("#### 📂 1. Modelos de Planilha")
                cols = st.columns(len(modelos_planilha))
                
                for idx, modelo in enumerate(modelos_planilha):
                    with cols[idx]:
                        # 🛠️ Suporte dinâmico a múltiplos modelos de arquivo
                        caminho_arquivo = modelo.get("path", "")
                        nome_exibicao = modelo.get("nome", "Modelo (.xlsx)")
                        file_name = modelo.get("file_name", "modelo.xlsx")
                        
                        try:
                            with open(caminho_arquivo, "rb") as file:
                                st.download_button(
                                    label=f"📄 {nome_exibicao}",
                                    data=file,
                                    file_name=file_name,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    icon="📥",
                                    use_container_width=True,
                                    key=f"dl_{idx}_{key_estado_dinamico}"
                                )
                        except FileNotFoundError:
                            st.button(f"📄 {nome_exibicao} (Indisponível)", disabled=True, use_container_width=True)

        with st.container(border=True):
            st.markdown("#### 📤 2. Fazer Upload do Arquivo")
            uploaded_file = st.file_uploader( "Arraste e solte a planilha aqui", type=["xlsx", "xls"], key=f"uploader_{key_estado_dinamico}")

            if uploaded_file is not None:
                try:
                    df_raw = pd.read_excel(uploaded_file)
                    if df_raw.empty:
                        st.error("⚠️ O arquivo enviado está totalmente vazio.")
                    else:
                        dados_sanitizados = limpar_nans_dict(df_raw.to_dict(orient="records"))
                    
                        st.session_state[key_dados] = dados_sanitizados
                        st.session_state[key_etapa] = "PREVIEW"
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Erro ao ler o arquivo Excel: {str(e)}")

#===============================================================================
# Tatar erro tabela
#===============================================================================
def renderizar_erro_api(erro_payload: Any,  config_colunas_erro: Optional[Dict[str, Any]] = None, chave_estado_dinamico: str = "") -> None:
    """
    Componente visual puro para renderizar respostas de erro de API de forma destacada.
    
    Alteração: Generalizado para suportar payloads de 'ordens', 'eventos' ou objetos genéricos.
    """
    with st.container(border=True):
        payload = erro_payload
        if isinstance(payload, dict) and "detail" in payload:
            payload = payload["detail"]

        # CASO 1: Erro de Validação de Pacote (Status 422 customizado do backend)
        if isinstance(payload, dict) and payload.get("error_type") == "Package Validation Error":
            st.error(f"❌ **{payload.get('message', 'Erro ao validar pacote.')}**")
            
            m1, m2, _ = st.columns([2, 2, 6])
            m1.metric("Total no Pacote", payload.get("total_pacote", 0))
            m2.metric("Total Rejeitadas", payload.get("total_rejeitadas", 0), delta_color="inverse")
            
            rejeitadas = payload.get("linhas_rejeitadas", [])
            if rejeitadas:
                st.markdown("##### 🚨 Linhas Rejeitadas:")
                if isinstance(rejeitadas, list) and len(rejeitadas) > 0 and isinstance(rejeitadas[0], dict):
                    
                    linhas_processadas: List[Dict[str, Any]] = []
                    for item in rejeitadas:                       
                        registro = item.get("original", {})
                        
                        if isinstance(registro, str):   
                            try:
                                registro = json.loads(registro)
                            except Exception:
                                registro = {}
                        elif not isinstance(registro, dict):
                            registro = {}

                        # Extrai a lista de motivos de forma limpa
                        motivos_raw = item.get("motivos", [])
                        motivos_texto = ", ".join(motivos_raw) if isinstance(motivos_raw, list) else str(motivos_raw)
                        registro['Motivo do Erro'] = motivos_texto
                        linhas_processadas.append(registro)
                    
                    exibir_tabela_generica(
                        dados=linhas_processadas,
                        config_colunas=config_colunas_erro,
                        colunas_resumidas=None,
                        callback_edit=None,
                        callback_deletar=None,
                        callback_estilo=None,
                        chave_tabela=f"pacote_erros_importacao_{chave_estado_dinamico}",
                        suporta_moeda=False                     
                    )
                else:
                    for item in rejeitadas:
                        st.warning(f"• {item}")

        # CASO 2: Lista de Erros de Validação (Pydantic / FastAPI)
        elif isinstance(payload, list):
            st.error("❌ **Erro de validação nos campos enviados:**")
            for numero, item in enumerate(payload, start=1):
                if not isinstance(item, dict):
                    st.warning(f"- {item}")
                    continue

                loc_partes = [str(parte) for parte in item.get("loc", []) if parte not in {"body", "dados"}]
                loc = " > ".join(loc_partes) or "não informado"
                indice = item.get("loc", [])[2] if len(item.get("loc", [])) > 2 else None
                campo = loc
                if isinstance(indice, int) and str(indice) in loc_partes:
                    campo = f"Registro {indice + 1} > " + " > ".join(loc_partes[1:])

                tipo = item.get("type")
                mensagem = item.get("msg") or item.get("message") or "Erro de validação"
                valor_recebido = item.get("input", "não informado")
                prefixo_tipo = f"`{tipo}` - " if tipo else ""
                st.markdown(
                    f"- **Campo `{campo}`**: {prefixo_tipo}{mensagem}. "
                    f"**Valor recebido:** `{valor_recebido}`"
                )

        # CASO 3: Mensagem de Texto Simples ou Exceção Geral
        else: 
            st.error(f"❌ **Erro na Operação:** {str(payload)}")


# ==============================================================================
# 🧱 FORMULÁRIOS ISOLADOS POR EVENTO (Padrão Limpo e Declarativo)
# ==============================================================================
def renderizar_formulario_bonificacao(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("🟢 Evento de Bonificação de Ativos")
    registro_id = dados_origem.get("id", "novo")
    
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")
    state['novo'] = state.get('novo', dados_origem.get('fk_ativo_gerado') or "Selecionar Ativo")

    # --- VALORES PADRÃO (RECONSTRUÇÃO DA INSTRUÇÃO) ---
    modo_calculo_salvo = "Fator %"
    val_calculo_default = "0"
    
    modo_custo_salvo = "Valor cota"
    val_custo_default = "0"

    if len(instrucoes) > 0:
        inst_0 = instrucoes[0]
        
        # 1. Recupera o cálculo de quantidade
        if "qtd_nova" in inst_0:
            modo_calculo_salvo = "Quantidade"
            val_calculo_default = f"{inst_0['qtd_nova']}".replace(".", ",")
        elif "qtd_fator_delta" in inst_0:
            modo_calculo_salvo = "Fator %"
            val_calculo_default = f"{inst_0['qtd_fator_delta'] * 100}".replace(".", ",")

        # 2. Recupera o custo atribuído (chaves de instrução: 'valor' ou 'valor_cota_op')
        if "valor" in inst_0:
            modo_custo_salvo = "Valor Total"
            val_custo_default = f"{inst_0['valor']}".replace(".", ",")
        elif "valor_cota_op" in inst_0:
            modo_custo_salvo = "Valor cota"
            val_custo_default = f"{inst_0['valor_cota_op']}".replace(".", ",")

    # --- LAYOUT TOTALMENTE LINEAR ---
    c1, c2, c3, c4, c5, c6 = st.container(border=True).columns([1.2, 1.2, 1.3, 1.0, 1.3, 1.0], vertical_alignment="bottom")
    
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'bonif_orig_{key_estado_dinamico}', titulo="📦 Ativo de Origem:")
        ticker_base = state['orig'] if state['orig'] != "Selecionar Ativo" else None
        
    with c2:
        componente_buscador_ativo(state, 'novo', sufixo_key=f'bonif_novo_{key_estado_dinamico}', titulo="🟢 Ativo Novo:")
        ticker_gerado = state['novo'] if state['novo'] != "Selecionar Ativo" else None
        
    with c3:
        opcoes_calc = ["Fator %", "Quantidade"]
        opcao_calculo = st.selectbox("Cálculo de Qtd", options=opcoes_calc, index=opcoes_calc.index(modo_calculo_salvo), key=f"bonif_tipo_calc_{key_estado_dinamico}")
        
    with c4:
        rotulo_qtd = "Fator (%)" if opcao_calculo == "Fator %" else "Qtd Nova"
        val_qtd_input = st_number_input_custom(rotulo_qtd, value=val_calculo_default, key=f"bonif_val_qtd_{key_estado_dinamico}")
        valor_qtd_final = val_qtd_input / 100 if opcao_calculo == "Fator %" else val_qtd_input
        
    with c5:
        opcoes_custo = ["Valor cota", "Valor Total"]
        opcao_custo = st.selectbox("Tipo de Custo", options=opcoes_custo, index=opcoes_custo.index(modo_custo_salvo), key=f"bonif_tipo_custo_{key_estado_dinamico}")
        
    with c6:
        rotulo_custo = "Custo Unit" if opcao_custo == "Valor cota" else "Custo Total"
        val_custo_input = st_number_input_custom(rotulo_custo, value=val_custo_default, key=f"bonif_val_custo_{key_estado_dinamico}")

    # --- RETORNO DA INSTRUÇÃO ---
    if ticker_base and ticker_gerado and (valor_qtd_final != 0 or val_custo_input != 0):
        chave_calc = "qtd_fator_delta" if opcao_calculo == "Fator %" else "qtd_nova"
        
        instrucao = {
            "ticker": ticker_gerado,
            "tipo_tributacao": "AJUSTE_CONTABIL",
            chave_calc: abs(valor_qtd_final)
        }

        # Aplica a chave correta da instrução baseada no tipo de custo selecionado
        if opcao_custo == "Valor cota":
            instrucao["valor_cota_op"] = abs(val_custo_input)
        else:
            instrucao["valor"] = abs(val_custo_input)

        return {
            "fk_ativo_base": ticker_base,
            "fk_ativo_gerado": ticker_gerado,
            "instrucoes": [instrucao]
        }
        
    return {}

def renderizar_formulario_grupamento_desdobramento(tipo_evento: str, dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader(f"🔄 Evento de {tipo_evento.title()}")
    registro_id = dados_origem.get("id", "novo")
  
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")

    ch_mut_calculo = "Fator Proporcional"
    quant_atual = "0,0"
    
    # ✨ CORREÇÃO: Resgate direto e seguro pela primeira instrução da esteira
    if len(instrucoes) > 0:
        inst_0 = instrucoes[0]
        if "qtd_fator_final" in inst_0:
            ch_mut_calculo = "Fator Proporcional"
            fator = inst_0["qtd_fator_final"]
            # ✨ CORREÇÃO: Aumentada precisão decimal para grupamentos complexos
            quant_atual = f"{round(fator * 100, 8)}".replace(".", ",") if tipo_evento == "DESDOBRAMENTO" else f"{round(fator, 10)}".replace(".", ",")
        elif "qtd_nova" in inst_0:
            ch_mut_calculo = "Quantidade Nova Exata"
            quant_atual = f"{inst_0['qtd_nova']}".replace(".", ",")

    c1, c2, c3 = st.container(border=True).columns([2.5, 1.8, 1.7])
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'g_orig_{key_estado_dinamico}', titulo="📉 Ativo Objeto:")
        ticker_mae = state['orig'] if state['orig'] != "Selecionar Ativo" else None
    with c2:
        opcoes_mut = ["Fator Proporcional", "Quantidade Nova Exata"]
        idx_mut = opcoes_mut.index(ch_mut_calculo) if ch_mut_calculo in opcoes_mut else 0
        var_mut = st.selectbox("Forma de Cálculo", opcoes_mut, index=idx_mut, key=f"g_sel_{key_estado_dinamico}")
    with c3:
        if var_mut == "Fator Proporcional":
            label_fator = "Fator Multiplicador % (Ex: 200% 1->2)" if tipo_evento == "DESDOBRAMENTO" else "Proporção Final (Ex: 0,1 10->1)"
        else:
            label_fator = "Nova Quantidade Exata"
            
        quant = st_number_input_custom(label_fator, value=quant_atual, key=f"g_qtd_{key_estado_dinamico}")
        # Validadores visuais de segurança
        if quant <= 100 and var_mut == "Fator Proporcional" and tipo_evento == "DESDOBRAMENTO":
            quant = 0
            st.warning("Deve ser maior que 100%")
        elif quant >= 1 and var_mut == "Fator Proporcional" and tipo_evento == "GRUPAMENTO":
            quant = 0
            st.warning("Deve ser menor que 1")

    if ticker_mae and quant != 0:
        inst_mutacao = {"ticker": ticker_mae, "tipo_tributacao": "AJUSTE_CONTABIL"}
        if var_mut == "Fator Proporcional":
            inst_mutacao["qtd_fator_final"] = round(quant / 100, 10) if tipo_evento == "DESDOBRAMENTO" else quant
        else:
            inst_mutacao["qtd_nova"] = quant
        return {
            "fk_ativo_base": ticker_mae,
            "fk_ativo_gerado": ticker_mae,
            "instrucoes": [inst_mutacao]
        }
    return {}

def renderizar_formulario_grupamento_desdobramento_duplo(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("⚡ Grupamento seguido de Desdobramento")
    registro_id = dados_origem.get("id", "novo")
        
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")

    ch_mut_calculo = "Fator Proporcional"
    if len(instrucoes) > 0 and "qtd_nova" in instrucoes[0]:
        ch_mut_calculo = "Quantidade Nova Exata"

    c1, c2, c3, c4 = st.container(border=True).columns(4)
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'gd_orig_{key_estado_dinamico}', titulo="📉 Ativo Objeto:")
        ticker_mae = state['orig'] if state['orig'] != "Selecionar Ativo" else None
    with c2:
        opcoes_mut = ["Fator Proporcional", "Quantidade Nova Exata"]
        idx_mut = opcoes_mut.index(ch_mut_calculo) if ch_mut_calculo in opcoes_mut else 0
        var_mut = st.selectbox("Forma de Cálculo", opcoes_mut, index=idx_mut, key=f"gd_sel_{key_estado_dinamico}")


    val_grup_str, val_desd_str = "0,0", "0,0"
    quant_grup, quant_desd = 0.0, 0.0
    validacao_ok = True

    if var_mut == "Fator Proporcional":
        if len(instrucoes) > 0 and "qtd_fator_final" in instrucoes[0]:
            val_grup_str = f"{instrucoes[0]['qtd_fator_final']}".replace(".", ",")
        if len(instrucoes) > 1 and "qtd_fator_final" in instrucoes[1]:
            val_desd_str = f"{instrucoes[1]['qtd_fator_final'] * 100}".replace(".", ",")
            
        with c3: 
            quant_grup = st_number_input_custom("1. Fator do Grupamento (Ex: 0,025)", value=val_grup_str, key=f"gd_grup_{key_estado_dinamico}")
            if quant_grup >= 1:
                st.warning("Deve ser menor que 1")
                validacao_ok = False
        with c4: 
            quant_desd = st_number_input_custom("2. Fator do Desdobramento (Ex: 8000%)", value=val_desd_str, key=f"gd_desd_{key_estado_dinamico}")
            if quant_desd <= 100:
                st.warning("Deve ser maior que 100%")
                validacao_ok = False
            else:
                quant_desd = quant_desd / 100

    else:
        if len(instrucoes) > 0 and "qtd_nova" in instrucoes[0]:
            val_grup_str = f"{instrucoes[0]['qtd_nova']}".replace(".", ",")
        if len(instrucoes) > 1 and "qtd_nova" in instrucoes[1]:
            val_desd_str = f"{instrucoes[1]['qtd_nova']}".replace(".", ",")
            
        with c3: quant_grup = st_number_input_custom("1. Qtd. Nova Pós-Grupamento", value=val_grup_str, key=f"gd_grup_{key_estado_dinamico}")
        with c4: quant_desd = st_number_input_custom("2. Qtd. Nova Pós-Desdobramento", value=val_desd_str, key=f"gd_desd_{key_estado_dinamico}")

    if validacao_ok and ticker_mae and quant_grup != 0 and quant_desd != 0:
        inst1 = {"ticker": ticker_mae, "tipo_tributacao": "AJUSTE_CONTABIL"}
        inst2 = {"ticker": ticker_mae, "tipo_tributacao": "AJUSTE_CONTABIL"}
        if var_mut == "Fator Proporcional":
            inst1["qtd_fator_final"] = quant_grup
            inst2["qtd_fator_final"] = quant_desd
        else:
            inst1["qtd_nova"] = quant_grup
            inst2["qtd_nova"] = quant_desd
        return {
            "fk_ativo_base": ticker_mae,
            "fk_ativo_gerado": ticker_mae,
            "instrucoes": [inst1, inst2]
        }
    return {}

def renderizar_formulario_fracao(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("🪙 Leilão de Frações (Recebimento em Caixa)")
    registro_id = dados_origem.get("id", "novo")
       
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")

    valor_atual, quant_atual = "0,0", "0,0"
    ch_frac_atual = "Valor p/ Cota Vendida"
    
    # 🔄 Recuperação segura dos dados salvos na instrução de caixa
    for inst in instrucoes:
        if inst.get("ticker") == "DINHEIRO_CAIXA":
            if "valor_caixa_cota_op" in inst:
                ch_frac_atual = "Valor p/ Cota Vendida"
                valor_atual = f"{inst['valor_caixa_cota_op']}".replace(".", ",")
            elif "valor_caixa" in inst:
                ch_frac_atual = "Valor Bruto Recebido"
                valor_atual = f"{inst['valor_caixa']}".replace(".", ",")
            if "qtd_delta" in inst:
                quant_atual = f"{abs(inst['qtd_delta'])}".replace(".", ",")

    c1, c2, c3, c4 = st.container(border=True).columns([1.5, 1.5, 1.5, 1.5])
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'f_orig_{key_estado_dinamico}', titulo="📉 Ativo de Origem:")
        ticker_mae = state['orig'] if state['orig'] != "Selecionar Ativo" else None

    with c2:
        opcoes_frac = ["Valor p/ Cota Vendida", "Valor Bruto Recebido"]
        idx_frac = opcoes_frac.index(ch_frac_atual) if ch_frac_atual in opcoes_frac else 0
        var_frac = st.selectbox("Tipo de Valor", opcoes_frac, index=idx_frac, key=f"f_sel_{key_estado_dinamico}") 

    with c3:
        rotulo_valor = "Valor por Cota" if var_frac == "Valor p/ Cota Vendida" else "Valor Total Bruto"
        valor = st_number_input_custom(rotulo_valor, value=valor_atual, key=f"f_val_{key_estado_dinamico}")

    with c4:
        quant = st_number_input_custom("Qtd Vendida (Opcional)", value=quant_atual, key=f"f_qtd_{key_estado_dinamico}")

    if ticker_mae and valor != 0:
        chave_financeira = "valor_caixa_cota_op" if var_frac == "Valor p/ Cota Vendida" else "valor_caixa"
        inst_frac = {
            "ticker": "DINHEIRO_CAIXA",
            chave_financeira: valor,
            "tipo_tributacao": "LEILAO_FRACOES"
        }
        if quant != 0:
            inst_frac["qtd_delta"] = -abs(quant)
        return {
            "fk_ativo_base": ticker_mae,
            "fk_ativo_gerado": None,
            "instrucoes": [inst_frac]
        }
    return {}

def renderizar_formulario_atualizacao(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("🔁 Evento de Atualização / Conversão de Ativo")
    registro_id = dados_origem.get("id", "novo")

    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")
    state['novo'] = state.get('novo', dados_origem.get('fk_ativo_gerado') or "Selecionar Ativo")

    modo_salvo = "Fator %"
    val_default_str = "0"
    
    if len(instrucoes) > 0:
        inst_0 = instrucoes[0]
        if "qtd_nova" in inst_0:
            modo_salvo = "Quantidade Nova Exata"
            val_default_str = f"{inst_0['qtd_nova']}".replace(".", ",")
        elif "qtd_fator_delta" in inst_0:
            modo_salvo = "Fator %"
            val_default_str = f"{round(inst_0['qtd_fator_delta'] * 100, 8)}".replace(".", ",")

    c1, c2, c3, c4 = st.container(border=True).columns([1.5, 1.5, 1.2, 1.2], vertical_alignment="bottom")
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'at_orig_{key_estado_dinamico}', titulo="📉 Ativo Antigo (Saída):")
        ticker_antigo = state['orig'] if state['orig'] != "Selecionar Ativo" else None
    with c2:
        componente_buscador_ativo(state, 'novo', sufixo_key=f'at_novo_{key_estado_dinamico}', titulo="📈 Ativo Novo (Entrada):")
        ticker_novo = state['novo'] if state['novo'] != "Selecionar Ativo" else None
    with c3:
        opcoes_calc = ["Fator %", "Quantidade Nova Exata"]
        opcao_calculo = st.selectbox("Tipo de Cálculo", options=opcoes_calc, index=opcoes_calc.index(modo_salvo), key=f"at_tipo_calc_{key_estado_dinamico}")
    with c4:
        rotulo_input = "Fator Proporcional" if opcao_calculo == "Fator %" else "Qtd Nova Exata"
        valor_input = st_number_input_custom(rotulo_input, value=val_default_str, key=f"at_val_calc_{key_estado_dinamico}")
        valor_final = valor_input / 100 if opcao_calculo == "Fator %" else valor_input

    if ticker_antigo and ticker_novo and valor_input != 0:
        chave_calc = "qtd_fator_delta" if opcao_calculo == "Fator %" else "qtd_nova"
        return {
            "fk_ativo_base": ticker_antigo,
            "fk_ativo_gerado": ticker_novo,
            "instrucoes": [
                {
                    "ticker": ticker_novo,
                    "proporcao_custo": 1.0,
                    chave_calc: abs(valor_final),
                    "tipo_tributacao": "AJUSTE_CONTABIL"
                },
                {
                    "ticker": ticker_antigo,
                    "qtd_fator_delta": -1.0,
                    "proporcao_custo": -1.0,
                    "tipo_tributacao": "AJUSTE_CONTABIL"
                }
            ]
        }
    return {}

def renderizar_formulario_opa(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("📢 OPA (Oferta Pública de Aquisição)")
    registro_id = dados_origem.get("id", "novo")
    
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")

    val_cota = "0,0"
    ch_opa_atual = "Valor p/ Cota Vendida"

    if len(instrucoes) > 0:
        inst_0 = instrucoes[0]
        if "valor_caixa_cota_op" in inst_0:
            ch_opa_atual = "Valor p/ Cota Vendida"
            val_cota = f"{inst_0['valor_caixa_cota_op']}".replace(".", ",")
        elif "valor_caixa" in inst_0:
            ch_opa_atual = "Valor Bruto Recebido"
            val_cota = f"{inst_0['valor_caixa']}".replace(".", ",")

    c1, c2, c3 = st.container(border=True).columns([2.5, 2.0, 1.5])
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'opa_orig_{key_estado_dinamico}', titulo="📉 Ativo de Saída:")
        ticker_mae = state['orig'] if state['orig'] != "Selecionar Ativo" else None
    with c2:
        opcoes_opa = ["Valor p/ Cota Vendida", "Valor Bruto Recebido"]
        idx_opa = opcoes_opa.index(ch_opa_atual) if ch_opa_atual in opcoes_opa else 0
        var_opa = st.selectbox("Tipo de Recebimento", opcoes_opa, index=idx_opa, key=f"opa_sel_{key_estado_dinamico}")
    with c3:
        rotulo_financeiro = "Valor por Cota" if var_opa == "Valor p/ Cota Vendida" else "Valor Total Bruto"
        valor = st_number_input_custom(rotulo_financeiro, value=val_cota, key=f"opa_val_{key_estado_dinamico}")

    if ticker_mae and valor != 0:
        chave_financeira = "valor_caixa_cota_op" if var_opa == "Valor p/ Cota Vendida" else "valor_caixa"
        return {
            "fk_ativo_base": ticker_mae,
            "fk_ativo_gerado": None,
            "instrucoes": [{
                "ticker": ticker_mae,
                chave_financeira: valor,
                "qtd_fator_delta": -1.0,
                "proporcao_custo": -1.0,
                "tipo_tributacao": "APURACAO_DARF"
            }]
        }
    return {}

def renderizar_formulario_reducao_capital(dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    st.subheader("🏛️ Redução de Capital (Amortização Visual)")
    registro_id = dados_origem.get("id", "novo")
    
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]
    
    state['orig'] = state.get('orig', dados_origem.get('fk_ativo_base') or "Selecionar Ativo")
    
    val_amortizar = "0,0"
    ch_red_atual = "Valor por Cota"
    for inst in instrucoes:
        if inst.get("ticker") == "DINHEIRO_CAIXA":
            if "valor_caixa_cota_com" in inst:
                ch_red_atual = "Valor por Cota"
                val_amortizar = f"{abs(inst['valor_caixa_cota_com'])}".replace(".", ",")
            elif "valor_caixa" in inst:
                ch_red_atual = "Valor Total Recebido"
                val_amortizar = f"{abs(inst['valor_caixa'])}".replace(".", ",")

    c1, c2, c3 = st.container(border=True).columns([2.5, 2.0, 1.5], vertical_alignment="bottom")
    with c1:
        componente_buscador_ativo(state, 'orig', sufixo_key=f'red_orig_{key_estado_dinamico}',titulo="📉 Ativo de Origem:")
        ticker_mae = state['orig'] if state['orig'] != "Selecionar Ativo" else None
    with c2:
        opcoes_red = ["Valor por Cota", "Valor Total Recebido"]
        idx_red = opcoes_red.index(ch_red_atual) if ch_red_atual in opcoes_red else 0
        var_red = st.selectbox("Formato do Recebimento", opcoes_red, index=idx_red, key=f"red_sel_{key_estado_dinamico}")
    with c3:
        # ✨ AJUSTE VISUAL: Rótulo dinâmico baseado na regra do cálculo
        rotulo_financeiro = "Valor por Cota" if var_red == "Valor por Cota" else "Valor Total Bruto"
        valor = st_number_input_custom(rotulo_financeiro, value=val_amortizar, key=f"red_val_{key_estado_dinamico}")

    if ticker_mae and valor != 0:
        chave_financeira = "valor_caixa_cota_com" if var_red == "Valor por Cota" else "valor_caixa"
        return {
            "fk_ativo_base": ticker_mae,
            "fk_ativo_gerado": None,
            "instrucoes": [{
                "ticker": "DINHEIRO_CAIXA",
                chave_financeira: -abs(valor),
                "tipo_tributacao": "AJUSTE_CONTABIL"
            }]
        }
    return {}

def renderizar_formulario_cisao_incorporacao(tipo_evento: str, dados_origem: dict, instrucoes: list, key_estado_dinamico="form_default") -> dict:
    
    registro_id = dados_origem.get("id", "novo")
    
    if key_estado_dinamico not in st.session_state:
        st.session_state[key_estado_dinamico] = {}
    state = st.session_state[key_estado_dinamico]

    # --- 1. PARSE E IDENTIFICAÇÃO DA TRIBUTAÇÃO DO ARQUIVO ---
    dados_origem = dados_origem or {}
    
    state['ativo_original_evento'] = state.get('ativo_original_evento') or dados_origem.get('fk_ativo_base') or "Selecionar Ativo"
    state['ativo_novo_evento'] = state.get('ativo_novo_evento') or dados_origem.get('fk_ativo_gerado') or "Selecionar Ativo"
  
    # Inicialização das Variáveis (Fallback caso o JSON não traga algum ticker)
    tributacao_detectada = "AJUSTE_CONTABIL"

    # Caixa Defaults
    ch_cx_r_atual = "Valor Bruto Recebido"
    valor_cx_r_atual = "0,0"
    valor_cx_atual = "0,0"

    # Mãe Defaults
    ch_m_atual = "Proporção do Custo (%)"
    valor_m_atual = "0,0"

    # Filho Defaults
    ch_qt_f_atual = "Fator de Conversão (%)"
    qt_f_atual = "0,0"
    ch_f_atual = "Valor Financeiro Bruto"
    valor_f_atual = "0,0"

    # Filho Defaults - Proporção ( DARF )
    ch_f_prop_atual = "Proporção do Custo (%)"
    prop_f_atual = "0,0"

    # --- 2. LOOP DE EXTRAÇÃO E FORMATAÇÃO DOS DADOS ---
    for inst in instrucoes:

        # 🪙 SE FOR DINHEIRO EM CAIXA
        if inst.get("ticker") == "DINHEIRO_CAIXA":
            tributacao_detectada = inst.get("tipo_tributacao", "AJUSTE_CONTABIL")
            inst_cx_atual = inst
            
            ch_cx_r_atual = "valor_caixa" if "valor_caixa" in inst_cx_atual else "valor_caixa_cota_com"
            valor_cx_r_atual = inst_cx_atual.get(ch_cx_r_atual, None)
            if valor_cx_r_atual is not None:
                valor_cx_r_atual = f"{valor_cx_r_atual}".replace(".", ",")
            ch_cx_r_atual = MAP_REVERSO_LABELS.get(ch_cx_r_atual, "Valor Bruto Recebido")

            if "valor" in inst_cx_atual:
                valor_cx_atual = inst_cx_atual.get("valor")
                valor_cx_atual = f"{valor_cx_atual}".replace(".", ",")

        # 📉 SE FOR O ATIVO BASE (MÃE)
        elif inst.get("ticker") == dados_origem.get('fk_ativo_base'):
            inst_m_atual = inst
            
            ch_m_atual = "custo_delta" if "custo_delta" in inst_m_atual else "proporcao_custo"
            valor_m_atual = inst_m_atual.get(ch_m_atual, None)
            if valor_m_atual is not None:
                if ch_m_atual == "proporcao_custo":
                    valor_m_atual = round(abs(valor_m_atual) * 100, 5)
                valor_m_atual = f"{valor_m_atual}".replace(".", ",")
            ch_m_atual = MAP_REVERSO_LABELS.get(ch_m_atual, "Proporção do Custo (%)")

        # 📈 SE FOR O ATIVO NOVO (FILHO)
        elif inst.get("ticker") == dados_origem.get('fk_ativo_gerado'):
            inst_f_atual = inst
            
            # Trata a Quantidade
            ch_qt_f_atual = "qtd_delta" if "qtd_delta" in inst_f_atual else "qtd_fator_delta"
            qt_f_atual = inst_f_atual.get(ch_qt_f_atual, None)
            if qt_f_atual is not None:
                if ch_qt_f_atual == "qtd_fator_delta" and qt_f_atual != -1:
                    qt_f_atual = round(qt_f_atual * 100, 5)
                qt_f_atual = f"{qt_f_atual}".replace(".", ",")
            ch_qt_f_atual = MAP_REVERSO_LABELS.get(ch_qt_f_atual, "Fator de Conversão (%)")

            # Trata o Custo
            ch_f_atual = "valor" if "valor" in inst_f_atual else "valor_cota_com" if "valor_cota_com" in inst_f_atual else "valor_cota_op"
            valor_f_atual = inst_f_atual.get(ch_f_atual, None)
            if valor_f_atual is not None:
                valor_f_atual = f"{valor_f_atual}".replace(".", ",")
            ch_f_atual = MAP_REVERSO_LABELS.get(ch_f_atual, "Valor Financeiro Bruto")
            
            # Trata proporção custo
            ch_f_prop_atual = "custo_delta" if "custo_delta" in inst_f_atual else "proporcao_custo"
            prop_f_atual = inst_f_atual.get(ch_f_prop_atual, None)
            if prop_f_atual is not None:
                if ch_f_prop_atual == "proporcao_custo":
                    prop_f_atual = round(abs(prop_f_atual) * 100, 5)
                prop_f_atual = f"{prop_f_atual}".replace(".", ",")
            ch_f_prop_atual = MAP_REVERSO_LABELS.get(ch_f_prop_atual, "Proporção do Custo (%)")


    # --- 3. CONFIGURAÇÃO DE OPÇÕES E INDEX DO SELETOR DE TRIBUTAÇÃO ---
    if tipo_evento == "CISÃO":
        opcoes_tributacao = ["AJUSTE_CONTABIL", "RETIDO_FONTE"]
    else:
        opcoes_tributacao = ["AJUSTE_CONTABIL", "APURACAO_DARF", "RETIDO_FONTE"]
        
    try:
        index_tributacao = opcoes_tributacao.index(tributacao_detectada)
    except ValueError:
        index_tributacao = 0

    c_top, c_top2 = st.columns([2, 2])
    c_top.subheader(f"🔀 Evento de {tipo_evento.title()}")
    # Seletor de Tributação Dinâmico
    with c_top2:
        tipo_tributacao = st.selectbox("Tributação:", opcoes_tributacao, index=index_tributacao, key=f"sl_tributacao_{key_estado_dinamico}")

    payload = {"instrucoes": []}

    # =========================================================================
    # 🔀 CENÁRIO 1: CISÃO OU INCORPORAÇÃO  + AJUSTE_CONTABIL
    # =========================================================================
    if tipo_tributacao == "AJUSTE_CONTABIL":
        
        if tipo_evento == "CISÃO":
            # 1. Entrada de Dados da Mãe (Origem - Cisão)
            c1, c2, c3 = st.container(border=True).columns([2.5, 1.5, 2])
            with c1:
                componente_buscador_ativo(state, 'ativo_original_evento', sufixo_key=f'c_ac_m_{key_estado_dinamico}', titulo="📉 Ativo Base (Mãe):")
                ticker_mae = state['ativo_original_evento'] if state['ativo_original_evento'] != "Selecionar Ativo" else None
            with c2: 
                valor_m = st_number_input_custom("Valor Redução", value=valor_m_atual, key=f"c_ac_num_m_{key_estado_dinamico}")
            with c3:
                opcoes_m = list(MAP_PROPORCAO.keys())
                idx_m = opcoes_m.index(ch_m_atual) if ch_m_atual in opcoes_m else 0
                var_m = st.selectbox("Variável de Redução", opcoes_m, index=idx_m, key=f"c_ac_sel_m_{key_estado_dinamico}")
        else:
            # 1. Entrada de Dados da Mãe (Origem - Incorporação)
            c1, c2, c3 = st.container(border=True).columns([2.5, 1.5, 2])
            with c1:
                componente_buscador_ativo(state, 'ativo_original_evento', sufixo_key=f'i_ac_m_{key_estado_dinamico}', titulo="📉 Ativo Base (Mãe):")
                ticker_mae = state['ativo_original_evento'] if state['ativo_original_evento'] != "Selecionar Ativo" else None
            with c2: 
                st.text_input("Valor Redução", value="100,0", disabled=True, key=f"i_ac_num_m_{key_estado_dinamico}")
                valor_m = 100
            with c3: 
                st.text_input("Variável de Redução", value="Proporção do Custo (%)", disabled=True, key=f"i_ac_sel_m_{key_estado_dinamico}")
                var_m = "Proporção do Custo (%)"

        # 2. Entrada de Dados do Filho (Destino) - Custo espelhado e Variável idêntica à da Mãe
        c4, c5, c6, c7, c8 = st.container(border=True).columns([1.5, 1.0, 1.5, 1.2, 1.6])
        with c4:
            componente_buscador_ativo(state, 'ativo_novo_evento', sufixo_key=f'c_ac_f_{key_estado_dinamico}', titulo="📈 Novo Ativo (Filho):")
            ticker_filho = state['ativo_novo_evento'] if state['ativo_novo_evento'] != "Selecionar Ativo" else None
        with c5: 
            valor_q = st_number_input_custom("Quantidade / Fator", value=qt_f_atual, key=f"c_ac_num_q_{key_estado_dinamico}")
        with c6:
            opcoes_q = list(MAP_QTD.keys())
            idx_q = opcoes_q.index(ch_qt_f_atual) if ch_qt_f_atual in opcoes_q else 0
            var_q = st.selectbox("Variável de Qtd", opcoes_q, index=idx_q, key=f"c_ac_sel_q_{key_estado_dinamico}")
        with c7: 
            # 🎯 Sincroniza o Custo via Session State
            custo_exibicao = f"{valor_m}".replace(".", ",") if (valor_m is not None and valor_m != 0.0) else "0.0"
            st.session_state[f'c_ac_dis_c_{key_estado_dinamico}'] = custo_exibicao
            st.text_input("Custo Atribuído", disabled=True, key=f"c_ac_dis_c_{key_estado_dinamico}")
        with c8: 
            # 🎯 Sincroniza a Variável de Custo via Session State
            st.session_state[f'c_ac_lbl_c_{key_estado_dinamico}'] = var_m
            st.text_input("Variável de Custo", disabled=True, key=f"c_ac_lbl_c_{key_estado_dinamico}")

        # 3. Construção Defensiva do Payload Estruturado
        payload['fk_ativo_base'] = ticker_mae
        payload['fk_ativo_gerado'] = ticker_filho
        
        # Resolve a chave contábil com base no novo MAP_AJUSTE_CONTABEL
        chave_contabil = MAP_PROPORCAO[var_m]
        
        if ticker_mae and valor_m != 0 and ticker_filho and valor_q != 0:
            # Mãe retira o custo (Sinal Negativo)
            val_m_processado = -round(valor_m / 100, 10) if chave_contabil == "proporcao_custo" else -valor_m

            # Filho recebe o custo espelhado (Sinal Positivo)
            val_f_processado = round(valor_m / 100, 10) if chave_contabil == "proporcao_custo" else valor_m
            
            # Trata a quantidade gerada usando o novo MAP_QTD
            chave_q = MAP_QTD[var_q]
            quant = round(valor_q / 100, 10) if chave_q in ["qtd_fator_delta"] else valor_q
            
            # --- Dicionário da Mãe ---
            inst_m = {
                "ticker": ticker_mae, 
                chave_contabil: val_m_processado, 
                "tipo_tributacao": "AJUSTE_CONTABIL"
            }
            if tipo_evento == "INCORPORAÇÃO":
                inst_m['qtd_fator_delta'] = -1

            # --- Dicionário do Filho ---
            inst_f = {
                "ticker": ticker_filho, 
                "tipo_tributacao": "AJUSTE_CONTABIL",
                chave_contabil: val_f_processado,
                chave_q: abs(quant)
            }            
            
            # Consolidação final na lista única do payload
            payload["instrucoes"] = [inst_m, inst_f]
        else:
            payload = None

    # =========================================================================
    # 🔀 CENÁRIO 2: CISÃO OU INCORPORAÇÃO + RETIDO_FONTE
    # =========================================================================
    elif tipo_tributacao == "RETIDO_FONTE":

        if tipo_evento == "CISÃO":
            # 1. Entrada de Dados da Mãe (Origem - Cisão)
            c1, c2, c3 = st.container(border=True).columns([2.5, 1.5, 2])
            with c1:
                componente_buscador_ativo(state, 'ativo_original_evento', sufixo_key=f'c_rf_m_{key_estado_dinamico}', titulo="📉 Ativo Base (Mãe):")
                ticker_mae = state['ativo_original_evento'] if state['ativo_original_evento'] != "Selecionar Ativo" else None
            with c2: 
                valor_m = st_number_input_custom("Valor Redução", key=f"c_rf_num_m_{key_estado_dinamico}", value=valor_m_atual)
            with c3:
                opcoes_m = list(MAP_PROPORCAO.keys())
                idx_m = opcoes_m.index(ch_m_atual) if ch_m_atual in opcoes_m else 0
                var_m = st.selectbox("Variável de Redução", opcoes_m, index=idx_m, key=f"c_rf_sel_m_{key_estado_dinamico}")
        else:
            # 1. Entrada de Dados da Mãe (Origem - Incorporação)
            c1, c2, c3 = st.container(border=True).columns([2.5, 1.5, 2])
            with c1:
                componente_buscador_ativo(state, 'ativo_original_evento', sufixo_key=f'i_rf_m_{key_estado_dinamico}', titulo="📉 Ativo Base (Mãe):")
                ticker_mae = state['ativo_original_evento'] if state['ativo_original_evento'] != "Selecionar Ativo" else None
            with c2: 
                st.text_input("Valor Redução", value="100,0", disabled=True, key=f"i_rf_num_m_{key_estado_dinamico}")
                valor_m = 100
            with c3: 
                st.text_input("Variável de Redução", value="Proporção do Custo (%)", disabled=True, key=f"i_rf_sel_m_{key_estado_dinamico}")
                var_m = "Proporção do Custo (%)"
     
        # 2. Entrada de Dados do Filho (Destino)
        c4, c5, c6, c7, c8 = st.container(border=True).columns([1.2, 0.8, 1.5, 0.8, 1.6])
        with c4:
            componente_buscador_ativo(state, 'ativo_novo_evento', sufixo_key=f'c_rf_f_{key_estado_dinamico}', titulo="📈 Novo Ativo (Filho):")
            ticker_filho = state['ativo_novo_evento'] if state['ativo_novo_evento'] != "Selecionar Ativo" else None
        with c5: 
            valor_q = st_number_input_custom("Quantidade / Fator", key=f"c_rf_num_q_{key_estado_dinamico}", value=qt_f_atual)
        with c6:
            opcoes_q = list(MAP_QTD.keys())
            idx_q = opcoes_q.index(ch_qt_f_atual) if ch_qt_f_atual in opcoes_q else 0
            var_q = st.selectbox("Variável de Qtd", opcoes_q, index=idx_q, key=f"c_rf_sel_q_{key_estado_dinamico}")
        with c7: 
            valor_c = st_number_input_custom("Custo Atribuído", key=f"c_rf_num_c_{key_estado_dinamico}", value=valor_f_atual)
        with c8:
            opcoes_c = list(MAP_CUSTO_FILHO.keys())
            idx_c = opcoes_c.index(ch_f_atual) if ch_f_atual in opcoes_c else 0
            var_c = st.selectbox("Variável de Custo", opcoes_c, index=idx_c, key=f"c_rf_sel_c_{key_estado_dinamico}")

        # 3. Entrada de Dados de Recebimento de Caixa (Totalmente livre)
        c9, c10 = st.container(border=True).columns([2, 2])
        with c9: 
            valor_cx_r = st_number_input_custom("Montante Recebido", key=f"c_rf_num_cx_{key_estado_dinamico}", value=valor_cx_r_atual)
        with c10:
            opcoes_cx = list(MAP_RECEBIMENTO_CAIXA.keys())
            idx_cx = opcoes_cx.index(ch_cx_r_atual) if ch_cx_r_atual in opcoes_cx else 0
            var_cx_r = st.selectbox("Variável Recebimento", opcoes_cx, index=idx_cx, key=f"c_rf_sel_cx_{key_estado_dinamico}")

        # 4. Construção Centralizada do Payload
        payload['fk_ativo_base'] = ticker_mae
        payload['fk_ativo_gerado'] = ticker_filho

        if (ticker_mae and valor_m != 0 and 
            ticker_filho and valor_q != 0 and valor_c != 0 and 
            valor_cx_r != 0):
            
            # Resolve chaves e valores da Mãe
            chave_contabil_mae = MAP_PROPORCAO[var_m]
            val_m_processado = -round(valor_m / 100, 10) if chave_contabil_mae == "proporcao_custo" else -valor_m
            
            # Resolve chaves e valores do Filho
            ch_q = MAP_QTD[var_q]
            chave_contabil_filho = MAP_CUSTO_FILHO[var_c]
            
            # Resolve chaves e valores do caixa
            chave_contabil_caixa_rec = MAP_RECEBIMENTO_CAIXA[var_cx_r]

            quant = round(valor_q / 100, 10) if ch_q in ["qtd_fator_delta"] else valor_q
            val_f = round(valor_c / 100, 10) if chave_contabil_filho in ["proporcao_custo"] else valor_c

            # Calculo valor Cota da perda Dinheiro
            if chave_contabil_filho == "valor_cota_op":
                val_c = val_f * quant
                if ch_q == "qtd_fator_delta":
                    chave_contabil_caixa = "valor_cota_com"
                else:
                    chave_contabil_caixa = "valor"
            elif chave_contabil_filho in ["valor_cota_com", "valor"]:
                val_c = val_f
                chave_contabil_caixa = chave_contabil_filho
            
            # --- Dicionário da Mãe ---
            inst_m = {
                "ticker": ticker_mae,
                chave_contabil_mae: val_m_processado,
                "tipo_tributacao": "AJUSTE_CONTABIL"
            }
            if tipo_evento == "INCORPORAÇÃO":
                inst_m['qtd_fator_delta'] = -1

            # --- Dicionário do Filho ---
            inst_f = {
                "ticker": ticker_filho, 
                "tipo_tributacao": "AJUSTE_CONTABIL",
                chave_contabil_filho: val_f,
                ch_q: abs(quant)
            }

            # --- Dicionário do Caixa ---
            inst_cx = {
                "ticker": "DINHEIRO_CAIXA", 
                "tipo_tributacao": "RETIDO_FONTE",                
                chave_contabil_mae: val_m_processado,
                chave_contabil_caixa: val_c,
                chave_contabil_caixa_rec: valor_cx_r                
            }

            # Consolidação final na lista única do payload
            payload["instrucoes"] = [inst_m, inst_f, inst_cx]
        else:
            payload = None

    # =========================================================================
    # 🔀 CENÁRIO 3: INCORPORAÇÃO + APURACAO_DARF
    # =========================================================================
    elif tipo_tributacao == "APURACAO_DARF" and tipo_evento == "INCORPORAÇÃO":
        
        # 1. Entrada de Dados da Mãe (Origem - Incorporação)
        c1, c2, c3 = st.container(border=True).columns([2.5, 1.5, 2])
        with c1:
            componente_buscador_ativo(state, 'ativo_original_evento', sufixo_key=f'i_df_m_{key_estado_dinamico}', titulo="📉 Ativo Base (Mãe):")
            ticker_mae = state['ativo_original_evento'] if state['ativo_original_evento'] != "Selecionar Ativo" else None
        with c2: 
            st.text_input("Valor Redução", value="100,0", disabled=True, key=f"i_df_num_m_{key_estado_dinamico}")
            valor_m = 100
        with c3: 
            st.text_input("Variável de Redução", value="Proporção do Custo (%)", disabled=True, key=f"i_df_sel_m_{key_estado_dinamico}")
            var_m = "Proporção do Custo (%)"

        # 2. Entrada de Dados do Filho (Destino) - Custo espelhado e Variável idêntica à da Mãe
        c4, c5, c6, c7, c8 = st.container(border=True).columns([1.5, 1.0, 1.5, 1.0, 1.6])
        with c4:
            componente_buscador_ativo(state, 'ativo_novo_evento', sufixo_key=f'i_df_f_{key_estado_dinamico}', titulo="📈 Novo Ativo (Filho):")
            ticker_filho = state['ativo_novo_evento'] if state['ativo_novo_evento'] != "Selecionar Ativo" else None
        with c5: 
            valor_q = st_number_input_custom("Quantidade / Fator", key=f"i_df_num_q_{key_estado_dinamico}", value=qt_f_atual)
        with c6:
            opcoes_q = list(MAP_QTD.keys())
            idx_q = opcoes_q.index(ch_qt_f_atual) if ch_qt_f_atual in opcoes_q else 0
            var_q = st.selectbox("Variável de Qtd", opcoes_q, index=idx_q, key=f"i_df_sel_q_{key_estado_dinamico}")
        
        valor_c = 0.0
        with c7: 
            # 🎯 Sincroniza o Custo via Session State
            valor_f = st_number_input_custom("Custo Atribuído", key=f"i_df_num_c_{key_estado_dinamico}", value=prop_f_atual)
        with c8:
            opcoes_f = list(MAP_PROPORCAO.keys())
            idx_f = opcoes_f.index(ch_f_prop_atual) if ch_f_prop_atual in opcoes_f else 0
            var_f = st.selectbox("Variável de Custo", opcoes_f, index=idx_f, key=f"i_df_sel_f_{key_estado_dinamico}")
        # 3. Entrada de Dados de Recebimento de Caixa (Totalmente livre)
        c9, c10, c11, c12 = st.container(border=True).columns([1.2, 2, 1.2, 2])
        with c9: 
            valor_cx_r = st_number_input_custom("Montante Recebido", key=f"i_df_num_cx_{key_estado_dinamico}", value=valor_cx_r_atual)
        with c10:
            opcoes_cx = list(MAP_RECEBIMENTO_CAIXA.keys())
            idx_cx = opcoes_cx.index(ch_cx_r_atual) if ch_cx_r_atual in opcoes_cx else 0
            var_cx_r = st.selectbox("Variável Recebimento", opcoes_cx, index=idx_cx, key=f"i_df_sel_cx_{key_estado_dinamico}")
        with c11: 
            # 🎯 Sincroniza o Custo via Session State
            if var_f == "Proporção do Custo (%)": 
                custo_exibicao_c = f"{round(100 - valor_f, 10)}".replace(".", ",") if (valor_f is not None and valor_f != 0.0) else "0.0"
                st.session_state[f'i_df_dis_c_label_{key_estado_dinamico}'] = custo_exibicao_c
                st.text_input("Custo Atribuído", disabled=True, key=f"i_df_dis_c_label_{key_estado_dinamico}")
                # 🟢 RESOLVIDO: Declarado valor_c apropriadamente mesmo quando a proporção calcula o restante
                valor_c = round(100 - valor_f, 10)
            else:
                valor_c = st_number_input_custom("Custo Atribuído", key=f"i_df_dis_c_input_{key_estado_dinamico}", value=valor_cx_atual)
        with c12: 
            # 🎯 Sincroniza a Variável de Custo via Session State
            st.session_state[f'i_df_lbl_c_{key_estado_dinamico}'] = var_f
            st.text_input("Variável de Custo", disabled=True, key=f"i_df_lbl_c_{key_estado_dinamico}")

        # 4. Construção Defensiva do Payload Estruturado
        payload['fk_ativo_base'] = ticker_mae
        payload['fk_ativo_gerado'] = ticker_filho
        
        if ticker_mae and valor_m != 0 and ticker_filho and valor_q != 0 and valor_cx_r != 0:
            # Resolve a chave contábil com base no novo MAP_AJUSTE_CONTABEL
            chave_contabil = MAP_PROPORCAO[var_f]

            # Resolve chaves e valores do caixa
            chave_contabil_caixa_rec = MAP_RECEBIMENTO_CAIXA[var_cx_r]

            # Filho recebe o custo espelhado (Sinal Positivo)
            val_f_processado = round(valor_f / 100, 10) if chave_contabil == "proporcao_custo" else valor_f
            
            # Caixa recebe o resto
            if chave_contabil == "proporcao_custo": 
                val_c_processado = round(-1 + val_f_processado, 10)
            else:
                val_c_processado = -valor_c

            # Trata a quantidade gerada usando o novo MAP_QTD
            chave_q = MAP_QTD[var_q]
            quant = round(valor_q / 100, 10) if chave_q in ["qtd_fator_delta"] else valor_q
            
            # --- Dicionário da Mãe ---
            inst_m = {
                "ticker": ticker_mae, 
                "proporcao_custo": -1, 
                "qtd_fator_delta": -1,
                "tipo_tributacao": "AJUSTE_CONTABIL"
            }
                
            # --- Dicionário do Filho ---
            inst_f = {
                "ticker": ticker_filho, 
                "tipo_tributacao": "AJUSTE_CONTABIL",
                chave_contabil: val_f_processado,
                chave_q: abs(quant)
            }            
            
            # --- Dicionário do Caixa ---
            inst_cx = {
                "ticker": "DINHEIRO_CAIXA", 
                "tipo_tributacao": "APURACAO_DARF",                
                chave_contabil: val_c_processado,
                chave_contabil_caixa_rec: valor_cx_r                
            }
            # Consolidação final na lista única do payload
            payload["instrucoes"] = [inst_m, inst_f, inst_cx]
        else:
            payload = None

    return payload