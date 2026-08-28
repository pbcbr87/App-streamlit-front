import streamlit as st
import requests
import time
from settings import API_URL, MANUTENCAO
from streamlit_extras.cookie_manager import cookie_manager
from Pages.utils.components import renderizar_status_motor_sidebar, processar_notificacoes_pendentes
from Pages.utils.request_api import ( autenticar_usuario_api,
                                      executar_requisicao_disparar_update,
                                      obter_perfil_usuario_api,
                                      ApiRequestError
                                    )

print(f"---------Inicio--------------{time.time()}")
# print(f'st.state: Logado: {st.session_state.logado if "logado" in st.session_state else None}, cmd Delete cookie: {st.session_state.deleteCookie if "deleteCookie" in st.session_state else None}, Ativar cookie: {st.session_state.ative_cookie if "ative_cookie" in st.session_state else None} ')
# # print("Calculo em antamento: ", st.session_state.motor_em_andamento)
# print("-----------------------------")
# ------------------------------------------------
# 1. FUNÇÃO CENTRALIZADA DE REQUESTS (BOA PRÁTICA)
# ------------------------------------------------
def get_user_cached():
    """Busca o perfil do usuário logado usando o cliente padronizado."""
    try:
        return obter_perfil_usuario_api()
    except ApiRequestError as e:
        st.error(f"❌ {e.message}")
        return None

def reset_usuario():
    """
    Limpa todos os dados de sessão relacionados ao usuário,
    garantindo que não sobrem vestígios de acessos anteriores.
    """
    st.session_state.logado = False    
    keys_usuario = ['user', 'id', 'token', 'nome', 'email', 'admin']
    
    for key in keys_usuario:
        st.session_state[key] = None

    st.session_state.update_login_disparado = False

    for key in ['carteira_api', 
                'carteira_api_aporte', 
                'page_aportes',
                'page_aporte_rapido',
                'planejamento_guiado',
                'page_eventos',
                'operacao_api', 
                'evento_usuario_dict', 
                'dividendos_usuarios_api', 
                'page_movimentacao',
                'page_dividendos',
                'dados_carteira_cache']:
        if key in st.session_state:
            del st.session_state[key]

    st.cache_data.clear()

#------------------------------------------------
#Congiguraçãoes iniciais
#------------------------------------------------
st.set_page_config(
    page_title="Legacy Seed - 🫘 Plante o seu legado🌱",
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
    print(f"Ping inicial para acordar a API: {API_URL.rstrip('/')}/")
    # Ping inicial para 'acordar' a API caso esteja em sleep
    resp = requests.get(f"{API_URL.rstrip('/')}/", timeout=2)       
except Exception as e:
    print(f"Aguardando acordar a pagina 4seg: {e}")
    time.sleep(4)

#==========================================================
#Delcarar sessions
#==========================================================
# Inicializa a flag de controle na sessão se ela não existir
defaults = {
        "motor_em_andamento": False,
        "update_login_disparado": False,
        "ative_cookie": True,
        "deleteCookie": False,
    }
for key, value in defaults.items():
    st.session_state.setdefault(key, value)

# Só verificar cookie se foi ativado ou tever um reload(defaul == True)
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
    # Disparar Update do backend apenas uma vez por sessão para o usuário logado, evitando loops de requisições
    if not st.session_state.get('update_login_disparado', False):
        try:
            executar_requisicao_disparar_update(st.session_state.id)
            st.session_state.update_login_disparado = True  # Trava para não disparar de novo nos próximos reruns
        except ApiRequestError as e:
            print(f"[LOGIN UPDATE] Aviso/Erro ao disparar recálculo no login: {e.message}")
            st.session_state.update_login_disparado = True  # Marca como True para evitar loops

#==========================================================
# Funções para paiginas
#==========================================================
#------------------------------------------------
#Pagina Em manutenção
#------------------------------------------------
def maintenance_page_gif():
    if "main_aceito" not in st.session_state:
        st.session_state["main_aceito"] = False

    
    _, col, _ = st.columns([1,1,1])
    with col:
        container = st.container(horizontal=False, horizontal_alignment="center", vertical_alignment="center")
        with container:
            st.write("## 🚧 Manutenção em Andamento")
            
            # GIF com largura total da coluna
            st.image(
                "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExOGNucTV2c294ZHRjbm42bGNzeTdrYWVidHJ5M2hlb2Nlc3NzaGh4aiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Qu0jn2SFM8m193ghie/giphy.gif", 
                width=500
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

            if st.button("Seque o jogo. Vamos testar Juntos", type="primary"):
                st.session_state["main_aceito"] = True
                st.rerun()

#------------------------------------------------
#Pagina de login
#------------------------------------------------
def login():
    with st.container(horizontal_alignment="center"):
        with st.form("login", width="content", enter_to_submit=True):
            a, b, c = st.columns([1,5,1], vertical_alignment="center")
            try:
                b.image('imagens/login.png', width="stretch", caption="🫘 Plante o seu legado🌱")
            except Exception as e:
                pass

            user_input = st.text_input('Usuário', icon=":material/person:")
            senha_input = st.text_input('Senha', type='password', icon=":material/lock:")

            if st.form_submit_button("Acessar Sistema", width="stretch"):
                if not user_input or not senha_input:
                    st.warning('⚠️ Preencha usuário e senha.')
                    return
                with st.status("Autenticando...", expanded=False) as status:
                    try:
                        data = autenticar_usuario_api(user_input, senha_input)
                        token = data.get("access_token")

                        if not token:
                            status.update(
                                label="Erro na resposta", state="error"
                            )
                            st.error("API não retornou um token válido.")
                            return

                        # Guarda token no cookie (10 dias)
                        manager.set(
                            "LY_SID", token, max_age=864000, samesite="lax"
                        )
                        st.session_state.token = token

                        # Carrega perfil do usuário
                        user_info = get_user_cached()
                        if user_info:
                            st.session_state.logado = True
                            st.session_state.nome = user_info["nome"].upper()
                            st.session_state.user = user_info["login"].upper()
                            st.session_state.email = user_info["email"].upper()
                            st.session_state.admin = user_info["admin"]
                            st.session_state.id = user_info["id"]

                            status.update(label="Bem-vindo!", state="complete")
                            st.rerun()
                            return
                        else:
                            status.update( label="Erro de Perfil", state="error" )
                            st.error("❌ Erro ao carregar perfil do usuário.")

                    except ApiRequestError as e:
                        status.update(label="Falha no Acesso", state="error")

                        if e.status_code in (400, 401):
                            st.error("🚫 Usuário ou senha incorretos.")
                        else:
                            st.error(f"❌ {e.message}")

                        reset_usuario()
#------------------------------------------------
#Pagina de logut 
#------------------------------------------------
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
        pages = {"Login": [st.Page(login)]}
        pg = st.navigation(pages, position="hidden")
        return pg

    #------------------------------------------------
    #Estrutura de navegação principal
    #------------------------------------------------
    conta_pages = [
        st.Page("Pages/Conta/home.py", title="Início", icon="🏠"),
        st.Page("Pages/Conta/settings.py", title="Meu Cadastro", icon="⚙️"),
        st.Page(logout, title="Sair", icon="🚪"),
    ]

    cateira_pages = [
        st.Page("Pages/Carteira/dashboard_carteira.py", title="Composição", icon="📊", default=True),
        st.Page("Pages/Carteira/movimentacao.py", title="Movimentações", icon="📜"),
        st.Page("Pages/Carteira/eventos_usuario.py", title="Gerenciar Eventos", icon="🎁"),
    ]

    aporte_planejado_pages = [
        st.Page("Pages/Aporte/aporte_rapido.py", title="Onde Aportar Rápido", icon="🫗"),
        st.Page("Pages/Aporte/aporte_grupo.py", title="Onde Aportar Macro", icon="🚿"),
        st.Page("Pages/Aporte/planejar_guiado.py", title="Objetivos 🎯", icon="🍎"),
    ]

    imposto_renda_pages = [
        st.Page("Pages/Imposto_renda/imposto_renda.py", title="Bens Direito - BRL/USD", icon="🏛️"),
        st.Page("Pages/Imposto_renda/resumo_vendas_mensal.py", title="Operações Comuns e FIIs - BRL", icon="💱"),
        st.Page("Pages/Imposto_renda/rendimento.py", title="Rendimentos - BRL", icon="🧾"),
        st.Page("Pages/Imposto_renda/resumo_ano_exterior.py", title="Resumo Exterior - USD", icon="🌐"),
    ]

    dividendos_usuarios_pages = [
        st.Page("Pages/Dividendos_usuarios/dividendos_grafico.py", title="Gráfico de Dividendos 🤑", icon="📈"),
        st.Page("Pages/Dividendos_usuarios/dividendos_usuarios.py", title="Gerenciar Dividendos", icon="✍️"),
    ]

    evento_pages = [
        st.Page("Pages/Evento/eventos_cadastrados.py", title="Eventos Cadastrados", icon="📅"),
        st.Page("Pages/Evento/eventos_pendentes.py", title="Eventos Pendentes", icon="⏳"),
    ]

    dividendos_pages = [
        st.Page("Pages/Dividendos/dividendos_cadastrados.py", title="Dividendos Cadastrados", icon="💵")
    ]

    ativos_pages = [
        st.Page("Pages/Ativos/ativos_cadastrados.py", title="Ativos Cadastrados", icon="🏷️")
    ]

    admin_pages = [
        st.Page("Pages/Usuarios/create_user.py", title="Criar Usuário", icon="👤")
    ]

    status = "🟢"
    if st.session_state.motor_em_andamento == True:
        status = "🔄"
    elif st.session_state.motor_em_andamento == "ERRO":
        status = "🚫"
    user = f"{st.session_state.user}".title()
    texto_user = f"**{user}** {status}"

    if st.session_state.admin:
        texto_user = f"**{user}** {status} 🛡️"
    pages = {"🏦 Sua Carteira": cateira_pages, 
             "💰 Remunerações 🧺": dividendos_usuarios_pages, 
             "💧 Aporte e Objetivos 🌳": aporte_planejado_pages, 
             "🏛️ Imposto de Renda": imposto_renda_pages,
             texto_user: conta_pages}
    
    if st.session_state.admin == True:
        pages["Usuarios 🛡️"] = admin_pages
        pages["Eventos 🛡️"] = evento_pages
        pages["Ativos 🛡️"] = ativos_pages
        pages["Dividendos 🛡️"] = dividendos_pages

    if MANUTENCAO and st.session_state.admin == False and not st.session_state.get("main_aceito", False):
        pages = {"Manutenção": [st.Page(maintenance_page_gif, title='Manutenção')]}
        pg = st.navigation(pages, position="top")
        return pg
    
    pg = st.navigation(pages, position="top")    
    #Adicionar componentes na sidebar
    st.logo(image='imagens/icon_grande.png', size="large")
    with st.sidebar:        
        st.image('imagens/login.png', width="stretch" )
        renderizar_status_motor_sidebar(st.session_state.id)

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

            # Reutilizando a função padronizada para o botão manual também!
            try:
                executar_requisicao_disparar_update(st.session_state.id)
                st.toast("Cálculo da carteira iniciado em background!", icon="🚀")
            except ApiRequestError as e:
                st.toast(f"Erro ao disparar recálculo: {e.message}")   
    return pg

#------------------------------------------------
#Executar navegação
#------------------------------------------------
ajustar_CSS_main()
processar_notificacoes_pendentes()
pg = navegacao()
pg.run()

