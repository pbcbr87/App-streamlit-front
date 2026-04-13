import streamlit as st
import requests
import pandas as pd
from json import dumps, loads
import time
from settings import API_URL
from datetime import date

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Simulador de Eventos")

# --- ESTADO DA SESSÃO ---
if 'token' not in st.session_state:
    st.session_state['token'] = None  # Certifique-se de que o token existe

if 'lista_criada' not in st.session_state:
    st.session_state['lista_criada'] = None

def parse_date_native(val):
    if not val:
        return date.today()
    
    # Se já for um objeto date, apenas retorna ele
    if isinstance(val, date):
        return val
    
    # Se for uma string (comum ao vir do banco/JSON), converte
    if isinstance(val, str):
        try:
            # Tenta converter formato "YYYY-MM-DD" ou "YYYY-MM-DD HH:MM:SS"
            return date.fromisoformat(val[:10])
        except ValueError:
            return date.today()
            
    return date.today()

def sanitizar_evento(dict_evento):
    """Converte valores incompatíveis (NaN, NumPy tipos) para tipos nativos Python."""
    import numpy as np
    novo_dict = {}
    for k, v in dict_evento.items():
        if pd.isna(v) or v is np.nan:
            novo_dict[k] = None
        elif isinstance(v, (np.float64, np.float32)):
            novo_dict[k] = float(v)
        elif isinstance(v, (np.int64, np.int32)):
            novo_dict[k] = int(v)
        else:
            novo_dict[k] = v
    return novo_dict

def enviar_tabela(dataframe):
    linhas = dataframe.to_json(orient='records', date_format='iso')
    linhas = loads(linhas)
    tabela = dumps({"dados": linhas})
    
    resp = requests.post(f'{API_URL}eventos/inserir_eventos_tabela', tabela, headers={'Authorization':f'Bearer {st.session_state.token}'})
    try:
        resposta_json = resp.json()
    except:
        st.error(f"Erro na API. Status {resp.status_code}. Resposta de texto: {resp.text}")

        # --- Tratamento de Sucesso (200 OK) ---
    if resp.status_code == 200:
        st.success('✅ Dados enviados com sucesso!')          
    # --- Tratamento de Erro de Validação (422 Unprocessable Entity) ---
    elif resp.status_code == 422:
        st.error('❌ Existe dados inválidos no seu arquivo. Veja abaixo os detalhes:')
                            
        detail = resposta_json.get('detail', {})
        linhas_rejeitadas = detail.get('linhas_rejeitadas', [])
        
        if linhas_rejeitadas:
            st.warning(f"Foram encontradas {len(linhas_rejeitadas)} linha(s) com erro de validação.")
            df_erros = pd.DataFrame(linhas_rejeitadas)
            st.dataframe(df_erros)
        else:
            st.text(f"Detalhe de erro da API: {detail}")
    else:
        st.error(f"⚠️ Erro HTTP inesperado: Status {resp.status_code}")

# --- FUNÇÕES DE LÓGICA (API) ---
def api_request_simular(evento, operacao_param, posicao):
    headers = {'Authorization': f'Bearer {st.session_state.token}'}
    params = {
        'ev_json': evento,
        'posicao': posicao,
        'operacao_param': operacao_param
    }
    
    try:
        resp = requests.get(f'{API_URL}eventos/simular_evento', params=params, headers=headers)
        
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 422:
            st.error('❌ Dados inválidos no arquivo.')
            detail = resp.json().get('detail', {})
            if 'linhas_rejeitadas' in detail:
                st.dataframe(pd.DataFrame(detail['linhas_rejeitadas']))
            return None
        else:
            st.error(f"Erro na API: {resp.status_code}")
            return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

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

# --- INTERFACE DE USUÁRIO (UI) ---
def render_layout_input():
    """Renderiza os campos de entrada e retorna o dicionário de parâmetros."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader('💰 Carteira para Teste')
        c1, c2 = st.columns(2)
        with c1:
            quant_acum = st_number_input_custom("Qtd Cotas (qt)",  value="100,00")
        with c2:
            custo_acum = st_number_input_custom("Custo Acumulado", value="10.000,00")
    
    with col2:
        st.subheader('📅 Período do Evento')
        c1, c2, c3 = st.columns(3)
        
        evento = st.session_state.get('evento_pedente_sel') or {}

        val_aprov = parse_date_native(evento.get('data_aprov'))
        val_com = parse_date_native(evento.get('data_com'))
        val_pag = parse_date_native(evento.get('data_pag'))

        data_aprov = c1.date_input('Aprovação', format="DD/MM/YYYY", min_value=date(2000, 1, 1), value=val_aprov if val_aprov >= date(2000, 1, 1) else date(2000, 1, 1))
        data_com = c2.date_input('Data Com', format="DD/MM/YYYY", min_value=date(2000, 1, 1), value=val_com if val_com >= date(2000, 1, 1) else date(2000, 1, 1))
        data_pag = c3.date_input('Pagamento', format="DD/MM/YYYY", min_value=date(2000, 1, 1), value=val_pag if val_pag >= date(2000, 1, 1) else date(2000, 1, 1))

    st.divider()
    
    # Lista de tipos e seleção
    tipo_list = ['ATUALIZAÇÃO', 'BONIFICAÇÃO', 'CISÃO', 'DESDOBRAMENTO', 'FRAÇÃO', 
                 'GRUPAMENTO', 'GRUPAMENTO_DESDOBRAMENTO', 'INCORPORAÇÃO', 'OPA', 'REDUÇÃO DE CAPITAL']
    
    tipo = st.selectbox('Tipo de Evento', tipo_list, index=tipo_list.index(evento.get('tipo', 'ATUALIZAÇÃO')))
    
    # Campos dinâmicos baseados no tipo
    inputs = {
        "id_ativo": None, "ativo_gerado": None, "proporcao": 0.0, "valor": 0.0,
        "grupamento": 0.0, "desdobramento": 0.0, "pro_ativo": 0.0, "pro_gerado": 0.0,
        "valor_gerado": 0.0, "operacao": None, "dinheiro": None
    }

    container = st.container(border=True)
    with container:
        cols = st.columns(3)
        
        # Campos comuns para quase todos
        inputs["id_ativo"] = cols[0].text_input("ID Ativo Original", value= evento.get('fk_ativo', None))
            
        if tipo == 'BONIFICAÇÃO':
            inputs["ativo_gerado"] = inputs["id_ativo"]
            inputs["valor"] = cols[1].number_input("Valor por cota", format="%.5f")
            inputs["proporcao"] = cols[2].number_input("Proporção", format="%.5f")
            
        elif tipo == 'DESDOBRAMENTO' or tipo == 'GRUPAMENTO':
            inputs["ativo_gerado"] = inputs["id_ativo"]
            inputs["proporcao"] = cols[1].number_input("Proporção", format="%.5f")
            
        elif tipo == 'GRUPAMENTO_DESDOBRAMENTO':
            inputs["ativo_gerado"] = inputs["id_ativo"]
            inputs["grupamento"] = cols[1].number_input("Prop. Grupamento", format="%.5f")
            inputs["desdobramento"] = cols[2].number_input("Prop. Desdobramento", format="%.5f")

        elif tipo in ['ATUALIZAÇÃO']:
            inputs["ativo_gerado"] = cols[1].text_input("ID Novo Ativo")
            inputs["proporcao"] = cols[2].number_input("Proporção", format="%.5f")

        elif tipo in ['CISÃO']:
            inputs["ativo_gerado"] = cols[1].text_input("ID Novo Ativo")
            
            use_formula = st.toggle('Usar fórmula')
            if use_formula:
                default_json = '[{"id_ativo": "EXEMPLO", "custo": "custo * 0.15", "qt": "qt * 0.25"}]'
                raw_op = st.text_area('Fórmula da Operação (JSON)', value=default_json)
                try: inputs["operacao"] = loads(raw_op)
                except: st.error("JSON de operação inválido")
            else:
                inputs["proporcao"] = cols[2].number_input("Proporção qt nova", format="%.5f")
                c1, c2, c3 = st.columns([3, 3, 1])
                inputs["pro_ativo"] = c1.number_input("Redução ativo original", format="%.5f")
                if c3.toggle("Valor"):
                    inputs["valor_gerado"] =c2.number_input("Valor por cota novo", format="%.5f")
                else:
                    inputs["pro_gerado"] = c2.number_input("Proporção por cota novo", format="%.5f")

        elif tipo in ['INCORPORAÇÃO']:
            inputs["ativo_gerado"] = cols[1].text_input("ID Novo Ativo")
            if st.toggle('FII'):
                with cols[2]:
                    inputs["proporcao"] = st_number_input_custom("Proporção qt nova %")
                    inputs["valor_gerado"] = st_number_input_custom("Valor por cota novo")
                with cols[0]:
                    valor_venda = st_number_input_custom("Valor de venda")
                with cols[1]:
                    valor_dinheiro = st_number_input_custom("Valor em dinheiro")
                    inputs["dinheiro"] = f"({valor_dinheiro} * qt) - 0.2 * (qt * {valor_venda} - custo) if (qt *  {valor_venda} - custo) > 0 else {valor_dinheiro}  * qt"
                st.text(f"Formula Dinheiro:")
                st.text(f"{inputs["dinheiro"]} = {(valor_dinheiro * quant_acum) - 0.2 * (quant_acum * valor_venda - custo_acum) if (quant_acum *  valor_venda - custo_acum) > 0 else valor_dinheiro  * quant_acum}")

            else:
                use_formula = st.toggle('Usar fórmula')
                if use_formula:
                    default_json = '[{"id_ativo": "EXEMPLO", "custo": "custo * 0.15", "qt": "qt * 0.25"}]'
                    raw_op = st.text_area('Fórmula da Operação (JSON)', value=default_json)
                    try: inputs["operacao"] = loads(raw_op)
                    except: st.error("JSON de operação inválido")
                else:
                    with cols[2]:
                        inputs["proporcao"] = st_number_input_custom("Proporção qt nova %")
                    with st.container(horizontal=True):
                        if st.toggle("Valor"):
                            inputs["valor_gerado"] = st_number_input_custom("Valor por cota novo")
        elif tipo == 'REDUÇÃO DE CAPITAL':
            inputs["ativo_gerado"] = inputs["id_ativo"]
            inputs["valor"] = cols[1].number_input("Valor por cota", format="%.5f")

        elif tipo == 'OPA' or tipo == 'FRAÇÃO':
            inputs["valor"] = cols[1].number_input("Valor por cota", format="%.5f")

    # Opção de Dinheiro Global
    if st.toggle('Configurar fórmula de recebimento em dinheiro'):
        inputs["dinheiro"] = st.text_area('Fórmula Dinheiro', value="(0.56 * qt)")

    return tipo, inputs, quant_acum, custo_acum, data_aprov, data_com, data_pag

# --- FLUXO PRINCIPAL ---

# Header e Navegação
t1, t2, t3 = st.columns([5, 1, 1])
t1.title("🛠️ Simulação de Eventos Corporativos")
if t2.button("⬅️ Mains Eventos", width='stretch'):
    st.switch_page('Pages/Evento/eventos_cadastrados.py')

if t3.button("🧐 Eventos Pendentes", width='stretch'):
    st.switch_page('Pages/Evento/eventos_pendentes.py')

if 'evento_pedente_sel' in st.session_state and st.session_state['evento_pedente_sel'] is not None:
   st.header("Evento Pendente Selecionado para Simulação")
   st.dataframe([st.session_state.evento_pedente_sel])

# Exibição dos Resultados
c1, c2, c3, c4, _ = st.columns([1, 1, 1, 1, 2])

if st.session_state['lista_criada']:  
    if c2.button('💾 Salvar', width="stretch"):
        evento_final = sanitizar_evento(st.session_state['lista_criada'][0])    
        df_envio = pd.DataFrame([evento_final])
        enviar_tabela(df_envio)
        st.session_state['lista_criada'] = None
        st.session_state['evento_pedente_sel'] = None
        
    if c3.button('📝 Modificar antes de enviar', width="stretch"):
        st.session_state['evento_dict'] = st.session_state['lista_criada'][0]
        st.switch_page('Pages/Evento/insert_evento.py')

    if c1.button(' Voltar', width="stretch"):
        st.session_state['lista_criada'] = None
        st.rerun()

    if c4.button('🗑️ Limpar', width="stretch"):
        st.session_state['lista_criada'] = None
        st.session_state['evento_pedente_sel'] = None
        st.rerun()

if st.session_state['lista_criada']:     
    st.success("✅ Simulação concluída!")
    # Exibe a prévia formatada (se existir no estado)
    if 'previa_df' in st.session_state:
        df = pd.DataFrame(st.session_state['previa_df'])
        # (Lógica de formatação de colunas aqui se desejar mostrar o DF formatado)
        st.subheader("Prévia do Cálculo")
        st.dataframe(df)

    st.subheader("Eventos Gerados")
    st.dataframe(pd.DataFrame(st.session_state['lista_criada']))

if not st.session_state['lista_criada']:
    tipo, inputs, q_acum, c_acum, d_aprov, d_com, d_pag = render_layout_input()
    
    if st.button("🧪 Simular Evento", type="primary"):
        if q_acum <= 0:
            st.warning("Quantidade deve ser maior que zero.")
        else:
            # Montagem dos dicionários
            evento_dict = {
                'fk_ativo': inputs["id_ativo"],
                'ativo_gerado': inputs["ativo_gerado"],
                'tipo': tipo,
                'data_aprov': d_aprov.isoformat(),
                'data_com': d_com.isoformat(),
                'data_pag': d_pag.isoformat(),
                'valor_base': inputs["valor"],
                'proporcao': inputs["proporcao"],
                'dinheiro': inputs["dinheiro"],
                'operacao': None
            }
            
            posicao_dict = {'qt': str(q_acum), 'custo': str(c_acum)}
            
            with st.spinner('Processando...'):
                resp = api_request_simular(dumps(evento_dict), dumps(inputs), dumps(posicao_dict))
                
                if resp and len(resp[0]) >= 2:
                    st.session_state['lista_criada'] = resp[1]
                    st.session_state['previa_df'] = resp[0]
                    st.rerun()
                else:
                    st.warning("A simulação não retornou dados suficientes. Verifiar data_com e data_pag.")