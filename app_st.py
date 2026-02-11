import streamlit as st
import requests
from decimal import Decimal
from settings import API_URL, MANUTENCAO

#deixar visivel as session:
# st.write(st.session_state)
# st.context.cookies
#------------------------------------------------
# API_URL = 'https://pythonapi-production-6268.up.railway.app/'
# API_URL = 'python_api.railway.internal'
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

#função para pegar o token de autenticação
def get_user(token: str):
    usuario = requests.get(f'{API_URL}usuarios/', headers={'Authorization':f'Bearer {token}'}).json()
    return usuario


ajustar_CSS_main()
#------------------------------------------------
#Delcarar sessions
#------------------------------------------------
if 'logado' not in st.session_state or st.session_state.logado == False:    
    st.session_state.logado = False
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
        st.header("Log in")
        user_input = st.text_input('User')
        senha_input = st.text_input('Senha', type='password')

        if st.form_submit_button("Log in"):
            if not user_input or not senha_input:
                st.warning('Usuário ou senha vazio')
                return
            
            try:
                resp = requests.post(f'{API_URL}auth/token', {'username': user_input, 'password': senha_input})
            except Exception as e:
                print("Erro: ", e)
                st.warning(f'Conexão com backend, Detalhes: {e}')            
                st.session_state.logado = False
                return

            if resp.status_code == 200:         
                resp_token = resp.json()
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
                    st.Page('Pages/Carteira/movimentacao.py', title='Movimentações'),
                    st.Page('Pages/Carteira/page_3.py', title='Planejar'),
                    st.Page('Pages/Carteira/page_4.py', title='Aporte')
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

    pages = {"Sua Carteira": cateira_pages, "Remunerações Coorporativas": dividendos_usuarios_pages, "Eventos Coorporativos": evento_usuario_pages, "Conta": conta_pages}
    # pages = {"Manutençao": [st.Page(maintenance_page_gif, title='Manutenção')]}
    if st.session_state.admin == True:
        pages["Admin"] = admin_pages
        pages["Evento"] = evento_pages
        pages["Ativos"] = ativos_pages
        pages["Dividendos"] = dividendos_pages

    if MANUTENCAO and st.session_state.admin == False:
        pages = {"Manutençao": [st.Page(maintenance_page_gif, title='Manutenção')]}
        pg = st.navigation(pages, position="sidebar")
        return pg
    pg = st.navigation(pages, position="sidebar")
    
    #Adicionar componentes na sidebar
    with st.sidebar:
        if st.button('Atualizar Carteira', type='primary', key='atualizar_carteira'):
            if 'carteira_api' in st.session_state:
                del st.session_state['carteira_api']
            if 'carteira_api_aporte' in st.session_state:
                del st.session_state['carteira_api_aporte']
            if 'operacao_api' in st.session_state:
                del st.session_state['operacao_api']
            if 'evento_usuario_dict' in st.session_state:
                del st.session_state['evento_usuario_dict']

            with st.spinner("Aguardando...", show_time=True):
                resp = requests.get(f'{API_URL}comandos_api/calcular/{st.session_state.get("id", 0)}', headers={'Authorization':f'Bearer {st.session_state.token}'})
                if resp.status_code == 200:
                    st.success("Carteira atualizada com sucesso!")
                else:
                    st.error(f"Erro ao atualizar carteira: Status {resp.status_code}")
    return pg

#------------------------------------------------
#Executar navegação
pg = navegacao()
pg.run()









