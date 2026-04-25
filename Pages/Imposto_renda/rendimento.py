import streamlit as st
import pandas as pd
import requests
from datetime import date
from settings import API_URL
from great_tables import GT, loc, style
from streamlit_extras.great_tables import great_tables

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Legacynvest - Rendimentos IR")

# --- FUNÇÕES DE FORMATAÇÃO ---
def fmt_brl(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def fmt_usd(valor):
    try:
        return f"US$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "US$ 0,00"

def map_ir_details(row):
    tipo = str(row.get('tipo', '')).upper()
    if 'DIVIDENDO' in tipo: return "09", "Lucros e dividendos recebidos"
    if 'RENDIMENTO' in tipo and 'EXT' not in tipo: return "99", "Outros - Aplicacoes financeiras em fundos de investimento imobiliario"
    if 'JCP' in tipo: return "10", "Juros Sobre Capital Próprio"
    if 'TRIBUTADO' in tipo: return "06", "Rendimentos de aplicações financeiras"
    return None, tipo

# --- 1. INTERFACE ---
col_tit, col_ano, col_btn = st.columns([6, 2, 2])
col_tit.title("📑 Rendimentos Anuais (IRPF)")

with col_ano:
    ano_sel = st.selectbox("Ano-Calendário", list(range(date.today().year, 2019, -1)), label_visibility="collapsed")

if col_btn.button("🔄 Recarregar Tudo", use_container_width=True):
    if "df_ir_rendimentos" in st.session_state:
        del st.session_state.df_ir_rendimentos
    st.rerun()

# --- 2. CARREGAMENTO ---
if "df_ir_rendimentos" not in st.session_state:
    user_id = st.session_state.get("id", 0)
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{API_URL}ir/ir_dividendos/{user_id}", params={"ano": ano_sel}, headers=headers)
        
        if response.status_code == 200:
            df_raw = pd.DataFrame(response.json())
            if not df_raw.empty:
                cols_fin = [c for c in df_raw.columns if 'total_' in c]
                for c in cols_fin:
                    df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce').astype(float).fillna(0.0)
                st.session_state.df_ir_rendimentos = df_raw
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

# --- 3. EXIBIÇÃO ---
df_base = st.session_state.get("df_ir_rendimentos", pd.DataFrame())

if not df_base.empty:
    df = df_base.copy()
    df['Cod'], df['Desc_Oficial'] = zip(*df.apply(map_ir_details, axis=1))
    df['tipo_rend_id'] = df['Cod'].fillna("") + " - " + df['Desc_Oficial']
    
    # Ordenação por código IR e depois por Ticker
    df = df.sort_values(by=['tipo_rend_id', 'codigo_ativo'])

    # --- CONFIGURAÇÃO DE LARGURAS (Ajuste conforme seu monitor) ---
    LARGURA_TIPO = "400px"
    LARGURA_TICKER = "70px"
    LARGURA_FONTE = "330px"
    LARGURA_VALOR = "150px"

    # 🔵 TABELA 1: ISENTOS
    df_isento = df[df['Cod'].isin(['09', '99'])].copy()
    if not df_isento.empty:
        st.subheader("🔵 Rendimentos Isentos e Não Tributáveis")
        df_isento['valor_f'] = df_isento['total_liquido_brl'].apply(fmt_brl)
        gt_isento = (
            GT(df_isento[['tipo_rend_id', 'codigo_ativo', 'nome', 'valor_f']])
            .cols_label(tipo_rend_id="Tipo de Rendimento", codigo_ativo="Ticker", nome="Fonte Pagadora", valor_f="Valor")
            .cols_width(
                cases={
                    "tipo_rend_id": LARGURA_TIPO,
                    "codigo_ativo": LARGURA_TICKER,
                    "nome": LARGURA_FONTE,
                    "valor_f": LARGURA_VALOR
                }
            )
            .tab_options(table_width="100%")
        )
        great_tables(gt_isento)

    # 🟡 TABELA 2: TRIBUTAÇÃO EXCLUSIVA
    df_exclusiva = df[df['Cod'].isin(['10', '06'])].copy()
    if not df_exclusiva.empty:
        st.subheader("🟡 Sujeitos à Tributação Exclusiva/Definitiva")
        df_exclusiva['valor_f'] = df_exclusiva['total_liquido_brl'].apply(fmt_brl)
        gt_exclusiva = (
            GT(df_exclusiva[['tipo_rend_id', 'codigo_ativo', 'nome', 'valor_f']])
            .cols_label(tipo_rend_id="Tipo de Rendimento", codigo_ativo="Ticker", nome="Fonte Pagadora", valor_f="Valor")
            .cols_width(
                cases={
                    "tipo_rend_id": LARGURA_TIPO,
                    "codigo_ativo": LARGURA_TICKER,
                    "nome": LARGURA_FONTE,
                    "valor_f": LARGURA_VALOR
                }
            )
            .tab_options(table_width="100%")
        )
        great_tables(gt_exclusiva)

    # 🌎 TABELA 3: EXTERIOR (COM COLUNA IMPOSTO BRL RESTAURADA)
    df_ext = df[df['tipo'] == 'RENDIMENTO EXT'].copy()
    if not df_ext.empty:
        st.subheader("🌎 Rendimentos no Exterior")
        df_ext['bruto_usd_f'] = df_ext['total_bruto_usd'].apply(fmt_usd)
        df_ext['imp_usd_f'] = df_ext['total_imposto_usd'].apply(fmt_usd)
        df_ext['bruto_brl_f'] = df_ext['total_bruto_brl'].apply(fmt_brl)
        df_ext['imp_brl_f'] = df_ext['total_imposto_brl'].apply(fmt_brl)
        
        gt_ext = (
            GT(df_ext[['codigo_ativo', 'nome', 'bruto_usd_f', 'imp_usd_f', 'bruto_brl_f', 'imp_brl_f']])
            .cols_label(
                codigo_ativo="Ticker", 
                nome="Empresa", 
                bruto_usd_f="Bruto (USD)", 
                imp_usd_f="Imposto (USD)", 
                bruto_brl_f="Bruto (BRL)",
                imp_brl_f="Imposto (BRL)"
            )
            .tab_style(style=style.text(color="#d9534f"), locations=loc.body(columns=['imp_usd_f', 'imp_brl_f']))
            .tab_options(table_width="100%")
        )
        great_tables(gt_ext)

    # 💸 TABELA 4: TAXAS
    df_fee = df[df['tipo'] == 'AGENCY PROC. FEE'].copy()
    if not df_fee.empty:
        st.markdown("---")
        st.subheader("💸 Taxas de Serviço (Agency Proc. Fee)")
        df_fee['usd_f'] = df_fee['total_liquido_usd'].apply(fmt_usd)
        df_fee['brl_f'] = df_fee['total_liquido_brl'].apply(fmt_brl)
        gt_fee = (
            GT(df_fee[['codigo_ativo', 'nome', 'usd_f', 'brl_f']])
            .cols_label(codigo_ativo="Ticker", nome="Fonte", usd_f="USD", brl_f="BRL")
            .tab_style(style=style.text(color="#d9534f"), locations=loc.body())
            .tab_options(table_width="100%")
        )
        great_tables(gt_fee)
else:
    st.info(f"Nenhum dado encontrado para o ano {ano_sel}.")