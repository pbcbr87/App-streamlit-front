import streamlit as st
import pandas as pd
import requests
from datetime import date
from settings import API_URL

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Legacynvest - Impostos Exterior")

def safe_get_list(url, params):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, params=params, headers=headers)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        st.error(f"Erro ao conectar na API: {e}")
        return []

def fmt_brl(valor):
    if valor is None: return "R$ 0,00"
    # Tratamento para números negativos no formato brasileiro
    v = float(valor)
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_usd(valor):
    if valor is None: return "US$ 0,00"
    v = float(valor)
    return f"US$ {v:,.2f}"

def fmt_dual(valor_brl, valor_usd):
    # A função dual já resolve o escape para o Streamlit
    texto = f"{fmt_brl(valor_brl)} ({fmt_usd(valor_usd)})"
    return texto.replace("$", r"\$")

# --- 1. CABEÇALHO E CONTROLES ---
col_titulo, col_ano, col_btn = st.columns([6, 2, 2])
col_titulo.title("🌎 Consolidação Exterior")

# --- NOTA IMPORTANTE NO INÍCIO (AVISO GERAL) ---
with st.expander("ℹ️ Instruções para Declaração IRPF"):
    st.warning(f"""
    ⚠️ **Orientações de Preenchimento IRPF:**

    1. **Compensação de Perdas:** Na ficha de **Bens e Direitos**, lembre-se de marcar a opção: 
    `"Possui perdas a compensar de acordo com a Lei nº 14.754, de 2023 (art. 9º)?"` para validar seus prejuízos.
    2. **Patrimônio:** Os dados de **Custo de Aquisição** (posição em 31/12) devem ser consultados na aba **Bens e Direitos do Legacy Seed**.
    3. **Rendimentos:** Esta página processa exclusivamente os valores de **Ganhos e Perdas** (Resultado Vendas + Proventos) para apuração do imposto.

       A declaração deve ser feita na ficha de **Bens e Direitos**, dentro do item de cada ativo em **Aplicações Financeiras**. 
    Preencha os campos conforme os dados da tabela acima:

    * **Campo 'Rendimento ou Perda':** Informe o valor da coluna **'Ganhos / Prejuizos'** (que já é a soma de proventos e resultado vendas).
    * **Campo 'Imposto Pago no Exterior':** Informe o valor da coluna **'Imp. Pago Exterior'** (este valor será utilizado para dedução do imposto devido no Brasil).

    **Observação:** O sistema já realiza a compensação automática de perdas entre os ativos conforme a Lei 14.754/2023. Informações apenas para conferência. Todos os valores são calculados pelo programa IRPF. 
                
    """)

with col_ano:
    ano = st.selectbox("Ano-Calendário", list(range(date.today().year, 2023, -1)), index=1, label_visibility="collapsed")

with col_btn:
    btn_carregar = st.button("🔄 Sincronizar Exterior", width="stretch")

# --- 2. LÓGICA DE CARREGAMENTO ---
if btn_carregar:
    with st.spinner(f"Processando cálculos de {ano}..."):
        user_id = st.session_state.get("id", 0)
        resumo_raw = safe_get_list(f"{API_URL}ir/resumo_ano_exterior/{user_id}", {"ano": ano})
        
        # Busca o ano anterior para saber o prejuízo transportado
        ano_anterior_raw = safe_get_list(f"{API_URL}ir/resumo_ano_exterior/{user_id}", {"ano": ano - 1})
        
        if resumo_raw:
            st.session_state.df_exterior = pd.DataFrame(resumo_raw)
            
            # Lógica para garantir que o saldo anterior seja capturado ou zerado
            df_ant = pd.DataFrame(ano_anterior_raw)
            if not df_ant.empty:
                snap_ant = df_ant[df_ant['is_fechamento_anual'] == True]
                # Salvamos o saldo se for prejuízo (< 0), caso contrário salvamos 0.0
                if not snap_ant.empty:
                    valor_ant = snap_ant.iloc[0]['saldo']
                    st.session_state.saldo_anterior = valor_ant if valor_ant < 0 else 0.0
                else:
                    st.session_state.saldo_anterior = 0.0
            else:
                st.session_state.saldo_anterior = 0.0
                
            st.success(f"Dados de {ano} carregados com sucesso!")
        else:
            st.session_state.df_exterior = pd.DataFrame()
            st.warning("Nenhum dado encontrado.")

# --- 3. EXIBIÇÃO DA TABELA ---
df = st.session_state.get("df_exterior", pd.DataFrame())
saldo_anterior = st.session_state.get("saldo_anterior", 0.0)

if not df.empty:
    # Obtém o ano diretamente do DataFrame
    df_itens = df[df['is_fechamento_anual'] == False].copy()
    ano_do_dado = int(df_itens['ano_calendario'].iloc[0]) if not df_itens.empty else ano

    # A) INFOS DO ANO ANTERIOR
    st.info(f"📉 **Prejuízo Acumulado de {ano_do_dado-1}:** {fmt_brl(saldo_anterior)}")

    # B) TABELA POR ATIVO
    if not df_itens.empty:
        st.markdown(f"### 📋 Rendimentos e Perdas por Ativo - {ano_do_dado}")
        
        df_display = pd.DataFrame()
        df_display['Ativo'] = df_itens['fk_ativo'].fillna("Ativo s/ Nome")
        
        # 1. Resul. Vendas (BRL + USD)
        df_display['Resul. Vendas'] = df_itens.apply(
            lambda x: fmt_dual(x['lucro_vendas_brl'], x['lucro_vendas_usd']), axis=1
        )
        
        # 2. Div. Brutos (BRL + USD)
        df_display['Div. Brutos'] = df_itens.apply(
            lambda x: fmt_dual(x['dividendos_brutos_brl'], x['dividendos_brutos_usd']), axis=1
        )
        
        # 3. Ganhos / Prejuizos (Apenas BRL conforme solicitado)
        df_display['Ganhos / Prejuizos'] = df_itens['resultado_liquido_brl'].apply(fmt_brl)
        
        df_display['Imposto Devido'] = (df_itens['resultado_liquido_brl'] * 0.15).apply(fmt_brl)
        
        # 4. Imp. Pago Exterior (BRL + USD)
        df_display['Imp. Pago Exterior'] = df_itens.apply(
            lambda x: fmt_dual(x['imposto_pago_exterior_brl'], x['imposto_pago_exterior_usd']), axis=1
        )
        
        # Colunas de conferência de saldo
        df_display['Base de Cálculo (Item)'] = df_itens['base_calculo'].apply(fmt_brl)
        df_display['Saldo Acumulado'] = df_itens['saldo'].apply(fmt_brl)
        df_display['Imp. Devido (Saldo)'] = df_itens['imposto_devido_saldo'].apply(fmt_brl)

        st.table(df_display)

    # C) FECHAMENTO CONSOLIDADO
    # Filtramos pelo snapshot de fechamento e pelo ano identificado
    df_snapshot = df[(df['is_fechamento_anual'] == True) & (df['ano_calendario'] == ano_do_dado)].copy()
    
    if not df_snapshot.empty:
        st.divider()
        snap = df_snapshot.iloc[0]
        st.markdown(f"### 🎯 Fechamento Consolidado {ano_do_dado}")
        
        c1, c2 = st.columns(2)
        saldo_final = snap['saldo']
        
        c1.metric(f"Base de Cálculo Final {ano_do_dado}", fmt_brl(saldo_final))
        c2.metric("Imposto Devido (15%)", fmt_brl(snap['imposto_devido_saldo']), delta="A pagar no ajuste anual", delta_color="inverse")
        
        if saldo_final < 0:
            st.info(f"**Compensação:** O prejuízo acumulado de **{fmt_brl(saldo_final)}** será transportado para o ano-calendário seguinte.")
else:
    st.info("Clique em 'Sincronizar Exterior' para processar os dados.")