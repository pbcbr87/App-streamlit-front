import streamlit as st
import requests

#deixar visivel as session:
st.write(st.session_state)

#Congiguraçãoes iniciais
st.set_page_config(
    page_title="Cartiera",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Aplicativo para gerenciamento de investimando \ncriado por Patrick Cangussu"
    }
)

#função para pegar o token de autenticação
@st.cache_data
def get_user(tk):
    usuario = requests.get(f'https://pythonapi-production-6268.up.railway.app/usuarios/', headers={'Authorization':f'Bearer {tk}'}).json()
    return usuario

#Delcarar sessions
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

#Pagina de login
def login():
    st.header("Log in")
    
    with st.form("login", width="content"):
        user_input = st.text_input('User')
        senha_input = st.text_input('Senha', type='password')
        
        
        
        if st.form_submit_button("Log in"):
            if (len(user_input) > 0) and (len(senha_input) > 0):
                try:
                    get_token = requests.post('https://pythonapi-production-6268.up.railway.app/auth/token', {'username': user_input, 'password': senha_input}).json()
                    if 'access_token' in get_token:
                        st.session_state.logado = True
                        st.session_state.token = get_token['access_token']
                        st.session_state.nome = get_user(get_token['access_token'])['nome']
                        st.session_state.user = get_user(get_token['access_token'])['login']
                        st.session_state.id = get_user(get_token['access_token'])['id']
                        st.rerun()
                except Exception as e:
                    print("Erro: ", e)
                    st.warning(f'Conexão com backend, Detalhes: {e}')            
                    st.session_state.logado = False               
            else:
                st.warning('Usuário ou senha vazio')
     
#Pagina Home
def home():
    st.text(f'Bem Vindo {st.session_state.nome}')
    st.text(f'User: {st.session_state.user}')
    st.text(f'Id: {st.session_state.id}')

    if st.button('Sair :material/logout:'):
        st.session_state.logado = False
        st.session_state.user = None
        st.session_state.id = None
        st.session_state.token = None
        st.session_state.nome = None
        st.rerun()

#Pagina de logut 
def logout():
    st.session_state.logado = False
    st.session_state.user = None
    st.session_state.id = None
    st.session_state.token = None
    st.session_state.nome = None
    st.rerun()

#Extrutura de nevegação:
if st.session_state.logado == False:
    pages = {"1": [st.Page(login)], "2": [st.Page('Pages/page_bruno.py', title='Bruno')]}
else:
    pages = {
    "Home": [st.Page(home,title='inicio', default=True),
             st.Page(logout, title='Sair', icon= ':material/logout:')    
    ],
    "Sua Carteira": [
        st.Page('Pages/page_1.py', title='Operações'),
        st.Page('Pages/page_2.py', title='Carteira')
    ],
    "Testes": [
        st.Page('Pages/page_empty.py', title='Empty')
    ],
    }            

pg = st.navigation(pages, position="top")
pg.run()






