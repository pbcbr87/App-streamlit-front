import streamlit as st
import pandas as pd
import requests
from settings import API_URL
from plotly import graph_objects as go



# --- 1. FUNÇÕES DE APOIO ---
def st_number_input_custom(label, value=None, key=None, placeholder="0,00"):
    def converter_valor_br(texto):
        if not texto:
            return 0.0
        try:
            # Tratamento robusto: remove ponto de milhar e troca vírgula por ponto
            limpo = str(texto).replace(".", "").replace(",", ".")
            return float(limpo)
        except ValueError:
            return None
    if value is not None:
        value = str(value)
    entrada = st.text_input(label, value=value, placeholder=placeholder, key=key)
    valor_numerico = converter_valor_br(entrada)
    return valor_numerico

@st.cache_data(ttl=600)
def get_categorias_usuario():
    user_id = st.session_state.get("id")
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{API_URL}carteira/pegar_carteira/{user_id}", headers=headers)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            return sorted(df['categoria'].unique().tolist()) if not df.empty else []
        return []
    except: return []

def post_aporte_etapa1(user_id, payload):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(f"{API_URL}carteira/aporte_etapa1/{user_id}", json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        st.error(f"Erro {response.status_code}: {response.text}")
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def post_aporte_etapa2(user_id, payload):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(f"{API_URL}carteira/aporte_etapa2/{user_id}", json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        st.error(f"Erro {response.status_code}: {response.text}")
        return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

def widget_aporte_global():
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.5, 1, 2])
        with c1:
            v_aporte = st_number_input_custom("Aporte", value="10.000", key="val_final")
        with c2:
            # moeda = st.selectbox("Moeda", ["BRL", "USD"])
            moeda = st.radio('Moeda',['BRL', 'USD'], horizontal=True)
        with c3:
            st.write("") 
            with st.popover("➕ Criar Grupo", width="stretch"):
                
                sel_cats = st.pills("Selecione Categorias", selection_mode="multi", options=st.session_state['page_aportes']['categorias_disponiveis'])
                if st.button("Confirmar Agrupamento", width="stretch"):
                    if sel_cats:
                        # Remove categorias selecionadas de outros grupos existentes
                        nova_lista = []
                        for g in st.session_state['page_aportes']['lista_grupos']:
                            cats_restantes = [c for c in g['cats'] if c not in sel_cats]
                            if cats_restantes:
                                nova_lista.append({"cats": cats_restantes, "min": g['min'], "max": g['max']})
                        
                        nova_lista.append({"cats": sel_cats, "min": "5,00", "max": "50,00"})
                        st.session_state['page_aportes']['lista_grupos'] = nova_lista
                        st.rerun()
    return v_aporte, moeda

def widget_config_categorias(v_aporte, moeda):
    """
    Renderiza os cards de configuração e retorna o payload pronto para a Etapa 1.
    """
    st.write("### 🛠️ Configuração de Limites do Aporte")
    
    # Referência curta para o namespace da página
    state = st.session_state['page_aportes']
    configuracoes_grupos = []

    # Verifica se a lista existe dentro do nosso dicionário de página
    if state.get('lista_grupos'):
        # Criamos as colunas baseadas na quantidade de grupos
        cols = st.columns(len(state['lista_grupos']))

        for idx, grupo in enumerate(state['lista_grupos']):
            with cols[idx]:
                with st.container(border=True):
                    # --- Cabeçalho e Exclusão ---
                    c_tit, c_del = st.columns([4, 1])
                    c_tit.markdown(f"**{' + '.join(grupo['cats'])}**")
                    
                    if c_del.button("✕", key=f"del_grp_{idx}", help="Remover grupo"):
                        state['lista_grupos'].pop(idx)
                        st.rerun()

                    # --- Inputs de Percentual ---
                    c_min, c_max = st.columns(2)
                    with c_min:
                        # Atualizamos o dicionário interno do grupo no state
                        v_min_float = st_number_input_custom(
                            "% Mín", value=grupo['min'], key=f"min_in_{idx}"
                        )
                        state['lista_grupos'][idx]['min_f'] = v_min_float
                    
                    with c_max:
                        v_max_float = st_number_input_custom(
                            "% Máx", value=grupo['max'], key=f"max_in_{idx}"
                        )
                        state['lista_grupos'][idx]['max_f'] = v_max_float

                    # --- Construção do payload técnico ---
                    configuracoes_grupos.append({
                        "categorias": grupo['cats'],
                        "margem_minima": v_min_float,
                        "margem_maxima": v_max_float
                    })

    # Retorna o Payload Completo estruturado
    return {
        "valor_total_aporte": v_aporte,
        "moeda": moeda,
        "configuracao_grupos": configuracoes_grupos
    }

def widget_resultado_grupo(dados):
    if not dados:
        return
    
    def converter_limpo(valor):
        """Converte strings formatadas ('35.71%', '618076.57') para float puro."""
        if isinstance(valor, (int, float)): 
            return float(valor)
        try:
            # Remove símbolos comuns e ajusta padrão de pontuação
            limpo = str(valor).replace('%', '').replace('R$', '').replace('$', '').strip()
            # Se houver vírgula e ponto, assume padrão BR (milhar.decimal,vírgula)
            if ',' in limpo and '.' in limpo:
                limpo = limpo.replace('.', '').replace(',', '.')
            # Se houver apenas vírgula, troca por ponto
            elif ',' in limpo:
                limpo = limpo.replace(',', '.')
            return float(limpo)
        except:
            return 0.0

    df_list = []
    for item in dados:
        # Extração convertendo strings da API para números reais
        # Dividimos por 100 os percentuais que vem como "35.71" para usar o format "{:.1%}"
        df_list.append({
            "Grupo": item["grupo"],
            "Meta": converter_limpo(item["meta_estrategica"]) / 100,
            "Atual %": converter_limpo(item["percentual_atual"]) / 100,
            "Defasagem %": converter_limpo(item["percentual_defasagem"]) / 100,
            "Valor Planejado": converter_limpo(item["brl"]["valor_objetivo"]),
            "Valor Atual": converter_limpo(item["brl"]["valor_atual"]),
            "Defasagem Financeira": converter_limpo(item["brl"]["defasagem_financeira"]),
            "Valor Aporte": converter_limpo(item["brl"]["valor_aporte"]),
            "Aporte %": converter_limpo(item["percentual_no_aporte"]) / 100,
            # Colunas de suporte (ocultas)
            "_num_defasagem": converter_limpo(item["brl"]["defasagem_financeira"]),
            "_val_atual_brl": converter_limpo(item["brl"]["valor_atual"]),
            "_val_obj_brl": converter_limpo(item["brl"]["valor_objetivo"])
        })

    df = pd.DataFrame(df_list)
    df = df.sort_values(by="Aporte %", ascending=False)
    
    # --- 1. Gráfico de Barras ---
    st.subheader("📊 Comparativo Visual: Atual vs Planejado")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Grupo"], y=df["_val_atual_brl"], name='Atual (BRL)', marker_color='#1E88E5'))
    fig.add_trace(go.Bar(x=df["Grupo"], y=df["_val_obj_brl"], name='Planejado (BRL)', marker_color='#FFA000'))
    fig.update_layout(barmode='group', height=350, template="plotly_white", margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig, width="stretch")

    # --- 2. Tabela Detalhada (Padrão Styler) ---
    st.subheader("📋 Detalhamento da Estratégia")

    def aplicar_cores_estrategia(row):
        # 1. Lógica para Defasagem (Texto Colorido)
        cor_defasagem = 'color: #D32F2F' if row['Defasagem Financeira'] < 0 else 'color: #388E3C'
        
        # 2. Lógica para Valor Aporte (Fundo Verde Suave se houver aporte)
        # Usamos uma cor de fundo (background) para dar destaque
        bg_aporte = 'background-color: rgba(0, 255, 0, 0.1); font-weight: bold' if row['Valor Aporte'] > 0 else ''
        
        estilos = [''] * len(row)
        
        # Aplicando os estilos nos índices corretos
        estilos[3] = cor_defasagem  # Defasagem %
        estilos[6] = cor_defasagem  # Defasagem Financeira
        estilos[7] = bg_aporte      # Valor Aporte (Destaque verde)
        
        return estilos

    
    colunas_visiveis = [
        "Grupo", "Meta", "Atual %", "Defasagem %", 
        "Valor Planejado", "Valor Atual", "Defasagem Financeira", 
        "Valor Aporte", "Aporte %"
    ]
   
    # 2. Resetamos o índice para garantir que o st.table não tente inventar um índice visual
    df_pre_styled = df[colunas_visiveis]
    # Criando o Styler seguindo seu padrão de ativos
    # 3. Aplicamos o Styler
    df_styled = (
        df_pre_styled.style.apply(aplicar_cores_estrategia, axis=1)
        .format({
            "Meta": "{:.2%}",
            "Atual %": "{:.2%}",
            "Defasagem %": "{:+.2%}",
            "Valor Planejado": "R$ {:,.2f}",
            "Valor Atual": "R$ {:,.2f}",
            "Defasagem Financeira": "R$ {:,.2f}",
            "Valor Aporte": "R$ {:,.2f}",
            "Aporte %": "{:.2%}"
        }, decimal=',', thousands='.')
    )

    st.table(df_styled, width="stretch", hide_index=True)

def widget_config_ativos(dist, moeda_padrao="BRL"):
    """
    Renderiza os cards de ajuste fino por grupo e retorna o payload para a Etapa 2.
    """
    st.write("### ⚙️ Aportes por Grupo")

    # 1. Inicialização da memória de moedas por grupo
    state = st.session_state['page_aportes'] # Referência ao namespace
    if not state.get('moedas_por_grupo'):
        state['moedas_por_grupo'] = {item['grupo']: moeda_padrao.upper() for item in dist}

    payload_etapa2_dist = []
    
    if dist:
        # Criamos o grid de colunas baseado na quantidade de grupos
        cols = st.columns(len(dist))

        for idx, item in enumerate(dist):
            nome_exibicao = item.get("grupo")
            
            with cols[idx]:
                with st.container(border=True):
                    # --- LINHA SUPERIOR: TÍTULO E SELECT DE MOEDA ---
                    c_tit, c_moeda = st.columns([3, 3])
                    c_tit.markdown(f"**{nome_exibicao}**")
                    
                    # Recupera a moeda atual deste grupo na memória
                    moeda_salva = state['moedas_por_grupo'].get(nome_exibicao, moeda_padrao.upper())
                    
                    chave_moeda = f"sel_moeda_{nome_exibicao}"
                    if chave_moeda not in st.session_state:
                        st.session_state[chave_moeda] = moeda_salva

                    moeda_atual = c_moeda.radio(
                        "Moeda", ["BRL", "USD"],
                        # index=0 if moeda_salva == "BRL" else 1,
                        horizontal=True,
                        key=f"sel_moeda_{nome_exibicao}",
                        label_visibility="collapsed"
                    )
                    # Atualiza a memória se o usuário trocar a moeda
                    state['moedas_por_grupo'][nome_exibicao] = moeda_atual
                    
                    # --- LÓGICA DE VALOR SUGERIDO ---
                    # Busca o valor que veio do cálculo da Etapa 1 (brl ou usd)
                    sugestao_dinamica = item.get(moeda_atual.lower(), {}).get("valor_aporte", 0.0)
                    
                    # Se não houver valor no state para esse par (grupo+moeda), injetamos a sugestão
                    chave_valor = f"val_etapa2_{nome_exibicao}_{moeda_atual}"
                    if chave_valor not in st.session_state:
                        st.session_state[chave_valor] = f"{float(sugestao_dinamica):.2f}".replace(".", ",")

                    # --- LINHA DE INPUTS ---
                    c_val, c_max = st.columns(2)
                    
                    with c_val:
                        valor_ajustado = st_number_input_custom(
                            f"Valor ({moeda_atual})", 
                            key=chave_valor
                        )
                    
                    with c_max:
                        porc_max = st_number_input_custom(
                            "% Máx/Ativo", 
                            value="20,00",
                            key=f"max_input_{nome_exibicao}"
                        )
                    
                    lista_categorias = [cat.strip() for cat in nome_exibicao.split("+")]
                    # --- CONSTRUÇÃO DO PAYLOAD ---
                    payload_etapa2_dist.append({
                        "grupo": lista_categorias, # Back-end espera lista
                        "valor_aporte": float(valor_ajustado) if valor_ajustado is not None else 0.0,
                        "moeda": moeda_atual,
                        "percentual_max_ativo": float(porc_max) if porc_max is not None else 20.0
                    })

    return payload_etapa2_dist

def widget_resultado_ativos(dist):
    for item in dist:

        nome_grupo = " + ".join(item["grupo"])
        moeda = item["moeda"]
        
        # Criar o Expander com resumo no título
        with st.expander(f"📂 {nome_grupo} | Alocado: {moeda} {item['valor_alocado']:.2f}"):
            
            # 1. Preparar os dados para o DataFrame
            df = pd.DataFrame(item["ativos"])

            # 2. Selecionar e renomear colunas para uma leitura mais limpa
            colunas_exibicao = {
                "ticker": "Ticker",
                "nome": "Nome",
                "preco_atual": "Preço Atual",
                "preco_min_12m": "Mín 12m",
                "posicao_range_12m": "% Range 12m",
                "preco_max_12m": "Máx 12m",

                "propor_aporte_12m": "% Aporte 12m",
                "aporte_12m": "Aporte 12m",

                "gap_original_financeiro": "Gap Orig. R$",
                "gap_ajustado_financeiro": "Gap Adj. R$",

                "redutor_preco": "Redutor Preço",
                "redutor_concentracao": "Redutor Conc.",

                "peso_original": "Peso Orig.",
                "peso_ajustado": "Peso Adj.",
                "sugestao_aporte": "Sugestão Aporte",
                "motivo_ajuste": "Status/Motivo"
            }
            
            df_display = df[list(colunas_exibicao.keys())].rename(columns=colunas_exibicao)
            df_display.insert(0, "Selecionar", False)
            # 3. Estilização e Formatação
            def colorir_aporte(val):
                color = 'background-color: rgba(0, 255, 0, 0.1)' if val > 0 else ''
                return color
            
            formatacao_brasileira = {
                                        "Preço Atual": "{:,.2f}",
                                        "Mín 12m": "{:,.2f}",
                                        "Máx 12m": "{:,.2f}",
                                        "% Aporte 12m": "{:.2%}",
                                        "Aporte 12m": "{:,.2f}",
                                        "Gap Orig. R$": "{:,.2f}",
                                        "Gap Adj. R$": "{:,.2f}",
                                        "Redutor Preço": "{:,.2f}",
                                        "Redutor Conc.": "{:,.2f}",
                                        "Peso Orig.": "{:,.2f}",
                                        "Peso Adj.": "{:,.2f}",
                                        "Sugestão Aporte": "{:,.2f}"
                                    }

            configuracao_colunas = {
                                    "Selecionar": st.column_config.CheckboxColumn(
                                        "✔",
                                        help="Selecione para incluir este ativo no aporte final",
                                        default=False,
                                    ),
                                    "Ticker": st.column_config.TextColumn(
                                        "Ticker",
                                        help="Código do ativo",
                                        disabled=True, # Evita edição acidental
                                    ),
                                    "Preço Atual": st.column_config.NumberColumn(
                                        f"Preço Atual ({moeda})",
                                        help="Preço de mercado atual",
                                    ),
                                    "% Range 12m": st.column_config.ProgressColumn(
                                        "% Range 12m",
                                        help="Posição do preço atual entre a mínima e máxima de 12 meses",
                                        format="%d%%",
                                        min_value=0,
                                        max_value=100,
                                    ),
                                    "Sugestão Aporte": st.column_config.NumberColumn(
                                        "Sugestão Aporte",
                                        format=f"{moeda} %.2f",
                                        help="Valor sugerido pelo algoritmo baseado no Gap e Redutores",
                                    ),
                                    "Status/Motivo": st.column_config.TextColumn(
                                        "📌 Status/Motivo",
                                        help="Explicação para o ajuste ou bloqueio do aporte",
                                    ),
                                    # Colunas que podem ser ocultadas ou simplificadas para não poluir
                                    "Redutor Preço": st.column_config.NumberColumn("📉 Red. Preço"),
                                    "Redutor Conc.": st.column_config.NumberColumn("🛡️ Red. Conc."),
                                    "Peso Adj.": st.column_config.NumberColumn("⚖️ Peso Adj."),
                                }
            colunas_visivel = ["Selecionar","Ticker", "Sugestão Aporte", "Preço Atual", "% Range 12m", "% Aporte 12m", "Status/Motivo", "Gap Orig. R$"] # Colunas principais para exibição
            # Aplicar formatação numérica e cores
            selecionado = st.data_editor(
                        df_display.style.format(formatacao_brasileira, decimal=',', thousands='.').map(colorir_aporte, subset=['Sugestão Aporte']), # <-- Correção aqui
                        width="stretch",
                        hide_index=True,
                        column_order=colunas_visivel,
                        disabled=list(colunas_exibicao.values()),
                        column_config= configuracao_colunas
                    )
            
            key_editor = f"editor_{nome_grupo}"
            # Lógica de persistência e limpeza
            if key_editor not in st.session_state['page_aportes'] or not st.session_state['page_aportes'][key_editor].equals(selecionado):
                st.session_state['page_aportes'][key_editor] = selecionado
                
                # Busca chaves que começam com 'perc_' para resetar o ajuste manual
                keys_to_clear = [k for k in st.session_state.keys() if k.startswith("perc_")]                
                
                if keys_to_clear:
                    for key in keys_to_clear:
                        del st.session_state[key]

            st.session_state['page_aportes']['data_editor'].update({nome_grupo: selecionado}) # Armazenar o DataFrame original para referência futura
            # 4. Métricas rápidas do grupo (opcional)
            c1, c2, c3 = st.columns(3)
            total_sugerido = df["sugestao_aporte"].sum()
            c1.metric("Total Sugerido", f"{moeda} {total_sugerido:.2f}")
            c2.metric("Ativos no Grupo", len(df))
            c3.metric("Moeda", moeda)

def formata_br(valor):
    """Converte um número para string no formato R$ 1.234,56"""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def widget_ajuste_manual_dinamico(df, valor_total_aporte):
    novos_dados = []
    total_percentual_atual = 0.0

    # 1. Cabeçalho Estilizado
    st.markdown("""
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; font-weight: bold; color: #31333F;">
                <div style="flex: 1;">Ticker</div>
                <div style="flex: 1.5;">Valor Aporte (R$)</div>
                <div style="flex: 1;">Qtd. Aprox.</div>
                <div style="flex: 2;">Alocação (%)</div>
                <div style="flex: 1.5;">Sugestão</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    for index, row in df.iterrows():
        ticker = row['Ticker']
        sugestao = row['Sugestão Aporte']
        preco_unitario = row['Preço Atual']
        
        soma_sugestoes = df['Sugestão Aporte'].sum()
        perc_sugerido = (sugestao / soma_sugestoes * 100) if soma_sugestoes > 0 else 0.0
        
        if f"perc_{ticker}" not in st.session_state:
            st.session_state[f"perc_{ticker}"] = float(perc_sugerido)

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([1, 1.5, 1, 2, 1.5])
            
            c1.markdown(f"**{ticker}**")
            
            # Valor Financeiro Calculado (BR)
            novo_percentual = st.session_state[f"perc_{ticker}"]
            valor_financeiro = (novo_percentual / 100) * valor_total_aporte
            c2.write(f"R$ {formata_br(valor_financeiro)}")
            
            # Cálculo de Ativos
            quantidade_ativos = int(valor_financeiro // preco_unitario) if preco_unitario > 0 else 0
            valor_efetivo = quantidade_ativos * preco_unitario
            
            c3.markdown(f"<span style='color: #0068c9; font-weight: bold; font-size: 18px;'>{quantidade_ativos}</span>", unsafe_allow_html=True)
            
            # Input de Percentual
            novo_percentual = c4.number_input(
                f"% {ticker}",
                min_value=0.0, max_value=100.0, step=0.1,
                label_visibility="collapsed",
                key=f"perc_{ticker}"
            )
            
            # Sugestão original (BR)
            valor_sug_original = perc_sugerido * valor_total_aporte / 100
            c5.write(f"R$ {formata_br(valor_sug_original)} / {formata_br(perc_sugerido)}%")

        total_percentual_atual += novo_percentual
        row_atualizada = row.to_dict()
        row_atualizada.update({
            'Ajuste %': novo_percentual,
            'Novo Aporte R$': valor_financeiro,
            'Quantidade': quantidade_ativos,
            'Valor Efetivo': valor_efetivo
        })
        novos_dados.append(row_atualizada)

    m1, m2, m3 = st.columns(3)
    
    # Métricas com formatação brasileira
    m1.metric("Total Alocado", f"{formata_br(total_percentual_atual)}%", 
              delta=f"{formata_br(total_percentual_atual - 100)}%" if abs(total_percentual_atual - 100) > 0.01 else None,
              delta_color="inverse" if total_percentual_atual > 100.01 else "normal")
    
    total_efetivo = sum(d['Valor Efetivo'] for d in novos_dados)
    sobra = valor_total_aporte - total_efetivo
    
    m2.metric("Total Efetivo", f"R$ {formata_br(total_efetivo)}")
    m3.metric("Sobra em Caixa", f"R$ {formata_br(sobra)}")

    if total_percentual_atual > 100.01:
        st.error(f"⚠️ Distribuição acima de 100%. Reduza {formata_br(total_percentual_atual - 100)}%.")

    return pd.DataFrame(novos_dados)

def widget_aposte_final():
    st.header("🚀 Aporte por Ativo - Ajuste Manual")
    lista_valores_aporte_grupo = []
    dist = data["sugestao_grupos"]
    for item in dist:   
        lista_valores_aporte_grupo.append({
            "grupo": " + ".join(item["grupo"]),
            "valor_alocado": item.get("valor_alocado", 0.0)
        }) 
    df_valores_aporte = pd.DataFrame(lista_valores_aporte_grupo)
  
    for grupo, df_selecionado in st.session_state['page_aportes']['data_editor'].items():
        if not df_selecionado.empty:
            # Filtramos apenas os ativos marcados com o Checkbox
            df_ativos_check = df_selecionado[df_selecionado["Selecionar"] == True]

            if not df_ativos_check.empty:
                valor_row = df_valores_aporte[df_valores_aporte['grupo'] == grupo]['valor_alocado']
                if not valor_row.empty:
                    valor_total = float(valor_row.values[0]) # <--- Pega o número real
                    
                    with st.expander(f"📌 Ajuste Manual: {grupo} - Aporte: R$ {formata_br(valor_total)}", expanded=False):
                        widget_ajuste_manual_dinamico(df_ativos_check, valor_total)
                else:
                    st.warning(f"Valor de aporte não encontrado para o grupo {grupo}")

#------------------------------------
# --- 2. INICIALIZAÇÃO DO ESTADO ---
#------------------------------------
if 'page_aportes' not in st.session_state:
    # 1. Pegamos as categorias primeiro
    cats = get_categorias_usuario()    
    # 2. Criamos o dicionário completo
    st.session_state['page_aportes'] = {
        'moedas_por_grupo': {},
        'categorias_disponiveis': cats,
        'lista_grupos': [{"cats": [cat], "min": "5,00", "max": "50,00"} for cat in cats],
        'ultimo_payload': None
    }

# --- 3. CABEÇALHO DE CONTROLE ---
st.title("🎯 Aporte Estratégico")
with st.expander("📘 Instruções", expanded=False):
    st.markdown("""
    1. **Defina o valor total do aporte** e a moeda desejada.
    2. **Agrupe as categorias** de ativos conforme sua estratégia, definindo limites mínimos e máximos para cada grupo.
    3. **Distribuição sugerida** do aporte entre os grupos.
    4. **Ajuste os valores por grupo** e defina o percentual máximo por ativo dentro de cada grupo.
    5. **Gere aporte por ativo** com base nas suas configurações.
    6. **Revise e ajuste manualmente** selecione quais ativos aportar.
    7. **Ajuste manual fino** escolha manualmente quanto aportar.
    """)

with st.expander("📊 Formulário Grupo", expanded=True):

    # --- 4. Formulário de aporte por grupos ---
    v_aporte, moeda = widget_aporte_global()
    payload_resp = widget_config_categorias(v_aporte, moeda)

    # --- 5. ENVIO E PROCESSAMENTO ---
    st.write("")
    if st.button("🚀 Distribuir Aporte", type="primary", width="stretch"):
        payload = payload_resp
        
        user_id = st.session_state.get("id")
        resultado = post_aporte_etapa1(user_id, payload)
        
        if resultado:
            # Limpa chaves de ajuste da Etapa 2 para resetar os campos
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith("val_etapa2_") or k.startswith("sel_moeda_")]
            for key in keys_to_clear:
                del st.session_state[key]
            
            if 'moedas_grupos' in st.session_state['page_aportes']:
                st.session_state['page_aportes']['moedas_por_grupo'] = {}

            if resultado.get("status") == "sucesso":
                st.session_state['page_aportes']['resultado_grupo_aporte'] = resultado.get('distribuicao', [])
                st.success("Cálculo realizado com sucesso!")


# --- 6. EXIBIÇÃO DOS RESULTADOS E FORMULÁRIO ETAPA POR ATIVOS ---
if 'resultado_grupo_aporte' in st.session_state['page_aportes']:
    with st.expander("📊 Resultado da Distribuição Sugerida", expanded=True):
        user_id = st.session_state.get("id")
        dist = st.session_state['page_aportes']['resultado_grupo_aporte']

        if dist:
            with st.expander("📈 Análise da Distribuição Sugerida", expanded=False):
                widget_resultado_grupo(dist)
        
        payload_etapa2_dist = widget_config_ativos(dist, moeda_padrao=moeda)

        # Botão Final
        st.write("")
        if st.button("🛒 Calcular Aporte por Ativo", width="stretch", type="primary"):
            payload_final = {
                "user_id": int(user_id) if user_id else 0,
                "distribuicao": payload_etapa2_dist
            }
            
            resultado_ativos = post_aporte_etapa2(user_id, payload_final)
            if resultado_ativos:
                if resultado_ativos["status"] == "sucesso":
                    st.session_state['page_aportes']['data_editor'] = {}
                    st.session_state['page_aportes']['resultado_ativos_aporte'] = resultado_ativos
                    st.rerun()

if 'resultado_ativos_aporte' in st.session_state['page_aportes'] and st.session_state['page_aportes']['resultado_ativos_aporte']:
    data = st.session_state['page_aportes']['resultado_ativos_aporte']
    with st.expander("📈 Detalhamento dos Ativos Sugeridos para Aporte", expanded=True):
        widget_resultado_ativos(data["sugestao_grupos"])

if 'data_editor' in st.session_state['page_aportes']:   
    widget_aposte_final()