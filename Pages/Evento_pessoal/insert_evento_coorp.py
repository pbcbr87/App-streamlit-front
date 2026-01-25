import streamlit as st
import requests
import pandas as pd
from json import dumps, loads
import time
from settings import API_URL
from datetime import date


#---------------------------------------------------------------
# --- Inicialização Unificada ---
keys_to_init = {
    'lista_ativo_cat_sugeridos': [],
    'lista_ativo_cat_o_sugeridos': [],
    'novo_ativo': 'Buscar Ativo',
    'ativo_original': 'Buscar Ativo'
}

for key, value in keys_to_init.items():
    if key not in st.session_state:
        st.session_state[key] = value
   
#----------------------------------------------------------------
def insert_evento(dados: dict):
    dados_json = dumps(dados, ensure_ascii=False)

    resp = requests.post(f'{API_URL}eventos_pessoal/criar_evento', dados_json, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.toast(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")
  
        # --- Tratamento de Sucesso (200 OK) ---    
    if resp.status_code == 200:
        st.toast(f"Dados Enviado com sucesso")

    if resp.status_code != 200:
        st.toast(f"⚠️ Erro na API. Status {resp.status_code}: {resp.text}")

def definir_ativo(input_key: str, output_key: str):
    if st.session_state[input_key]:
        st.session_state[output_key] = st.session_state[input_key]
    else:
        st.session_state[output_key] = 'Buscar Ativo'

def buscar_ativos(input_key: str, output_key: str):
    """Busca ativos na API e atualiza a chave de sugestões específica."""
    token = st.session_state.get('token')
    termo_busca = st.session_state.get(input_key, '')

    if not token:
        st.error("Usuário não autenticado.")
        return

    if not termo_busca:
        st.session_state[output_key] = []
        return

    try:
        url = f'{API_URL}ativos/pesquisar_dados_ativos/{termo_busca}'
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(url, headers=headers, timeout=5)
        
        if resp.status_code == 200:
            # List comprehension é mais legível que map/lambda para este caso
            sugestoes = [item['ativo_cat'] for item in resp.json()[:5]]
            st.session_state[output_key] = sugestoes
        else:
            st.session_state[output_key] = []
    except Exception as e:
        st.error(f"Erro na API: {e}")

def render_layout_input():
    """Renderiza os campos de entrada e retorna o dicionário de parâmetros."""
    c1, c2, c3, c4 = st.columns(4)
    quant_acum = c2.number_input("💰 Carteira para Teste: Qtd Cotas (qt)", value=100.00, format="%.5f", min_value=0.0)
    custo_acum = c3.number_input("💰 Carteira para Teste: Custo Acumulado", value=5000.00, format="%.5f", min_value=0.0)
    if c4.button("⬅️ Voltar", width="stretch"):
        st.switch_page("Pages/Evento_pessoal/evento_cadastrados.py") 
    # Lista de tipos e seleção
    tipo_list = ['ATUALIZAÇÃO', 'BONIFICAÇÃO', 'CISÃO', 'DESDOBRAMENTO', 
                 'GRUPAMENTO', 'GRUPAMENTO_DESDOBRAMENTO', 'INCORPORAÇÃO', 'OPA', 'REDUÇÃO DE CAPITAL']
    tipo = c1.selectbox('Tipo de Evento', tipo_list)
    
    dinheiro = None

    container = st.container(border=True)
    with container:
        cols = st.columns((1,2,2,2), border=True)
        
        # Campos comuns para quase todos
        c1_1, c1_2 = cols[1].columns([1,2], vertical_alignment="center")
        c1_1.markdown(f"**Ativo Original:**")
        with c1_2.popover(st.session_state['ativo_original']):
            st.text_input("Buscar Ativo Original",key='busca_ativo_o', on_change=buscar_ativos, args=('busca_ativo_o', 'lista_ativo_cat_o_sugeridos'))  
            id_ativo = st.pills("Selecionar Original",key='sl_ativo_o', 
                                    options=st.session_state['lista_ativo_cat_o_sugeridos'], 
                                    selection_mode='single', on_change=definir_ativo,
                                    args=('sl_ativo_o', 'ativo_original'))
        
        data_aprov = cols[0].date_input('Aprovação', min_value=date(2000, 1, 1))
        data_com = cols[0].date_input('Data Com', min_value=date(2000, 1, 1))
        data_pag = cols[0].date_input('Pagamento', min_value=date(2000, 1, 1))
            
        if tipo == 'BONIFICAÇÃO':
            ativo_gerado = id_ativo
            valor = cols[1].number_input("Valor por cota", format="%.5f")
            proporcao = cols[1].number_input("Proporção %", format="%.2f")
            cols[3].markdown("### Resumo")
            cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {quant_acum + quant_acum*proporcao/100} **Custo:** {custo_acum + valor*quant_acum*proporcao/100}")

            operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": f"{valor}*qt*{proporcao/100}", "qt": f"qt*{proporcao/100}"}]
            
        elif tipo == 'DESDOBRAMENTO' or tipo == 'GRUPAMENTO':
            valor = None
            proporcao = None
            ativo_gerado = id_ativo
            if cols[1].toggle('Valor:'):
                qt_novo = cols[1].number_input("Novo Qtd acumulada", format="%.2f")                
                cols[3].markdown("### Resumo")
                cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {qt_novo} **Custo:** {custo_acum}")
                
                operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": "0", "qt": f"{qt_novo}"}]
            else:
                proporcao = cols[1].number_input("Proporção %", format="%.2f")
                if tipo == 'GRUPAMENTO':
                    fator = (1/proporcao) if proporcao != 0 else 0
                    cols[1].text(f"{fator} para 1")
                    cols[3].markdown("### Resumo")
                    cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {quant_acum*proporcao} **Custo:** {custo_acum}")
                    
                    operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": "0", "qt": f"qt*{proporcao}"}]
                else:
                    fator = (proporcao + 100)/100
                    cols[1].text(f"1 para {fator}")
                    cols[3].markdown("### Resumo")
                    cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {quant_acum*fator} **Custo:** {custo_acum}")
                    
                    operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": "0", "qt": f"qt*{proporcao/100}"}]

        elif tipo == 'GRUPAMENTO_DESDOBRAMENTO':
            valor = None
            proporcao = None
            ativo_gerado = id_ativo
            prop_grup = cols[1].number_input("Prop. Grupamento %", format="%.2f")
            fator = (1/prop_grup) if prop_grup != 0 else 0
            cols[1].text(f"{fator} para 1")
            prop_desd = cols[1].number_input("Prop. Desdobramento %", format="%.2f")
            fator = (prop_desd + 100)/100
            cols[1].text(f"1 para {fator}")

            cols[3].markdown("### Resumo")
            quant_grup = quant_acum*prop_grup
            fracao = quant_grup - int(quant_grup)
            if int(quant_grup) > 0:
                cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {int(quant_grup) * fator} **Leilão Fração:** {fracao * fator}")
            else:
                cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** 0 **Leilão Fração:** {fracao * fator}")

            operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": "0", "qt": f"qt*{prop_grup}"},
                             {"id_ativo": f"{id_ativo}", "custo": "0", "qt": f"qt* {prop_desd/100} * {prop_grup}"}]

        elif tipo in ['ATUALIZAÇÃO']:
            valor = None
            proporcao = None
            c1_1, c1_2 = cols[2].columns([1,2], vertical_alignment="center")
            c1_1.markdown(f"**Novo Ativo:**")
            with c1_2.popover(st.session_state['novo_ativo']):
                st.text_input("Buscar Novo Ativo",key='busca_ativo', on_change=buscar_ativos, args=('busca_ativo', 'lista_ativo_cat_sugeridos'))  
                ativo_gerado = st.pills("Selecionar Novo",key='sl_ativo', 
                                        options=st.session_state['lista_ativo_cat_sugeridos'], 
                                        selection_mode='single', on_change=definir_ativo,
                                        args=('sl_ativo', 'novo_ativo'))
            with cols[2].container(horizontal=True):
                novo_qt = st.number_input("Qtd", format="%.5f")
           
            cols[3].markdown("### Resumo")
            cols[3].info(f"**Original:** {id_ativo} **Qtd:** {0} **Lucro** {0}")
            cols[3].success(f"**Novo:** {ativo_gerado} **Qtd:** {novo_qt} **Custo:** {custo_acum}")

            operacao_dict = [{"id_ativo": f"{ativo_gerado}", "custo": "0", "qt": f"{novo_qt}"},
                             {"id_ativo": f"{id_ativo}", "custo": "0", "qt": "0" }]

        elif tipo in ['CISÃO']:
            valor = None
            proporcao = None
            valor_orig = cols[1].number_input("Valor Redução ativo original", format="%.5f")

            c1_1, c1_2 = cols[2].columns([1,2], vertical_alignment="center")
            c1_1.markdown(f"**Novo Ativo:**")
            with c1_2.popover(st.session_state['novo_ativo']):
                st.text_input("Buscar Novo Ativo",key='busca_ativo', on_change=buscar_ativos, args=('busca_ativo', 'lista_ativo_cat_sugeridos'))  
                ativo_gerado = st.pills("Selecionar Novo",key='sl_ativo', 
                                        options=st.session_state['lista_ativo_cat_sugeridos'], 
                                        selection_mode='single', on_change=definir_ativo,
                                        args=('sl_ativo', 'novo_ativo'))
                
            with cols[2].container(horizontal=True):
                novo_qt = st.number_input("Qtd Novo", format="%.5f")
                novo_custo = st.number_input("Custo Novo", format="%.5f")

            cols[3].markdown("### Resumo")
            cols[3].info(f"**Original:** {id_ativo} **Qtd:** {quant_acum} **Custo:** {custo_acum - valor_orig}")
            cols[3].success(f"**Novo:** {ativo_gerado} **Qtd:** {novo_qt} **Custo:** {novo_custo}")

            operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": f"{-valor_orig}", "qt": "0"},
                             {"id_ativo": f"{ativo_gerado}", "custo": f"{novo_custo}", "qt": f"{novo_qt}" }]

        elif tipo in ['INCORPORAÇÃO']:
            valor = None
            proporcao = None
            valor_orig = cols[1].number_input("Valor venda (Custo + lucro)", format="%.5f")
            c1_1, c1_2 = cols[2].columns([1,2], vertical_alignment="center")
            c1_1.markdown(f"**Novo Ativo:**")
            with c1_2.popover(st.session_state['novo_ativo']):
                st.text_input("Buscar Novo Ativo",key='busca_ativo', on_change=buscar_ativos, args=('busca_ativo', 'lista_ativo_cat_sugeridos'))  
                ativo_gerado = st.pills("Selecionar Novo",key='sl_ativo', 
                                        options=st.session_state['lista_ativo_cat_sugeridos'], 
                                        selection_mode='single', on_change=definir_ativo,
                                        args=('sl_ativo', 'novo_ativo'))
            with cols[2].container(horizontal=True):
                novo_qt = st.number_input("Qtd", format="%.5f")
                novo_custo = st.number_input("Custo total", format="%.5f")
           
            cols[3].markdown("### Resumo")
            cols[3].info(f"**Original:** {id_ativo} **Qtd:** {0} **Lucro** {valor_orig - custo_acum}")
            cols[3].success(f"**Novo:** {ativo_gerado} **Qtd:** {novo_qt} **Custo:** {novo_custo}")


            operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": f"{valor_orig}", "qt": "-qt"},
                             {"id_ativo": f"{ativo_gerado}", "custo": f"{novo_custo}", "qt": f"{novo_qt}" }]
            
        elif tipo == 'REDUÇÃO DE CAPITAL' or tipo == 'OPA':
            proporcao = None
            valor = cols[1].number_input("Valor por cota", format="%.5f")
            ativo_gerado = None
            cols[3].markdown("### Resumo")
            if tipo == 'OPA':
                cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** 0 **Lucro:** {valor*quant_acum - custo_acum}")
                operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": f"{valor}*qt", "qt": "-qt"}]
            else:
                cols[3].info(f"**Valor atual:** {id_ativo} **Qtd:** {quant_acum} **Custo:** {custo_acum - valor*quant_acum}")
                operacao_dict = [{"id_ativo": f"{id_ativo}", "custo": f"{valor}*qt", "qt": "0"}]

        # Opção de Dinheiro Global
        if st.toggle('Configurar fórmula de recebimento em dinheiro'):
            dinheiro = st.number_input('Valor Dinheiro', value=1000.00, format="%.2f")

    evento_dict = {
                'fk_ativo': id_ativo,
                'ativo_gerado': ativo_gerado,
                'tipo': tipo,
                'data_aprov': data_aprov.isoformat(),
                'data_com': data_com.isoformat(),
                'data_pag': data_pag.isoformat(),
                'valor_base': valor,
                'proporcao': proporcao,
                'dinheiro': f"{dinheiro}",
                'operacao': operacao_dict
            }
    return evento_dict
#------------------------------------------------------------------------------------

evento_dict = render_layout_input()
if evento_dict['fk_ativo']:
    if st.button('💾 Inserir Evento Coorporativo'):
        insert_evento(evento_dict)
        st.session_state.evento_pessoal_dict = []