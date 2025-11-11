import streamlit as st
import requests
from decimal import Decimal


#deixar visivel as session:
# st.write(st.session_state)
# st.context.cookies
#------------------------------------------------
API_URL = 'https://pythonapi-production-6268.up.railway.app/'
#------------------------------------------------
#Congiguraçãoes iniciais
#------------------------------------------------
st.set_page_config(
    page_title="Cartiera",
    page_icon=":material/finance_mode:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Aplicativo para gerenciamento de investimando \ncriado por Patrick Cangussu"
    }
)

def ajustar_CSS_main():
    """
    Injeta CSS para reduzir o tamanho do VALOR e AUMENTAR o tamanho do LABEL.
    O valor 'escala' controla o tamanho geral.
    """
    st.markdown(
        f"""
        <style>
        /* Regra Crítica: Remove o padding superior do container principal do Streamlit (Confirmado como eficaz) */
        .stMainBlockContainer {{
            padding-top: 2rem !important; 
            margin-top: 1rem !important;
        }}</style>
        """,
        unsafe_allow_html=True,
    )

# Função de busca e conversão de dados da carteira
@st.cache_data(show_spinner="Carregando e convertendo dados da carteira...")
def get_carteira_data(token: str) -> list:
    """Busca a carteira da API e converte strings numéricas para Decimal."""
    
    resp = requests.get(
        f'{API_URL}/carteira/pegar_carteira', 
        headers={'Authorization':f'Bearer {token}'}
    )
    
    if resp.status_code != 200:
        st.error(f"Erro ao carregar carteira: Status {resp.status_code}")
        return []
    
    dict_resp = resp.json()
    
    if not isinstance(dict_resp, list):
         # Lida com o erro de formato de API (visto em conversas anteriores)
         st.error(f"Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
         return []

    for item in dict_resp:
        for item_key, valor in item.items():
            if isinstance(valor, str):
                valor_limpo = valor.strip()
                if not valor_limpo:
                    continue
                try:
                    # A conversão de str para Decimal
                    item[item_key] = Decimal(valor_limpo)
                except Exception:
                    pass # Deixa como string se não for um número

    return dict_resp

@st.cache_data(show_spinner="Carregando operações...")
def get_operacoes(token):
    resp = requests.get(f'{API_URL}/ordem_input/pegar_ordens', headers={'Authorization':f'Bearer {token}'})   
    
    if resp.status_code != 200:
        st.error(f"Erro ao carregar carteira: Status {resp.status_code}")
        return []

    dict_resp = resp.json()
    if not isinstance(dict_resp, list):
        # Lida com o erro de formato de API (visto em conversas anteriores)
        st.error(f"Formato da API inesperado. Recebido tipo: {type(dict_resp)}")
        return []

    for item in dict_resp:
        for item_key, valor in item.items():
            if isinstance(valor, str):
                valor_limpo = valor.strip()
                if not valor_limpo:
                    continue
                try:
                    # A conversão de str para Decimal
                    item[item_key] = Decimal(valor_limpo)
                except Exception:
                    pass # Deixa como string se não for um número

    return dict_resp

#função para pegar o token de autenticação
@st.cache_data()
def get_user(tk):
    usuario = requests.get(f'{API_URL}/usuarios/', headers={'Authorization':f'Bearer {tk}'}).json()
    return usuario


ajustar_CSS_main()
#------------------------------------------------
#Delcarar sessions
#------------------------------------------------
if 'logado' not in st.session_state:    
    st.session_state.logado = False


if st.session_state.logado == False:
    st.session_state.user = None
    st.session_state.id = None
    st.session_state.token = None
    st.session_state.nome = None

if "user" not in st.session_state:    
    st.session_state.user = None
    st.session_state.id = None
    st.session_state.token = None
    st.session_state.nome = None

#------------------------------------------------
# Funções para paiginas
#------------------------------------------------
#Pagina de login
def login():
    with st.container(horizontal_alignment="center").form("login", width="content", enter_to_submit=True, clear_on_submit=True):
        st.header("Log in")
        user_input = st.text_input('User')
        senha_input = st.text_input('Senha', type='password')

        if st.form_submit_button("Log in"):
            if not user_input or not senha_input:
                st.warning('Usuário ou senha vazio')
                return
            
            try:
                resp = requests.post('https://pythonapi-production-6268.up.railway.app/auth/token', {'username': user_input, 'password': senha_input})
            except Exception as e:
                print("Erro: ", e)
                st.warning(f'Conexão com backend, Detalhes: {e}')            
                st.session_state.logado = False
                return

            if resp.status_code == 200:  
                token = resp_token.get('access_token', None)
                if not token:
                    st.error("API não enviou o Token de acesso.")
                    return
                
                st.session_state.logado = True
                st.session_state.token = token
                
                user_data =  get_user(st.session_state.token)
                
                st.session_state.nome = user_data['nome'].upper()
                st.session_state.user = user_data['login'].upper()
                st.session_state.email = user_data['email'].upper()
                st.session_state.admin = user_data['admin']
                st.session_state.id = user_data['id']
                
                st.rerun()
                return
            elif resp.status_code in [400, 401]:
                try:
                    resp_token = resp.json()
                    detail = resp_token.get('detail', 'Erro de autenticação desconhecido.')
                    if isinstance(detail, str):
                        st.error(f"Falha ao logar: {detail}")
                    else:
                        st.error("Falha ao logar. Verifique suas credenciais.")
                except Exception:
                    st.error("Resposta da API inválida ou credenciais incorretas.")                    
            else:
                # OUTROS ERROS DA API (5xx)
                st.error(f"Erro inesperado da API: Status {resp.status_code}")

#Pagina de logut 
def logout():
    st.cache_data.clear()
    st.session_state.clear()
    st.rerun()
#------------------------------------------------
#Extrutura de navegação sem login
#------------------------------------------------
def navegacao():
    if st.session_state.logado == False:
        pages = {"Login": [st.Page(login)],
                "extras": [st.Page('Pages/page_bruno.py', title='Bruno')]}
        pg = st.navigation(pages, position="hidden")
        return pg
        
    if  st.session_state.nome == "XXX" and st.session_state.email == "X@X.COM":
        st.warning('Por favor, atualize cadastro, email e altere sua senha.')
        pages = { "Conta": [st.Page("Pages/Conta/settings.py", title="Meus cadastro", icon=":material/settings:")]}
        pg = st.navigation(pages, position="sidebar")
        return pg
    #------------------------------------------------
    #Estrutura de navegação principal
    #------------------------------------------------
    conta_pages = [st.Page("Pages/Conta/home.py",title='inicio', icon=":material/home:"),
                    st.Page("Pages/Conta/settings.py", title="Meus cadastro", icon=":material/settings:"),
                    st.Page(logout, title='Sair', icon= ':material/logout:')    
                    ]
    cateira_pages = [st.Page('Pages/Carteira/page_2.py', title='Carteira', default=True),
                    st.Page('Pages/Carteira/page_1.py', title='Operações'),
                    st.Page('Pages/Carteira/page_3.py', title='Planejar'),
                    st.Page('Pages/Carteira/page_4.py', title='Aporte')
                    ]
    admin_pages = [st.Page('Pages/Admin/create_user.py', title='Criar Usuário', icon=':material/person_add:')]

    pages = {"Sua Carteira": cateira_pages, "Conta": conta_pages}

    if st.session_state.admin == True:
        pages["Admin"] = admin_pages

    pg = st.navigation(pages, position="sidebar")
    
    #Carregar dados da carteira na session
    if 'carteira_api' not in st.session_state or st.session_state['carteira_api'] is None:     
        st.session_state['carteira_api'] = get_carteira_data(st.session_state.token) 
    if 'operacao_api' not in st.session_state or st.session_state['operacao_api'] is None:    
        st.session_state['operacao_api'] = get_operacoes(st.session_state.token) 

    #Adicionar componentes na sidebar
    with st.sidebar:
        if st.button('Atualizar Carteira', type='primary', key='atualizar_carteira'):
            with st.spinner("Aguardando...", show_time=True):
                resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/comandos_api/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
                if resp.status_code == 200:
                    st.success("Carteira atualizada com sucesso!")
                    # Recarregar dados da carteira
                    get_carteira_data.clear()
                    get_operacoes.clear()
                    st.session_state['carteira_api'] = get_carteira_data(st.session_state.token)
                    st.session_state['operacao_api'] = get_operacoes(st.session_state.token) 
                else:
                    st.error(f"Erro ao atualizar carteira: Status {resp.status_code}")
    return pg

#------------------------------------------------
#Executar navegação
pg = navegacao()
pg.run()









