import streamlit as st
import pandas as pd
import requests
from datetime import date
from settings import API_URL
from great_tables import GT, html, loc, style
from streamlit_extras.great_tables import great_tables

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Legacynvest - Impostos")

def carregar_dados_ano(ano_alvo):
    with st.spinner(f"Buscando fechamentos de {ano_alvo}..."):
        user_id = st.session_state.get("id", 0)
        resumo_raw = safe_get_list(f"{API_URL}ir/resumo_vendas_mensal/{user_id}", {"ano": ano_alvo})
        
        df_temp = pd.DataFrame(resumo_raw)
        if not df_temp.empty:
            df_temp['periodo_referencia'] = pd.to_datetime(df_temp['periodo_referencia'])
            st.session_state.df_resumo = df_temp
            return True
        else:
            st.session_state.df_resumo = pd.DataFrame()
            return False

def st_number_input_custom(label, value=None, key=None, placeholder="0,00"):
    def converter_valor_br(texto):
        if not texto:
            return 0.0
        try:
            # Remove pontos de milhar e troca a vírgula decimal por ponto
            limpo = texto.replace(".", "").replace(",", ".")
            return float(limpo)
        except ValueError:
            return None
    
    entrada = st.text_input(label, value=value, placeholder=placeholder, key=key)
    valor_numerico = converter_valor_br(entrada)
    if entrada and valor_numerico is None:
        st.warning("Use o formato 0,00")
        return None
    return valor_numerico

def safe_get_list(url, params):
    try:
        token = st.session_state.get("token")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, params=params, headers=headers)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        st.error(f"Erro ao conectar na API: {e}")
        return []

if "input_irrf" not in st.session_state:
    st.session_state.input_irrf = "0,00"


# --- 1. CABEÇALHO E CONTROLES ---
col_titulo, col_ano, col_btn = st.columns([6, 2, 2])
col_titulo.title("📊 Consolidação de Impostos")

with col_ano:
    anos_disponiveis = list(range(2020, date.today().year + 2))
    ano = st.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-2, label_visibility="collapsed")

with col_btn:
    btn_carregar = st.button("🔄 Carregar/Atualizar Dados",width="stretch")

# --- 2. LÓGICA DE CARREGAMENTO ---
if btn_carregar:
    with st.spinner(f"Buscando fechamentos de {ano}..."):
        user_id = st.session_state.get("id", 0)
        resumo_raw = safe_get_list(f"{API_URL}ir/resumo_vendas_mensal/{user_id}", {"ano": ano})
        
        df_temp = pd.DataFrame(resumo_raw)
        if not df_temp.empty:
            df_temp['periodo_referencia'] = pd.to_datetime(df_temp['periodo_referencia'])
            st.session_state.df_resumo = df_temp
            st.success(f"Dados de {ano} carregados!")
        else:
            st.session_state.df_resumo = pd.DataFrame()
            st.warning(f"Nenhum dado encontrado.")

if "df_resumo" not in st.session_state:
    st.session_state.df_resumo = pd.DataFrame()

df = st.session_state.df_resumo

if not df.empty:
    try:
        df_gt = df.copy()
        ano_dos_dados = df_gt['periodo_referencia'].dt.year.iloc[0]
        subtitulo_dinamico = f"Consolidação de Lucros e Imposto Devido - Exercício {ano_dos_dados+1}"
        
        df_gt['Mês'] = df_gt['periodo_referencia'].dt.strftime('%m/%Y')
        df_gt['pago_display'] = df_gt['pago'].apply(lambda x: "✅ Pago" if x else "❌ Pendente")
        df_gt['imposto_devido_total'] = df_gt['imposto_rv'] + df_gt['imposto_fii']
        
        # REORDENAÇÃO: IRRF agora vem ANTES do fechamento financeiro (DARF)
        cols_final = [
            'Mês', 
            # Bloco RV
            'lucro_tributavel_rv', 'prejuizo_acumulado_rv', 'imposto_rv',
            # Bloco FII
            'lucro_tributavel_fii', 'prejuizo_acumulado_fii', 'imposto_fii', 
            # Bloco IRRF
            'irrf_retido_mes', 'irrf_saldo_acumulado', 
            # Bloco Liquidação
            'imposto_devido_total', 'saldo_darf_minima', 'valor_darf_emitida', 'pago_display'
        ]

        cols_financeiras = [c for c in cols_final if c not in ['Mês', 'pago_display']]

        gt_table = (
            GT(df_gt[cols_final])
            .tab_header(
                title="Relatório de Fechamento Fiscal",
                subtitle=subtitulo_dinamico
            )
            .tab_spanner(
                label="📈 RV (Ações/BDR/ETF)", 
                columns=["lucro_tributavel_rv", "prejuizo_acumulado_rv", "imposto_rv"]
            )
            .tab_spanner(
                label="🏢 FII / FIAGRO", 
                columns=["lucro_tributavel_fii", "prejuizo_acumulado_fii", "imposto_fii"]
            )
            .tab_spanner(
                label="🕵️ Dedo-duro (IRRF)", 
                columns=["irrf_retido_mes", "irrf_saldo_acumulado"]
            )
            .tab_spanner(
                label="💰 Liquidação", 
                columns=["imposto_devido_total", "saldo_darf_minima", "valor_darf_emitida", "pago_display"]
            )
            .cols_label(
                lucro_tributavel_rv=html("Lucro<br>Tributável"),
                prejuizo_acumulado_rv=html("Prej.<br>Acum."),
                imposto_rv=html("Imposto<br>(15%)"),
                lucro_tributavel_fii=html("Lucro<br>Tributável"),
                prejuizo_acumulado_fii=html("Prej.<br>Acum."),
                imposto_fii=html("Imposto<br>(20%)"),
                imposto_devido_total=html("Total<br>Devido"),
                irrf_retido_mes=html("Retido<br>(Mês)"),
                irrf_saldo_acumulado=html("Saldo<br>Acumulado"),
                saldo_darf_minima=html("DARF Mín.<br>Acumulada"),
                valor_darf_emitida=html("DARF<br>Final"),
                pago_display="Status"
            )
            .fmt_currency(
                columns=cols_financeiras, 
                currency="BRL", sep_mark=".", dec_mark=","
            )
            .tab_style(
                style=style.text(style="italic", color="#666"),
                # Adicionado os prejuízos no estilo itálico para diferenciar do lucro
                locations=loc.body(columns=["saldo_darf_minima", "irrf_saldo_acumulado", "prejuizo_acumulado_rv", "prejuizo_acumulado_fii"])
            )
            .tab_style(
                style=[style.fill(color="#F0F2F6"), style.text(weight="bold")],
                locations=loc.body(columns=["valor_darf_emitida"])
            )
            .cols_align(align="center", columns=["pago_display"])
            .tab_style(
                style=style.text(color="green"),
                locations=loc.body(columns="pago_display", rows=(df_gt["pago_display"] == "✅ Pago").tolist())
            )
            .tab_style(
                style=style.text(color="red"),
                locations=loc.body(columns="pago_display", rows=(df_gt["pago_display"] == "❌ Pendente").tolist())
            )
        )
        
        great_tables(gt_table)
        
    except Exception as e:
        st.error(f"Erro ao renderizar Great Tables: {e}")
        st.dataframe(df, width="stretch")
    # --- 4. SELEÇÃO PARA EDIÇÃO (SELECTBOX) ---
    
    opcoes_mes = df['periodo_referencia'].dt.strftime('%m/%Y').tolist()
    mes_sel = st.selectbox("📝 Selecione o mês para detalhar ou editar:", opcoes_mes)
    # Filtra o item selecionado
    item = df[df['periodo_referencia'].dt.strftime('%m/%Y') == mes_sel].iloc[0]
    if mes_sel:
        st.session_state.input_irrf = f"{item.get('irrf_retido_mes', 0):,.2f}".replace(".", ",")
    
    col_info, col_edicao, col_result = st.columns([1.5, 1,  2])

    with col_info:
        st.markdown(f"#### Memória de Cálculo: **{mes_sel}**")
        
        # Coleta de dados do item selecionado
        vendas = item.get('vendas_totais_acoes', 0)
        isento = item.get('lucro_isento_acoes', 0)
        lucro_rv = item.get('lucro_tributavel_rv', 0)
        lucro_fii = item.get('lucro_tributavel_fii', 0)
        prej_rv = item.get('prejuizo_acumulado_rv', 0)
        prej_fii = item.get('prejuizo_acumulado_fii', 0)

        dados_conciliacao = [
            {"Descrição": "💰 Vendas Totais (RV)", "RV (15%)": f"R$ {vendas:,.2f}", "FII (20%)": "_"},
            {"Descrição": "🟢 Lucro Isento (RV)", "RV (15%)": f"R$ {isento:,.2f}", "FII (20%)": "_"},
            {"Descrição": "📈 Lucro Tributável", "RV (15%)": f"R$ {lucro_rv:,.2f}", "FII (20%)": f"R$ {lucro_fii:,.2f}"},
            {"Descrição": "📉 Prejuízo Acumulado", "RV (15%)": f"R$ {prej_rv:,.2f}", "FII (20%)": f"R$ {prej_fii:,.2f}"},
            {"Descrição": "⚖️ Base de Cálculo", "RV (15%)": f"R$ {(item.get('imposto_rv', 0)/0.15):,.2f}", "FII (20%)": f"R$ {(item.get('imposto_fii', 0)/0.2):,.2f}"},
            {"Descrição": "🏛️ Imposto Devido", "RV (15%)": f"R$ {item.get('imposto_rv', 0):,.2f}", "FII (20%)": f"R$ {item.get('imposto_fii', 0):,.2f}"}
        ]
        
        st.table(pd.DataFrame(dados_conciliacao).set_index("Descrição"))
        st.latex(r"Base de Cál. = L. Trib. + Prej. Acum. ant.")
        st.latex(r"Imposto Devido = Base de Cál. * Alíquota")
    with col_edicao:
        st.markdown("#### ⚙️ Ajustes")
        # 1. Entrada do novo valor (usuário digita)
        # novo_irrf = st.number_input("IRRF Retido no Mês:", value=float(item.get('irrf_retido_mes', 0)), step=0.01)
        novo_irrf = st_number_input_custom("IRRF Retido no Mês:", value=st.session_state.input_irrf)
        pago_status = st.checkbox("Pago?", value=bool(item.get('pago', False)))
        
        # --- LÓGICA DE PRÉ-VISUALIZAÇÃO CORRIGIDA ---
        
        # Pegamos o valor que a API já calculou como DARF Final
        darf_atual_api = float(item.get('valor_darf_emitida', 0))
        # Pegamos o IRRF que a API usou originalmente para chegar nesse valor
        irrf_original_api = float(item.get('irrf_retido_mes', 0))
        
        # Passo 1: Descobrimos qual era o imposto ANTES do IRRF (Devolvemos o IRRF antigo ao total)
        # Se a DARF era 90 e o IRRF era 10, o total bruto era 100.
        imposto_bruto_simulado = darf_atual_api + irrf_original_api
        
        # Passo 2: Aplicamos o NOVO IRRF sobre esse bruto
        darf_prevista = imposto_bruto_simulado - novo_irrf
        
        # Passo 3: Garantimos que não fique negativo (crédito acumulado não gera DARF negativa)
        darf_exibicao = max(0.0, darf_prevista)
        
        # Regra visual: Se for menor que R$ 10,00, a Receita não emite (vai para o saldo acumulado)
        # Mas para fins de "Previsão", mostramos o valor real ou zero se for o caso.
        if darf_exibicao < 10 and darf_exibicao > 0:
            msg_help = "Valor inferior a R$ 10,00. Será acumulado para o mês seguinte."
        else:
            msg_help = "Cálculo simulado: (Imposto Bruto + Saldo DARF Mínima) - (Novo IRRF + Crédito Acumulado)."
   
        if st.button("💾 Salvar", use_container_width=True, type="primary"):
            payload = {
                "periodo_referencia": item['periodo_referencia'].strftime('%Y-%m-%d'),
                "irrf_retido_mes": novo_irrf,
                "pago": pago_status
            }
            
            try:
                token = st.session_state.get("token")
                user_id = st.session_state.get("id", 0)
                headers = {'Authorization': f'Bearer {token}'}
                url_update = f"{API_URL}ir/atualizar_fechamento/{user_id}"
                
                response = requests.post(url_update, json=payload, headers=headers)
                
                if response.status_code == 200:
                    st.toast("Dados salvos e impostos recalculados!", icon="✅")
                    
                    # REUTILIZAÇÃO DA FUNÇÃO (Ponto 2 e 3)
                    # Em vez de escrever todo o código de carregar de novo, chamamos a função:
                    carregar_dados_ano(ano) 
                    
                    # O rerun limpa o estado visual e mostra a tabela nova
                    st.rerun()
                else:
                    st.error(f"Erro: {response.json().get('detail')}")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
    with col_result:
        # Título sutil para o bloco de simulação
        st.markdown("#### 🧮 Simulação")
        
        # Exibição da Fórmula em LaTeX (Centralizada e Elegante)
        metirca, lt=  st.columns([1, 2])
        lt.markdown("**Fórmula de Cálculo do DARF:**", help=msg_help)
        lt.latex(r"DARF = (I_b + S_d) - (IRRF_n + IRRF_a)")
        
        # Métrica Principal
        metirca.metric(
            "Prev. DARF", 
            f"R$ {darf_exibicao:,.2f}", 
            delta=None if darf_exibicao >= 10 else "Abaixo do Mín.",
            delta_color="off",
            help="Cálculo simulado para conferência antes do salvamento."
        )
        # Glossário Técnico (Markdown com fontes menores/itálico)
        st.markdown("""
        ---
        **Legenda da Fórmula:**
        * $I_b$: Imposto Bruto (RV + FII)
        * $S_d$: Saldo de DARF Mínima acumulada
        * $IRRF_n$: Novo IRRF informado
        * $IRRF_a$: Crédito de IRRF acumulado
        """, help="O crédito acumulado ($IRRF_a$) refere-se ao saldo de meses anteriores que ainda não foi compensado.")
else:
    st.info("Use o botão 'Carregar/Atualizar Dados' para buscar as informações mais recentes.")