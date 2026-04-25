import streamlit as st
import requests
from decimal import Decimal
from settings import API_URL, MANUTENCAO
from streamlit_extras.cookie_manager import cookie_manager
import time
from datetime import datetime


# print("---------Inicio--------------")
# print(f'st.state: Logado: {st.session_state.logado if "logado" in st.session_state else None}, cmd Delete cookie: {st.session_state.deleteCookie if "deleteCookie" in st.session_state else None}, Ativar cookie: {st.session_state.ative_cookie if "ative_cookie" in st.session_state else None} ')

# ------------------------------------------------
# 1. FUNÇÃO CENTRALIZADA DE REQUESTS (BOA PRÁTICA)
# ------------------------------------------------
def api_request(method, endpoint, data=None, params=None, timeout=10):
    headers = {}
    if 'token' in st.session_state and st.session_state.token:
        headers['Authorization'] = f"Bearer {st.session_state.token}"
    
    url = f"{API_URL}{endpoint}"
    
    try:
        if method == 'GET':
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        return requests.post(url, headers=headers, data=data, timeout=timeout)
    except Exception as e:
        # Retorna o erro para ser identificado no st.error
        return e

def get_user_cached():
    resp = api_request('GET', 'usuarios/')
    if isinstance(resp, Exception):        
        st.error(f"❌ Erro de Conexão: {resp}")
        return None
    return resp.json() if resp and resp.status_code == 200 else None 

def reset_usuario():
    """
    Limpa todos os dados de sessão relacionados ao usuário,
    garantindo que não sobrem vestígios de acessos anteriores.
    """
    st.session_state.logado = False    
    keys_usuario = ['user', 'id', 'token', 'nome', 'email', 'admin']
    
    for key in keys_usuario:
        st.session_state[key] = None
    
    st.cache_data.clear()

#------------------------------------------------
#Congiguraçãoes iniciais
#------------------------------------------------
st.set_page_config(
    page_title="Legacy Seed - Gerenciamento de Investimentos",
    page_icon="imagens/icon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "# Aplicativo para gerenciamento de investimentos \ncriado por Patrick Cangussu"
    }
)

# Função que ajusta via CSS a paigina
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

try:
    # O retorno não precisa ser armazenado se é só para "acordar"
    resp = api_request('GET', '', timeout=2)
    if isinstance(resp, Exception):
        time.sleep(2)
except:
    pass # Ignoramos erros aqui, o foco é apenas o estímulo inicial

#------------------------------------------------
#Delcarar sessions
#------------------------------------------------
defaults = { "ative_cookie": True, "deleteCookie": False }
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.ative_cookie == True:
    manager = cookie_manager(key="LY_CM")
    if not manager.ready():
        st.info("Preparando ambiente de acesso...")
        if st.session_state.deleteCookie != True:
            st.stop()

if st.session_state.deleteCookie == True:
    manager.delete("LY_SID")
    if manager.get("LY_SID"):
        st.session_state.deleteCookie = False
        st.rerun()

if 'logado' not in st.session_state:
    token_do_cookie = manager.get("LY_SID")
    if token_do_cookie:
        st.session_state.token = token_do_cookie
        user_data = get_user_cached()
        if user_data:
            st.session_state.logado = True
            st.session_state.nome = user_data['nome'].upper()
            st.session_state.user = user_data['login'].upper()
            st.session_state.email = user_data['email'].upper()
            st.session_state.admin = user_data['admin']
            st.session_state.id = user_data['id']
        else:
            reset_usuario()
    else:
        reset_usuario()

if st.session_state.logado == False:
    reset_usuario()

if st.session_state.logado == True:
    st.session_state.ative_cookie = False

#------------------------------------------------
# Funções para paiginas
#------------------------------------------------
#Pagina Em manutenção
def maintenance_page_gif():    
# CSS para centralizar até os componentes nativos
    st.markdown(
        """
        <style>
            .stMain {
                text-align: center;
            }
            /* Centraliza o box do st.info */
            .stAlert {
                text-align: left; /* Mantém o texto do box legível, mas o box centralizado */
                display: inline-block;
                width: auto;
            }
            div[data-testid="stMarkdownContainer"] > p {
                text-align: center;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Layout centralizado
    col1, col2, col3 = st.columns([1, 4, 1])
    
    with col2:
        st.markdown("## 🚧 Manutenção em Andamento")
        
        # GIF com largura total da coluna
        st.image(
            "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExOGNucTV2c294ZHRjbm42bGNzeTdrYWVidHJ5M2hlb2Nlc3NzaGh4aiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Qu0jn2SFM8m193ghie/giphy.gif", 
            width='stretch'
        )

        st.markdown("#### Estamos realizando melhorias importantes para você.")
        st.markdown("Agradeço imensamente a sua compreensão e paciência!")

        # Espaçamento
        st.write("") 

        # O toque especial sobre o Thomas centralizado
        st.info(
            "👶 **Nota do Papai:** Pode demorar um pouquinho mais que o planejado... "
            "O **Thomas** está na fase que exige total atenção do pai, e por aqui, "
            "ele é sempre a prioridade número um! 💙"
        )

#Pagina de login
def login():
    with st.container(horizontal_alignment="center").form("login", width="content", enter_to_submit=True, clear_on_submit=True):
        a, b, c = st.columns([1,5,1], vertical_alignment="center")
        b.image('imagens/login.png', width="stretch")

        user_input = st.text_input('Usuário')
        senha_input = st.text_input('Senha', type='password')

        if st.form_submit_button("Acessar Sistema", use_container_width=True):
            if not user_input or not senha_input:
                st.warning('⚠️ Preencha usuário e senha.')
                return
            
            with st.status("Autenticando...", expanded=False) as status:
                resp = api_request('POST', 'auth/token', data={'username': user_input, 'password': senha_input})
                
                # 1. Tratamento de Erro de Conexão (Exception)
                if isinstance(resp, Exception):
                    status.update(label="Falha na conexão", state="error")
                    st.error(f"❌ Servidor offline. (Detalhe: {type(resp).__name__})")
                    reset_usuario()
                    return

                # 2. Sucesso (Status 200)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get('access_token')
                    if not token:
                        status.update(label="Erro na resposta", state="error")
                        st.error("API não retornou um token válido.")
                        return
                    # Se valido armazena o token no cookie por 10 dias (864000 segundos)
                    manager.set("LY_SID", token, max_age=864000, samesite="lax")
                    status.update(label="Sucesso!", state="complete")
                    
                    # Carrega dados do usuário
                    st.session_state.token = token
                    user_info = get_user_cached()
                    if user_info:
                        st.session_state.logado = True
                        st.session_state.token = token
                        st.session_state.nome = user_info['nome'].upper()
                        st.session_state.user = user_info['login'].upper()
                        st.session_state.email = user_info['email'].upper()
                        st.session_state.admin = user_info['admin']
                        st.session_state.id = user_info['id']
                        
                        status.update(label="Bem-vindo!", state="complete")
                        st.rerun()
                        return
                    else:
                        status.update(label="Erro de Perfil", state="error")
                        st.error("❌ Erro ao carregar perfil do usuário.")

                # 3. Erros de Credenciais (400, 401)
                elif resp.status_code in [400, 401]:
                    status.update(label="Acesso Negado", state="error")
                    st.error("🚫 Usuário ou senha incorretos.")
                
                # 4. Outros Erros
                else:
                    status.update(label="Erro Inesperado", state="error")
                    st.error(f"⚠️ Servidor retornou erro {resp.status_code}")

#Pagina de logut 
def logout():       
    st.session_state.deleteCookie = True
    st.session_state.ative_cookie = True    
    reset_usuario()

    st.title('Até breve')
    with st.spinner("Logging out"):
        time.sleep(3)
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
                    st.Page('Pages/Carteira/movimentacao.py', title='Movimentações'),
                    st.Page('Pages/Carteira/page_3.py', title='Planejar'),
                    st.Page('Pages/Carteira/page_4.py', title='Aporte')
                    ]
    
    imposto_renda_pages = [st.Page('Pages/Imposto_renda/imposto_renda.py', title='Bens Direito - BRL/USD'),
                            st.Page('Pages/Imposto_renda/resumo_vendas_mensal.py', title='Operações Comuns e FIIs - BRL')
                            ]

    evento_usuario_pages = [st.Page('Pages/Evento_usuario/evento_cadastrados.py', title='Gerenciar Eventos'),
                            st.Page('Pages/Evento_usuario/insert_evento_coorp.py', title='Inserir Evento Coorporativos')
                            ]

    evento_pages = [st.Page('Pages/Evento/eventos_cadastrados.py', title='Eventos Cadastrados'),
                    st.Page('Pages/Evento/eventos_pendentes.py', title='Evento Pendentes'),
                    st.Page('Pages/Evento/simular.py', title='Simular Evento'),
                    st.Page('Pages/Evento/insert_evento.py', title='Inserir Evento'),
                    st.Page('Pages/Evento/edit_evento.py', title='Editar Evento')
                    ]
    dividendos_usuarios_pages = [   
                                 st.Page('Pages/Dividendos_usuarios/dividendos_grafico.py', title='Gráfico de Dividendos'),
                                 st.Page('Pages/Dividendos_usuarios/dividendos_usuarios.py', title='Gerenciar Dividendos')
                                 ]

    dividendos_pages = [st.Page('Pages/Dividendos/dividendos_cadastrados.py', title='Dividendos Cadastrados')]
    ativos_pages = [st.Page('Pages/Ativos/ativos_cadastrados.py', title='Ativos Cadastrados')]

    admin_pages = [st.Page('Pages/Admin/create_user.py', title='Criar Usuário', icon=':material/person_add:')]

    pages = {"Sua Carteira": cateira_pages, "Remunerações Coorporativas": dividendos_usuarios_pages, "Imposto de Renda": imposto_renda_pages, "Eventos Coorporativos": evento_usuario_pages, "Conta": conta_pages}
    # pages = {"Manutençao": [st.Page(maintenance_page_gif, title='Manutenção')]}
    if st.session_state.admin == True:
        pages["Admin"] = admin_pages
        pages["Evento"] = evento_pages
        pages["Ativos"] = ativos_pages
        pages["Dividendos"] = dividendos_pages

    if MANUTENCAO and st.session_state.admin == False:
        pages = {"Manutençao": [st.Page(maintenance_page_gif, title='Manutenção')]}
        pg = st.navigation(pages, position="top")
        return pg
    
    pg = st.navigation(pages, position="top")    
    #Adicionar componentes na sidebar
    st.logo(image='imagens/icon_grande.png', size="large")
    with st.sidebar:
        st.image('imagens/login.png', width="stretch" )
        if st.button('🔄 Atualizar Carteira', type='primary', key='atualizar_carteira', width="stretch"):
            keys_para_limpar = [
                                    'carteira_api', 
                                    'carteira_api_aporte', 
                                    'operacao_api', 
                                    'evento_usuario_dict', 
                                    'dividendos_usuarios_api'
                                ]                                
            for key in keys_para_limpar:
                if key in st.session_state:
                    del st.session_state[key]

            with st.spinner("Calculando...", show_time=True):
                resp = api_request('GET', f'comandos_api/calcular/{st.session_state.id}', timeout=1000)
                
                # Verificação de erro de    REDE ou TIMEOUT
                if isinstance(resp, Exception):
                    st.error(f"Erro de conexão: {resp}") # Aqui você vê o erro real!
                
                # Verificação de erro da API (ex: 500 ou 404)
                elif resp.status_code != 200:
                    st.error(f"Erro na API ({resp.status_code}): {resp.text}")
                
                else:
                    st.success("Carteira atualizada!")
    return pg

#------------------------------------------------
#Executar navegação
ajustar_CSS_main()

pg = navegacao()
pg.run()

