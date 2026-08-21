import streamlit as st
from Pages.utils.ferramentas import sanitizar_numero, formatar_ativo_visual


def renderizar_fluxograma_evento(tipo_evento: str, payload: dict, resultado=None):
    if not payload:
        return

    instrucoes = payload.get("instrucoes", [])
    ticker_base = payload.get("fk_ativo_base", "Ativo Base")
    ticker_gerado = payload.get("fk_ativo_gerado", "Ativo Novo")

    if tipo_evento in ["CISÃO", "INCORPORAÇÃO"]:
        _renderizar_fluxograma_cisao_incorporacao(tipo_evento, instrucoes, ticker_base, ticker_gerado, resultado)
    elif tipo_evento in ["DESDOBRAMENTO", "GRUPAMENTO", "GRUPAMENTO_DESDOBRAMENTO"]:
        # Chamada limpa repassando a instrução e o ticker_base isolados do payload!
        _renderizar_fluxograma_proporcional(instrucoes, ticker_base, tipo_evento, resultado)
    elif tipo_evento == "BONIFICAÇÃO":
        _renderizar_fluxograma_bonificacao(instrucoes, ticker_base,ticker_gerado, resultado)
    elif tipo_evento == "FRAÇÃO":
        _renderizar_fluxograma_leilao_fracoes(instrucoes, ticker_base, resultado)
    elif tipo_evento == "OPA":
        _renderizar_fluxograma_opa(instrucoes, ticker_base, resultado)
    elif tipo_evento in ["REDUÇÃO DE CAPITAL"]:
        _renderizar_fluxograma_reducao_capital(instrucoes, ticker_base, resultado)
    elif tipo_evento in ["ATUALIZAÇÃO"]:
        # Passamos também o ticker_gerado (fk_ativo_gerado) se existir
        _renderizar_fluxograma_atualizacao(instrucoes, ticker_base, ticker_gerado, resultado)


def _renderizar_fluxograma_proporcional(instrucoes: list, ticker_base: str, tipo_evento: str, resultado=None):
    """
    Renderiza o fluxo contábil de movimentação consumindo diretamente os cálculos,
    frações e custos acumulados (BRL/USD) retornados pelo backend no parâmetro 'resultado'.
    """
    if not instrucoes:
        return

    ticker_exibicao = formatar_ativo_visual(ticker_base)

    # Valores padrão de fallback caso não haja simulação real rodada (apenas rascunho visual)
    qtd_origem = "qtd"
    custo_brl_origem = "custo_brl"
    custo_usd_origem = "custo_usd"
    
    texto_intermediario = "qtd_temp"
    texto_final = "Posição Final"
    
    # 1. Se temos o resultado real do backend, extraímos os dados e custos prontos
    if resultado and len(resultado) >= 2:
        # Busca a referência inicial (Origem)
        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            qtd_origem = f"{sanitizar_numero(ref_anterior.get('quant_acum')):.4f}".replace(".", ",")
            c_brl = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_brl_origem = f"R$ {c_brl:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_usd_origem = f"US$ {c_usd:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        if tipo_evento == "GRUPAMENTO_DESDOBRAMENTO":
            # Pega as duas etapas do evento corporativo ordenadas pelo 'seq'
            etapas_evento = sorted(
                [x for x in resultado if x.get("tipo") == "GRUPAMENTO_DESDOBRAMENTO"],
                key=lambda x: x.get("seq", 0)
            )
            
            if len(etapas_evento) >= 2:
                # Etapa 1: Grupamento (Intermediário)
                grup_data = etapas_evento[0]
                q_inter = sanitizar_numero(grup_data.get("quant_acum"))
                f_inter = sanitizar_numero(grup_data.get("quant_fracao"))
                cb_inter = sanitizar_numero(grup_data.get("custo_acum_brl"))
                cu_inter = sanitizar_numero(grup_data.get("custo_acum_usd"))
                
                # Etapa 2: Desdobramento (Destino/Final)
                desd_data = etapas_evento[1]
                q_final = sanitizar_numero(desd_data.get("quant_acum"))
                f_final = sanitizar_numero(desd_data.get("quant_fracao"))
                cb_final = sanitizar_numero(desd_data.get("custo_acum_brl"))
                cu_final = sanitizar_numero(desd_data.get("custo_acum_usd"))

                # Formata textos do nó Intermediário
                texto_intermediario = f"Qtd: {q_inter:.4f}".replace(".", ",")
                if f_inter and f_inter > 0:
                    texto_intermediario += f" (Frac: {f_inter:.4f})".replace(".", ",")
                texto_intermediario += f"\\nCusto: R$ {cb_inter:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                texto_intermediario += f" | US$ {cu_inter:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

                # Formata textos do nó Final
                texto_final = f"Qtd: {q_final:.4f}".replace(".", ",")
                if f_final and f_final > 0:
                    texto_final += f" (Frac: {f_final:.4f})".replace(".", ",")
                texto_final += f"\\nCusto: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                texto_final += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
        else:
            # Grupamento ou Desdobramento puros
            etapa_unica = next((x for x in resultado if x.get("tipo") == tipo_evento), None)
            if etapa_unica:
                q_final = sanitizar_numero(etapa_unica.get("quant_acum"))
                f_final = sanitizar_numero(etapa_unica.get("quant_fracao"))
                cb_final = sanitizar_numero(etapa_unica.get("custo_acum_brl"))
                cu_final = sanitizar_numero(etapa_unica.get("custo_acum_usd"))

                texto_final = f"Qtd: {q_final:.4f}".replace(".", ",")
                if f_final and f_final > 0:
                    texto_final += f" (Frac: {f_final:.4f})".replace(".", ",")
                texto_final += f"\\nCusto: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
                texto_final += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

    # 2. Fallback visual algébrico (Sem simulação executada)
    else:
        if "qtd_fator_final" in instrucoes[0]:
            fator_g = instrucoes[0].get("qtd_fator_final", 1) if len(instrucoes) >= 1 else 1
            fator_d = instrucoes[1].get("qtd_fator_final", 1) if len(instrucoes) >= 2 else 1
        else:
            fator_g = instrucoes[0].get("qtd_nova", 1) if len(instrucoes) >= 1 else 1
            fator_d = instrucoes[1].get("qtd_nova", 1) if len(instrucoes) >= 2 else 1

        custo_brl_origem = "custo_brl"
        custo_usd_origem = "custo_usd"
        
        if tipo_evento == "GRUPAMENTO_DESDOBRAMENTO":
            if "qtd_fator_final" in instrucoes[0]:
                texto_intermediario = f"Qtd: int(qtd * {str(fator_g).replace('.', ',')})\\nCusto: Mantido"
                texto_final = f"Qtd: intermediário * {str(fator_d).replace('.', ',')}\\nCusto: Mantido"
            else:
                texto_intermediario = f"Qtd: int({str(fator_g).replace('.', ',')})\\nCusto: Mantido"
                texto_final = f"Qtd: intermediário * {str(fator_d).replace('.', ',')}\\nCusto: Mantido"
        else:
            if "qtd_fator_final" in instrucoes[0]:
                fator = instrucoes[0].get("qtd_fator_final")
                fator_exibicao = f"qtd * {fator}".replace('.', ',')
            else:
                fator = instrucoes[0].get("qtd_nova", 1)
                fator_exibicao = f"{fator}".replace('.', ',')
            texto_final = f"Qtd: {fator_exibicao}\\nCusto: Mantido"

    # ==========================================
    # RENDERIZAÇÃO DOS GRÁFICOS
    # ==========================================
    if tipo_evento == "GRUPAMENTO_DESDOBRAMENTO":
        dot_code = """
        digraph G {
            rankdir=LR;
            node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
            edge [fontname="Arial", fontsize=9, color="#17B890"];

            Origem [label="📦 __TICKER__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59", penwidth=1.5];
            Intermediario [label="🔄 __TICKER__\\n1. Pós-Grup.\\n__QTD_INTER__", fillcolor="#FFFBEB", color="#D97706", style="dashed,filled,rounded"];
            Destino [label="🟢 __TICKER__\\n2. Pós-Desdobramento\\n__QTD_FINAL__", fillcolor="#F0FDF4", color="#15803D", penwidth=2];

            Origem -> Intermediario [label=" Agrupa", style=dashed, color="#D97706"];
            Intermediario -> Destino [label=" Desdobra", color="#15803D"];
        }
        """
        dot_code = (dot_code
                    .replace("__TICKER__", ticker_exibicao)
                    .replace("__QTD_ATUAL__", str(qtd_origem))
                    .replace("__CUSTO_BRL_O__", custo_brl_origem)
                    .replace("__CUSTO_USD_O__", custo_usd_origem)
                    .replace("__QTD_INTER__", texto_intermediario)
                    .replace("__QTD_FINAL__", texto_final))
    else:
        label_transicao = "Grupamento" if tipo_evento == "GRUPAMENTO" else "Desdobramento"
        dot_code = """
        digraph G {
            rankdir=LR;
            node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
            edge [fontname="Arial", fontsize=9, color="#17B890"];

            Origem [label="📦 __TICKER__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59"];
            Destino [label="🟢 __TICKER__\\nPosição Ajustada\\n__QTD_FINAL__", fillcolor="#F0FDF4", color="#15803D", penwidth=2];
            
            Origem -> Destino [label=" __LABEL__"];
        }
        """
        dot_code = (dot_code
                    .replace("__TICKER__", ticker_exibicao)
                    .replace("__QTD_ATUAL__", str(qtd_origem))
                    .replace("__CUSTO_BRL_O__", custo_brl_origem)
                    .replace("__CUSTO_USD_O__", custo_usd_origem)
                    .replace("__QTD_FINAL__", texto_final)
                    .replace("__LABEL__", label_transicao))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_bonificacao(instrucoes: list, ticker_base: str, ticker_gerado: str = None, resultado=None):
    """
    Renderiza o fluxo contábil de Bonificação de Ações.
    
    COMPORTAMENTO:
      - Com Resultado (Backend): Exibe obrigatoriamente as duas moedas (Real e Dólar) 
        tanto no custo de origem quanto no custo final acumulado e atribuído.
      - Sem Resultado (Rascunho): Exibe apenas valores numéricos puros (sem símbolos de moeda),
        injetando os valores inseridos de forma direta nas descrições de custo.
    """
    if not instrucoes:
        return

    # Se não houver ticker_gerado explícito, assume-se que é o próprio ativo base
    ticker_gerado = ticker_gerado or ticker_base
    ativo_diferente = (ticker_base != ticker_gerado)

    ticker_base_exibicao = formatar_ativo_visual(ticker_base)
    ticker_gerado_exibicao = formatar_ativo_visual(ticker_gerado)

    # --- FALLBACKS / VALORES PADRÃO ---
    qtd_origem = "qtd"
    custo_origem_formatado = "custo_base"
    
    texto_destino = "Posição Ajustada"
    texto_bônus = "Ações Bonificadas"

    # Captura parâmetros da instrução para o rascunho
    inst = instrucoes[0]
    modo_qtd_exata = "qtd_nova" in inst
    qtd_nova_exata = inst.get("qtd_nova", 0)
    fator_bonus = inst.get("qtd_fator_final", 0) or inst.get("qtd_fator_delta", 0) or 0
    
    custo_total_atribuído = inst.get("valor", 0)
    custo_unit_atribuído = inst.get("valor_cota_op", 0)

    # --- 1. COM DADOS REAIS DO BACKEND (DUAS MOEDAS: R$ E US$) ---
    if resultado and len(resultado) >= 2:
        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            
            # Formata exibindo as duas moedas para a origem
            c_brl_str = f"R$ {c_brl_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            c_usd_str = f"US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_origem_formatado = f"{c_brl_str} | {c_usd_str}"

        ref_bonus = next((x for x in resultado if x.get("tipo") in ["BONIFICAÇÃO", "BONIFICACAO"]), None)
        if ref_bonus:
            q_final = sanitizar_numero(ref_bonus.get("quant_acum"))
            f_fracao = sanitizar_numero(ref_bonus.get("quant_fracao"))
            
            # Custos finais acumulados
            cb_final = sanitizar_numero(ref_bonus.get("custo_acum_brl"))
            cu_final = sanitizar_numero(ref_bonus.get("custo_acum_usd"))
            custo_final_brl_str = f"R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_final_usd_str = f"US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_final_formatado = f"{custo_final_brl_str} | {custo_final_usd_str}"

            # Custos atribuídos no lançamento
            custo_atrib_brl = sanitizar_numero(ref_bonus.get("preco_contabil_brl"))
            custo_atrib_usd = sanitizar_numero(ref_bonus.get("preco_contabil_usd"))
            atrib_brl_str = f"R$ {custo_atrib_brl:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            atrib_usd_str = f"US$ {custo_atrib_usd:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            # Quantidade de novas ações geradas no evento
            q_recebida = q_final if ativo_diferente else (q_final - q_orig if ref_anterior else 0)

            # Formata o texto de transição (Moeda Dupla)
            texto_bônus = f"+{q_recebida:.4f} un".replace(".", ",")
            texto_bônus += f"\\nCusto Atribuído: {atrib_brl_str} | {atrib_usd_str}"

            # Texto de destino pós-cálculo real (Moeda Dupla)
            texto_destino = f"Qtd Acumulada: {q_final:.4f}".replace(".", ",")
            if f_fracao and f_fracao > 0:
                texto_destino += f" (Frac: {f_fracao:.4f})".replace(".", ",")
            texto_destino += f"\\nCusto Acumulado: {custo_final_formatado}"

    # --- 2. COM DADOS ESTIMADOS / RASCUNHO (SEM SÍMBOLO DE MOEDA) ---
    else:
        # Se for quantidade nova exata
        if modo_qtd_exata:
            qtd_str = f"{qtd_nova_exata:.4f}".replace(".", ",") if qtd_nova_exata % 1 != 0 else f"{int(qtd_nova_exata)}"
            texto_bônus = f"+{qtd_str} ações"
        else:
            fator_porcentagem = fator_bonus * 100 if fator_bonus < 1 else fator_bonus
            fator_pct_str = f"{fator_porcentagem:.2f}%".replace(".", ",") if fator_porcentagem % 1 != 0 else f"{int(fator_porcentagem)}%"
            texto_bônus = f"+{fator_pct_str} de Bônus"

        # Define a string de custo formatada para o rascunho sem nenhum símbolo
        if custo_unit_atribuído > 0:
            v_custo_formatado = f"{custo_unit_atribuído:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_bônus += f"\\nCusto Unit. Atribuído: {v_custo_formatado}/un"
            custo_destino_str = f"Qtd Gerada * {v_custo_formatado}" if ativo_diferente else f"Custo Anterior + (Qtd Gerada * {v_custo_formatado})"
        elif custo_total_atribuído > 0:
            v_custo_formatado = f"{custo_total_atribuído:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_bônus += f"\\nCusto Total Atribuído: {v_custo_formatado}"
            custo_destino_str = v_custo_formatado if ativo_diferente else f"Custo Anterior + {v_custo_formatado}"
        else:
            texto_bônus += f"\\nCusto Atribuído: 0,00 (Isento)"
            custo_destino_str = "0,00" if ativo_diferente else "Custo Anterior"

        # Ajusta a fórmula visual no nó de destino com o valor numérico estimado
        fator_str = f"{fator_bonus}".replace(".", ",")
        
        if ativo_diferente:
            if modo_qtd_exata:
                texto_destino = f"Nova Posição\\nQtd Gerada: {qtd_str} un\\nCusto: {custo_destino_str}"
            else:
                texto_destino = f"Nova Posição\\nQtd Gerada: qtd_base * {fator_str}\\nCusto: {custo_destino_str}"
        else:
            if modo_qtd_exata:
                texto_destino = f"Qtd Acumulada: qtd + {qtd_str}\\nCusto Acumulado: {custo_destino_str}"
            else:
                texto_destino = f"Qtd Acumulada: qtd * (1 + {fator_str})\\nCusto Acumulado: {custo_destino_str}"

    # --- 3. CONSTRUÇÃO DO GRAPHVIZ (DOT CODE) ---
    if ativo_diferente:
        dot_code = f"""
        digraph G {{
            rankdir=LR;
            node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
            edge [fontname="Arial", fontsize=9];

            Origem [label="📦 __TICKER_BASE__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_ORIGEM__", fillcolor="#E8F1F5", color="#1E3D59"];
            Manter [label="📦 __TICKER_BASE__\\nPosição Mantida\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_ORIGEM__", fillcolor="#F5F7FA", color="#64748B"];
            Destino [label="🟢 __TICKER_GERADO__\\n__TEXTO_FINAL__", fillcolor="#F0FDF4", color="#15803D", penwidth=2];
            
            Origem -> Manter [label=" Mantido", style=dashed, color="#64748B"];
            Origem -> Destino [label=" __TEXTO_BONUS__", style=bold, color="#15803D"];
        }}
        """
    else:
        dot_code = f"""
        digraph G {{
            rankdir=LR;
            node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
            edge [fontname="Arial", fontsize=9, color="#15803D"];

            Origem [label="📦 __TICKER_BASE__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_ORIGEM__", fillcolor="#E8F1F5", color="#1E3D59"];
            Destino [label="🟢 __TICKER_BASE__\\n__TEXTO_FINAL__", fillcolor="#F0FDF4", color="#15803D", penwidth=2];
            
            Origem -> Destino [label=" __TEXTO_BONUS__", style=bold];
        }}
        """

    # Substituições finais no DOT code
    dot_code = (dot_code
                .replace("__TICKER_BASE__", ticker_base_exibicao)
                .replace("__TICKER_GERADO__", ticker_gerado_exibicao)
                .replace("__QTD_ATUAL__", str(qtd_origem))
                .replace("__CUSTO_ORIGEM__", custo_origem_formatado)
                .replace("__TEXTO_FINAL__", texto_destino)
                .replace("__TEXTO_BONUS__", texto_bônus))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_leilao_fracoes(instrucoes: list, ticker_base: str, resultado=None):
    """
    Renderiza o fluxo contábil de Venda/Leilão de Frações.
    A lógica com resultado real permanece intacta. O fallback (sem resultado) estima
    o valor bruto, valor por cota ou o cálculo (valor por cota * quantidade).
    """
    if not instrucoes:
        return

    ticker_exibicao = formatar_ativo_visual(ticker_base)

    # --- FALLBACKS / VALORES PADRÃO ---
    qtd_origem = "qtd"
    custo_brl_origem = "custo_brl"
    custo_usd_origem = "custo_usd"
    
    # Captura parâmetros da instrução
    inst = instrucoes[0]
    valor_unit_fracao = inst.get("valor_caixa_cota_op", 0) or inst.get("valor_caixa", 0)
    qtd_fracao_manual = abs(sanitizar_numero(inst.get("qtd_delta"))) if "qtd_delta" in inst else None

    # --- 1. COM DADOS REAIS DO BACKEND (Mantido exatamente como estava) ---
    if resultado and len(resultado) >= 2:
        texto_caixa = f"Liquidação de Frações"
        if valor_unit_fracao > 0:
            texto_caixa += f"\\n(R$ {valor_unit_fracao:,.6f}/un)".replace(",", "v").replace(".", ",").replace("v", ".")

        texto_ajustado = "Qtd Final = Qtd - Frações Vendidas"

        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_brl_origem = f"R$ {c_brl_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_usd_origem = f"US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        ref_leilao = next((x for x in resultado if x.get("tipo") in ["FRAÇÃO", "VENDA_FRACOES", "LEILAO_FRACOES"]), None)
        if ref_leilao:
            q_final = sanitizar_numero(ref_leilao.get("quant_acum"))
            cb_final = sanitizar_numero(ref_leilao.get("custo_acum_brl"))
            cu_final = sanitizar_numero(ref_leilao.get("custo_acum_usd"))
            
            q_vendida = q_orig - q_final if ref_anterior else 0
            valor_recebido_total = ref_leilao.get("valor_total_caixa") or (q_vendida * valor_unit_fracao)

            texto_ajustado = f"Qtd Restante: {q_final:.4f}".replace(".", ",")
            texto_ajustado += f"\\nCusto: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_ajustado += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            texto_caixa = f"💵 Caixa (Rendimento)\\nRecebido: R$ {valor_recebido_total:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            if q_vendida > 0:
                texto_caixa += f"\\nVendidas: {q_vendida:.4f} un".replace(".", ",")

    # --- 2. COM DADOS ESTIMADOS / RASCUNHO (Fallback Ajustado) ---
    else:
        # Define a quantidade a ser exibida no rascunho
        qtd_str = f"{qtd_fracao_manual:.4f}".replace(".", ",") if qtd_fracao_manual else "qtd_venda"
        texto_ajustado = f"Qtd Final: Qtd - {qtd_str}\\nCusto: Custo Proporcional Baixado"

        # Captura o valor bruto se ele tiver sido informado diretamente no payload
        valor_bruto_direto = inst.get("valor_caixa", 0)

        # 1. Prioridade: Se houver valor bruto explícito (valor_caixa), exibe ele direto (sem multiplicar!)
        if valor_bruto_direto > 0:
            v_bruto_str = f"R$ {valor_bruto_direto:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado)\\nRecebido: {v_bruto_str}"
            if qtd_fracao_manual:
                texto_caixa += f"\\n(Liquidação de {qtd_str} un)"

        # 2. Segunda prioridade: Se tivermos valor por cota E quantidade, estimamos a multiplicação
        elif valor_unit_fracao > 0 and qtd_fracao_manual:
            valor_estimado = valor_unit_fracao * qtd_fracao_manual
            v_est_str = f"R$ {valor_estimado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            v_unit_str = f"R$ {valor_unit_fracao:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado)\\nRecebido: {v_est_str}\\n({qtd_str} un * {v_unit_str}/un)"

        # 3. Terceira prioridade: Se tivermos apenas o valor por cota
        elif valor_unit_fracao > 0:
            v_unit_str = f"R$ {valor_unit_fracao:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado)\\nRecebido: {qtd_str} * {v_unit_str}/un"

        # 4. Fallback genérico
        else:
            texto_caixa = f"💵 Caixa (Estimado)\\nRecebido: Valor Bruto"

    # --- 3. CONSTRUÇÃO DO GRAPHVIZ (DOT CODE) ---
    dot_code = f"""
    digraph G {{
        rankdir=LR;
        node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
        edge [fontname="Arial", fontsize=9, color="#17B890"];

        Origem [label="📦 __TICKER__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59"];
        Dest_Original [label="📉 __TICKER__\\nPosição Remanescente\\n__TEXTO_AJUSTADO__", fillcolor="#FDF2F2", color="#E53E3E"];
        Dest_Caixa [label="💵 Caixa (Venda Frac.)\\n__TEXTO_CAIXA__", fillcolor="#FEFCE8", color="#A16207"];

        Origem -> Dest_Original [label=" Baixa de Fração", style=dashed, color="#E53E3E"];
        Origem -> Dest_Caixa [label=" Crédito em Conta", color="#A16207"];
    }}
    """
    
    dot_code = (dot_code
                .replace("__TICKER__", ticker_exibicao)
                .replace("__QTD_ATUAL__", str(qtd_origem))
                .replace("__CUSTO_BRL_O__", custo_brl_origem)
                .replace("__CUSTO_USD_O__", custo_usd_origem)
                .replace("__TEXTO_AJUSTADO__", texto_ajustado)
                .replace("__TEXTO_CAIXA__", texto_caixa))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_opa(instrucoes: list, ticker_base: str, resultado=None):
    """
    Renderiza o fluxo contábil de OPA (Oferta Pública de Aquisição) / Alienação Total.
    Trata de forma limpa os cenários de valor bruto (valor_caixa) e valor por cota (valor_caixa_cota_op).
    """
    if not instrucoes:
        return

    ticker_exibicao = formatar_ativo_visual(ticker_base)

    # --- FALLBACKS / VALORES PADRÃO ---
    qtd_origem = "qtd"
    custo_brl_origem = "custo_brl"
    custo_usd_origem = "custo_usd"
    
    # Captura parâmetros da instrução de OPA
    inst = instrucoes[0]
    valor_unit_opa = inst.get("valor_caixa_cota_op", 0)
    valor_bruto_opa = inst.get("valor_caixa", 0)
    
    # qtd_fator_delta ou qtd_delta costuma vir negativo para indicar a saída
    qtd_alienada_manual = abs(sanitizar_numero(inst.get("qtd_fator_delta") or inst.get("qtd_delta", 0)))

    texto_caixa = "Liquidação via OPA"
    texto_ajustado = "Qtd Final = Qtd - Ativos Alienados"

    # --- 1. COM DADOS REAIS DO BACKEND ---
    if resultado and len(resultado) >= 2:
        val_referencia_unit = valor_unit_opa or valor_bruto_opa
        texto_caixa = f"Liquidação via OPA"
        if val_referencia_unit > 0:
            texto_caixa += f"\\n(R$ {val_referencia_unit:,.6f}/un)".replace(",", "v").replace(".", ",").replace("v", ".")

        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_brl_origem = f"R$ {c_brl_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_usd_origem = f"US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        ref_opa = next((x for x in resultado if x.get("tipo") in ["OPA", "ALIENACAO", "ALIENACAO_TOTAL"]), None)
        if ref_opa:
            q_final = sanitizar_numero(ref_opa.get("quant_acum"))
            cb_final = sanitizar_numero(ref_opa.get("custo_acum_brl"))
            cu_final = sanitizar_numero(ref_opa.get("custo_acum_usd"))
            
            q_vendida = q_orig - q_final if ref_anterior else 0
            valor_recebido_total = ref_opa.get("valor_total_caixa") or (q_vendida * val_referencia_unit)

            texto_ajustado = f"Qtd Restante: {q_final:.4f}".replace(".", ",")
            texto_ajustado += f"\\nCusto: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_ajustado += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            texto_caixa = f"💵 Caixa (Rendimento)\\nRecebido: R$ {valor_recebido_total:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            if q_vendida > 0:
                texto_caixa += f"\\nAlienadas: {q_vendida:.4f} un".replace(".", ",")

    # --- 2. COM DADOS ESTIMADOS / RASCUNHO (Fallback Corrigido) ---
    else:
        # Se o fator for -1, significa que é uma baixa total (100% da posição)
        eh_baixa_total = (inst.get("qtd_fator_delta") == -1 or inst.get("qtd_delta") == -1)

        if eh_baixa_total:
            qtd_str = "(100%)un."
            texto_ajustado = "Qtd Final: 0 (Baixa Total)\\nCusto: Baixa Total (100%)"
        else:
            # Caso seja uma OPA parcial com quantidade física nominal informada
            qtd_str = f"{qtd_alienada_manual:.4f}".replace(".", ",") if qtd_alienada_manual > 0 else "qtd_alienada"
            texto_ajustado = f"Qtd Final: Qtd - {qtd_str}\\nCusto: Custo Proporcional Baixado"

        valor_bruto_opa = inst.get("valor_caixa", 0)

        # 1. Prioridade: Valor Bruto (valor_caixa)
        if valor_bruto_opa > 0:
            v_bruto_str = f"R$ {valor_bruto_opa:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado OPA)\\nRecebido: {v_bruto_str}"
            if eh_baixa_total:
                texto_caixa += "\\n(Alienação de toda a posição)"
            elif qtd_alienada_manual > 0:
                texto_caixa += f"\\n(Alienação de {qtd_str} un)"

        # 2. Segunda prioridade: Estimativa (Unitário * Quantidade) - Só faz sentido se não for o fator genérico -1
        elif valor_unit_opa > 0 and qtd_alienada_manual > 0 and not eh_baixa_total:
            valor_estimado = valor_unit_opa * qtd_alienada_manual
            v_est_str = f"R$ {valor_estimado:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            v_unit_str = f"R$ {valor_unit_opa:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado OPA)\\nRecebido: {v_est_str}\\n({qtd_str} un * {v_unit_str}/un)"

        # 3. Terceira prioridade: Valor Unitário por cota (mostra a fórmula implícita)
        elif valor_unit_opa > 0:
            v_unit_str = f"R$ {valor_unit_opa:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa = f"💵 Caixa (Estimado OPA)\\nRecebido: {qtd_str} * {v_unit_str}/un"

        # 4. Fallback Geral
        else:
            texto_caixa = "💵 Caixa (Estimado OPA)\\nRecebido: Valor de Alienação"

    # --- 3. CONSTRUÇÃO DO GRAPHVIZ (DOT CODE) ---
    dot_code = f"""
    digraph G {{
        rankdir=LR;
        node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
        edge [fontname="Arial", fontsize=9, color="#EF4444"];

        Origem [label="📦 __TICKER__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59"];
        Dest_Original [label="📉 __TICKER__\\nPosição Remanescente\\n__TEXTO_AJUSTADO__", fillcolor="#FDF2F2", color="#EF4444"];
        Dest_Caixa [label="💵 Caixa (Liquidação OPA)\\n__TEXTO_CAIXA__", fillcolor="#FEFCE8", color="#A16207"];

        Origem -> Dest_Original [label=" Saída de Ativos", style=dashed, color="#EF4444"];
        Origem -> Dest_Caixa [label=" Crédito (Alienação)", color="#A16207"];
    }}
    """
    
    dot_code = (dot_code
                .replace("__TICKER__", ticker_exibicao)
                .replace("__QTD_ATUAL__", str(qtd_origem))
                .replace("__CUSTO_BRL_O__", custo_brl_origem)
                .replace("__CUSTO_USD_O__", custo_usd_origem)
                .replace("__TEXTO_AJUSTADO__", texto_ajustado)
                .replace("__TEXTO_CAIXA__", texto_caixa))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_reducao_capital(instrucoes: list, ticker_base: str, resultado=None):
    """
    Renderiza o fluxo contábil de Redução/Restituição de Capital.
    O custo do ativo base é reduzido e o dinheiro é creditado no caixa, 
    sem alterar a quantidade de cotas.
    """
    if not instrucoes:
        return

    ticker_exibicao = formatar_ativo_visual(ticker_base)

    # --- FALLBACKS / VALORES PADRÃO ---
    qtd_origem = "qtd"
    custo_brl_origem = "custo_brl"
    custo_usd_origem = "custo_usd"

    inst = instrucoes[0]
    valor_unit_reduc = abs(inst.get("valor_caixa_cota_com", 0))
    valor_bruto_reduc = abs(inst.get("valor_caixa", 0))
    texto_ajustado = ""
    # --- 1. COM DADOS REAIS DO BACKEND ---
    if resultado and len(resultado) >= 2:
        val_referencia_unit = valor_unit_reduc or valor_bruto_reduc
        texto_caixa = "💵 Caixa (Redução de Capital)"
        
        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_brl_origem = f"R$ {c_brl_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_usd_origem = f"US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        ref_reduc = next((x for x in resultado if x.get("tipo") in ["REDUÇÃO DE CAPITAL"]), None)
        if ref_reduc:
            q_final = sanitizar_numero(ref_reduc.get("quant_acum"))
            cb_final = sanitizar_numero(ref_reduc.get("custo_acum_brl"))
            cu_final = sanitizar_numero(ref_reduc.get("custo_acum_usd"))
            
            valor_recebido_total_brl = -sanitizar_numero(ref_reduc.get("preco_contabil_brl"))
            valor_recebido_total_usd = -sanitizar_numero(ref_reduc.get("preco_contabil_usd"))

            # Quantidade permanece idêntica
            texto_ajustado = f"Qtd Mantida: {q_final:.4f}".replace(".", ",")
            texto_ajustado += f"\\nCusto Reduzido: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_ajustado += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            texto_caixa = f"💵 Caixa\\nRecebido: R$ {valor_recebido_total_brl:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_caixa += f" | US$ {valor_recebido_total_usd:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    # --- 2. COM DADOS ESTIMADOS / RASCUNHO (PRÉVIA SEM RESULTADO) ---
    else:

        # 1. Prioridade: Valor Bruto direto (valor_caixa)
        if valor_bruto_reduc > 0:
            # Na redução de capital a quantidade NÃO muda!
            v_bruto_str = f"R$ {valor_bruto_reduc:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_ajustado = f"Qtd Mantida: qtd\\nCusto: Custo - {v_bruto_str}"
            texto_caixa = f"💵 Caixa (Redução de Capital)\\nRecebido: {v_bruto_str}"

        # 2. Segunda prioridade: Valor Unitário por cota (valor_caixa_cota_com)
        elif valor_unit_reduc > 0:
            # Na redução de capital a quantidade NÃO muda!
            v_unit_str = f"R$ {valor_unit_reduc:,.4f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_ajustado = f"Qtd Mantida: qtd\\nCusto: Custo - qtd * {v_unit_str}/un"
            texto_caixa = f"💵 Caixa (Redução de Capital)\\nRecebido: qtd * {v_unit_str}/un"

        # 3. Fallback Geral
        else:
            texto_caixa = "💵 Caixa (Redução de Capital)\\nRecebido: Valor restituído"
            texto_ajustado =f"Qtd Mantida: qtd\\nCusto: Custo - Valor recebido"

    # --- 3. CONSTRUÇÃO DO GRAPHVIZ (DOT CODE) ---
    # Usamos cores azuis/verdes normais pois não há "saída/baixa" de ativos da carteira, apenas ajuste de custo
    dot_code = f"""
    digraph G {{
        rankdir=LR;
        node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
        edge [fontname="Arial", fontsize=9, color="#17B890"];

        Origem [label="📦 __TICKER__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59"];
        Dest_Original [label="📉 __TICKER__\\nPosição Atualizada\\n__TEXTO_AJUSTADO__", fillcolor="#F0FDF4", color="#16A34A"];
        Dest_Caixa [label="__TEXTO_CAIXA__", fillcolor="#FEFCE8", color="#A16207"];

        Origem -> Dest_Original [label=" Abatimento de Custo", color="#16A34A"];
        Origem -> Dest_Caixa [label=" Crédito em Conta", color="#A16207"];
    }}
    """
    
    dot_code = (dot_code
                .replace("__TICKER__", ticker_exibicao)
                .replace("__QTD_ATUAL__", str(qtd_origem))
                .replace("__CUSTO_BRL_O__", custo_brl_origem)
                .replace("__CUSTO_USD_O__", custo_usd_origem)
                .replace("__TEXTO_AJUSTADO__", texto_ajustado)
                .replace("__TEXTO_CAIXA__", texto_caixa))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_atualizacao(instrucoes: list, ticker_base: str, ticker_gerado: str = None, resultado=None):
    """
    Renderiza o fluxo contábil de Conversão ou Atualização de Ativo (troca de ticker/incorporação).
    O custo total (100%) da posição antiga é migrado para o novo ativo gerado,
    e a nova quantidade é gerada com base em Fator % ou Qtd Nova Exata.
    """
    if not instrucoes or not ticker_gerado:
        return

    ticker_antigo_exibicao = formatar_ativo_visual(ticker_base)
    ticker_novo_exibicao = formatar_ativo_visual(ticker_gerado)

    # --- FALLBACKS / VALORES PADRÃO ---
    qtd_origem = "qtd"
    custo_brl_origem = "custo_brl"
    custo_usd_origem = "custo_usd"

    # Procuramos a instrução do ativo gerado (nova entrada) e do ativo base (saída)
    inst_novo = next((x for x in instrucoes if x.get("ticker") == ticker_gerado), instrucoes[0])
    
    modo_fator = "qtd_fator_delta" in inst_novo
    fator_delta = inst_novo.get("qtd_fator_delta", 0)
    qtd_nova_exata = inst_novo.get("qtd_nova", 0)

    # --- 1. COM DADOS REAIS DO BACKEND ---
    if resultado and len(resultado) >= 2:
        # Busca referências no resultado processado
        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_brl_origem = f"R$ {c_brl_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            custo_usd_origem = f"US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        # Busca a linha da conversão no resultado para obter valores finais calculados
        ref_atualizacao = next((x for x in resultado if x.get("tipo") in ["ATUALIZAÇÃO"]), None)
        if ref_atualizacao:
            q_final = sanitizar_numero(ref_atualizacao.get("quant_acum"))
            cb_final = sanitizar_numero(ref_atualizacao.get("custo_acum_brl"))
            cu_final = sanitizar_numero(ref_atualizacao.get("custo_acum_usd"))

            texto_antigo_ajustado = "Qtd Final: 0 (Baixa Total)\\nCusto: Baixa Total (Migrado 100%)"
            
            texto_novo_ajustado = f"Qtd Gerada: {q_final:.4f}".replace(".", ",")
            texto_novo_ajustado += f"\\nCusto Incorporado: R$ {cb_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            texto_novo_ajustado += f" | US$ {cu_final:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

    # --- 2. COM DADOS ESTIMADOS / RASCUNHO (PRÉVIA SEM RESULTADO) ---
    else:
        texto_antigo_ajustado = "Qtd Final: 0 (Baixa Total)\\nCusto: Baixa Total (Migrado 100%)"

        if modo_fator:
            fator_porcentagem = fator_delta * 100
            fator_str = f"{fator_porcentagem:.2f}%".replace(".", ",") if fator_porcentagem % 1 != 0 else f"{int(fator_porcentagem)}%"
            texto_novo_ajustado = f"Qtd Gerada: qtd_anterior * {fator_str}\\nCusto: 100% do Custo Origem"
        else:
            qtd_str = f"{qtd_nova_exata:.4f}".replace(".", ",") if qtd_nova_exata > 0 else "qtd_nova"
            texto_novo_ajustado = f"Qtd Gerada: {qtd_str} un\\nCusto: 100% do Custo Origem"

    # --- 3. CONSTRUÇÃO DO GRAPHVIZ (DOT CODE) ---
    # Nós usamos cores de transição limpa (azul para vermelho indicando a baixa, e verde para o novo ativo gerado)
    dot_code = f"""
    digraph G {{
        rankdir=LR;
        node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
        edge [fontname="Arial", fontsize=9];

        Origem [label="📦 __TICKER_ANTIGO__\\nPosição Original\\nQtd: __QTD_ATUAL__\\nCusto: __CUSTO_BRL_O__ | __CUSTO_USD_O__", fillcolor="#E8F1F5", color="#1E3D59"];
        Dest_Antigo [label="📉 __TICKER_ANTIGO__\\nPosição Antiga\\n__TEXTO_ANTIGO_AJUSTADO__", fillcolor="#FDF2F2", color="#EF4444"];
        Dest_Novo [label="📈 __TICKER_NOVO__\\nNova Posição\\n__TEXTO_NOVO_AJUSTADO__", fillcolor="#F0FDF4", color="#16A34A"];

        Origem -> Dest_Antigo [label=" Encerramento", style=dashed, color="#EF4444"];
        Origem -> Dest_Novo [label=" Migração de Custo (100%)", color="#16A34A", penwidth=1.5];
    }}
    """
    
    dot_code = (dot_code
                .replace("__TICKER_ANTIGO__", ticker_antigo_exibicao)
                .replace("__TICKER_NOVO__", ticker_novo_exibicao)
                .replace("__QTD_ATUAL__", str(qtd_origem))
                .replace("__CUSTO_BRL_O__", custo_brl_origem)
                .replace("__CUSTO_USD_O__", custo_usd_origem)
                .replace("__TEXTO_ANTIGO_AJUSTADO__", texto_antigo_ajustado)
                .replace("__TEXTO_NOVO_AJUSTADO__", texto_novo_ajustado))

    st.graphviz_chart(dot_code)

def _renderizar_fluxograma_cisao_incorporacao(tipo_evento: str, instrucoes: list, ticker_base: str, ticker_gerado: str, resultado=None):
    """
    Renderiza o fluxo contábil para os 5 cenários de Cisão e Incorporação.
    
    COMPORTAMENTO:
      - Com Resultado (Backend): Mostra os valores exatos em moedas reais (R$ e US$) para posições originais e finais.
      - Sem Resultado (Rascunho): Mostra os valores inseridos de forma genérica e limpa, sem símbolos monetários.
    """
    if not instrucoes or not ticker_base or not ticker_gerado:
        return

    ticker_base_exibicao = formatar_ativo_visual(ticker_base)
    ticker_gerado_exibicao = formatar_ativo_visual(ticker_gerado)

    # Identificar a tributação a partir das instruções
    inst_cx = next((x for x in instrucoes if x.get("ticker") == "DINHEIRO_CAIXA"), None)
    tipo_tributacao = "AJUSTE_CONTABIL"
    if inst_cx:
        tipo_tributacao = inst_cx.get("tipo_tributacao", "RETIDO_FONTE")

    # --- PARSE DE VALORES DA INSTRUÇÃO (RASCUNHO / PREVIA) ---
    inst_m = next((x for x in instrucoes if x.get("ticker") == ticker_base), {})
    inst_f = next((x for x in instrucoes if x.get("ticker") == ticker_gerado), {})

    # Captura proporção/valor de redução da Mãe
    reducao_mae_val = inst_m.get("proporcao_custo") or inst_m.get("custo_delta") or 0.0
    reducao_mae_str = f"{abs(reducao_mae_val) * 100:.2f}%".replace(".", ",") if "proporcao_custo" in inst_m else f"{abs(reducao_mae_val):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

    # Captura quantidade/fator gerado no Filho
    qtd_gerada_val = inst_f.get("qtd_delta") or inst_f.get("qtd_fator_delta") or 0.0
    is_fator_q = "qtd_fator_delta" in inst_f
    if is_fator_q:
        qtd_gerada_str = f"{abs(qtd_gerada_val) * 100:.2f}% qtd_base".replace(".", ",")
    else:
        qtd_gerada_str = f"{abs(qtd_gerada_val):.2f}".replace(".", ",")

    # Captura custo atribuído ao Filho
    custo_filho_val = (inst_f.get("valor_cota_op") or inst_f.get("valor_cota_com") or inst_f.get("valor") or 
                       inst_f.get("proporcao_custo")  or inst_f.get("custo_delta") or 0.0)
    if "valor" in inst_f:
        custo_filho_str = f"{custo_filho_val:.2f}".replace(".", ",")
    elif "valor_cota_op" in inst_f:
        custo_filho_str = f"{custo_filho_val:,.2f}/un".replace(",", "v").replace(".", ",").replace("v", ".")
    elif "valor_cota_com" in inst_f:
        custo_filho_str = f"{custo_filho_val:,.2f}/qt_base".replace(",", "v").replace(".", ",").replace("v", ".")
    elif "proporcao_custo" in inst_f:
        custo_filho_str = f"{custo_filho_val*100:,.2f}%".replace(",", "v").replace(".", ",").replace("v", ".")
    elif "custo_delta" in inst_f:
        custo_filho_str = f"{custo_filho_val:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    else:
        custo_filho_str = "0.0"

    # --- MONTAGEM DOS DADOS REAIS DO BACKEND (DUAS MOEDAS) ---
    if resultado and len(resultado) >= 2:
        ref_anterior = next((x for x in resultado if x.get("tipo") == "REFERENCIA_ANTERIOR"), None)
        
        # Posição Original da Mãe
        qtd_origem = "0"
        custo_origem_formatado = "R$ 0,00 | US$ 0,00"
        if ref_anterior:
            q_orig = sanitizar_numero(ref_anterior.get('quant_acum'))
            qtd_origem = f"{q_orig:.4f}".replace(".", ",")
            c_brl_orig = sanitizar_numero(ref_anterior.get("custo_acum_brl"))
            c_usd_orig = sanitizar_numero(ref_anterior.get("custo_acum_usd"))
            custo_origem_formatado = f"R$ {c_brl_orig:,.2f} | US$ {c_usd_orig:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

        # Nova Posição da Mãe (Somente para Cisão, na Incorporação ela deixa de existir)
        ref_mae_final = next((x for x in resultado if x.get("tipo") == tipo_evento and x.get("ticker") == ticker_base), None)
        if ref_mae_final and tipo_evento == "CISÃO":
            q_m_f = sanitizar_numero(ref_mae_final.get("quant_acum"))
            cb_m_f = sanitizar_numero(ref_mae_final.get("custo_acum_brl"))
            cu_m_f = sanitizar_numero(ref_mae_final.get("custo_acum_usd"))
            
            texto_mae_final = (
                f"Qtd Acumulada: {q_m_f:.4f}\\n"
                f"Custo Acumulado: R$ {cb_m_f:,.2f} | US$ {cu_m_f:,.2f}"
            ).replace(".", ",").replace("v", ".")
        else:
            texto_mae_final = "Posição Encerrada\\nCusto: R$ 0,00 | US$ 0,00"

        # Nova Posição do Filho
        ref_filho_final = next((x for x in resultado if x.get("tipo") == tipo_evento and x.get("ticker") == ticker_gerado), None)
        if ref_filho_final:
            q_f_f = sanitizar_numero(ref_filho_final.get("quant_acum"))
            cb_f_f = sanitizar_numero(ref_filho_final.get("custo_acum_brl"))
            cu_f_f = sanitizar_numero(ref_filho_final.get("custo_acum_usd"))
            
            texto_filho_final = (
                f"Qtd Acumulada: {q_f_f:.4f}\\n"
                f"Custo Acumulado: R$ {cb_f_f:,.2f} | US$ {cu_f_f:,.2f}"
            ).replace(".", ",").replace("v", ".")
        else:
            texto_filho_final = "Custo Transferido"

        # Se houver caixa recebido
        texto_caixa_final = ""
        if inst_cx:
            rend_brl = next((x.get("rend_trib_excl", 0) for x in resultado if x.get("moeda") == "BRL"), 0)
            rend_usd = next((x.get("rend_trib_excl", 0) for x in resultado if x.get("moeda") == "USD"), 0)
            texto_caixa_final = f"Rendimento Isento/Retido:\\nR$ {rend_brl:,.2f} | US$ {rend_usd:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

    # --- MONTAGEM DA PRÉVIA / RASCUNHO (SEM SÍMBOLO DE MOEDA) ---
    else:
        qtd_origem = "qtd_base"
        custo_origem_formatado = "custo_base"

        if tipo_evento == "CISÃO":
            texto_mae_final = f"Qtd Mantida\\nCusto Reduzido em: {reducao_mae_str}"
        else:
            texto_mae_final = f"Posição Encerrada\\nCusto Reduzido: 100%"

        # Definição conceitual do Filho no Rascunho
        texto_filho_final = f"Nova Posição\\nQtd Recebida: {qtd_gerada_str}\\nCusto Recebido: {custo_filho_str}"

        # Se houver dinheiro no caixa
        texto_caixa_final = ""
        if inst_cx:
            v_caixa = inst_cx.get("valor_caixa") or inst_cx.get("valor_caixa_cota_com") or 0.0
            if "valor_caixa_cota_com" in inst_cx:
                v_caixa_str = f"{v_caixa:,.2f}/un".replace(",", "v").replace(".", ",").replace("v", ".")
            else:
                v_caixa_str = f"{v_caixa:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            v_cota = inst_cx.get("valor") or inst_cx.get("valor_cota_com") or 0.0
            if "valor_cota_com" in inst_cx:
                v_cota_str = f"{v_cota:,.2f}/un".replace(",", "v").replace(".", ",").replace("v", ".")
            else:
                v_cota_str = f"{v_cota:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
            
            prop_c = inst_cx.get("proporcao_custo") or inst_cx.get("custo_delta") or 0.0
            if "proporcao_custo" in inst_cx:
                prop_c_str = f"{abs(prop_c*100):,.2f}% custo_base".replace(",", "v").replace(".", ",").replace("v", ".")
            else:
                prop_c_str = f"{abs(prop_c):,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")

            if tipo_tributacao == "RETIDO_FONTE":
                texto_caixa_final = f"Dinheiro Bruto: {v_caixa_str}\nLucro: {v_cota_str} + {v_caixa_str} - {prop_c_str}\nImposto retido na fonte: 20% * Lucro\nValor liquido: {v_caixa_str} - Imposto"
            elif tipo_tributacao == "APURACAO_DARF":
                # Mostra o valor que foi para a "Venda"/DARF
                texto_caixa_final = f"Valor em Caixa: {v_caixa_str}\\nCusto p/ Apuração: {prop_c_str}\nLucro: {v_caixa_str} - {prop_c_str}"

    # --- CONSTRUÇÃO DO CÓDIGO DOT DO GRAPHVIZ ---
    # Define se exibe ou não o nó de caixa
    tem_caixa_node = (tipo_tributacao in ["RETIDO_FONTE", "APURACAO_DARF"])

    dot_code = f"""
    digraph G {{
        rankdir=LR;
        node [shape=box, style="filled,rounded", color="#1E3D59", fillcolor="#F5F7FA", fontname="Arial", fontsize=10];
        edge [fontname="Arial", fontsize=9];

        // Nós principais
        Origem [label="📦 {ticker_base_exibicao}\\nPosição Original\\nQtd: {qtd_origem}\\nCusto: {custo_origem_formatado}", fillcolor="#E8F1F5", color="#1E3D59"];
        
        MãeDestino [label="📦 {ticker_base_exibicao}\\n{texto_mae_final}", fillcolor="#F8FAFC", color="#64748B"];
        FilhoDestino [label="🟢 {ticker_gerado_exibicao}\\n{texto_filho_final}", fillcolor="#F0FDF4", color="#15803D", penwidth=2];
        
        Origem -> MãeDestino [label=" Evento Contábil", style=dashed, color="#64748B"];
        Origem -> FilhoDestino [label=" Gerado ({qtd_gerada_str})", style=bold, color="#15803D"];
    """

    if tem_caixa_node:
        dot_code += f"""
        CaixaDestino [label="🪙 DINHEIRO EM CAIXA\\n{texto_caixa_final}", fillcolor="#FEFCE8", color="#CA8A04", penwidth=1.5];
        Origem -> CaixaDestino [label=" {tipo_tributacao.replace('_', ' ')}", style=bold, color="#CA8A04"];
        """

    dot_code += "\n}"

    st.graphviz_chart(dot_code)
# (Adicione aqui as outras funções auxiliares privadas para bonificação, OPA, etc.)