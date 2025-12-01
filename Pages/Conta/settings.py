import streamlit as st
import requests
import time


API_URL = 'https://pythonapi-production-6268.up.railway.app/'


@st.cache_data
def get_user(tk):
    usuario = requests.get(f'{API_URL}usuarios/', headers={'Authorization':f'Bearer {tk}'}).json()
    return usuario

def alterar_senha():
    try:
        get_token = requests.post(f'{API_URL}auth/token', {'username': st.session_state.get('user', ''), 'password': senha_atual}).json()
        if 'access_token' not in get_token:
            st.warning("Senha atual incorreta. Tente novamente.")
            return
    except Exception as e:
        print("Erro: ", e)
        st.warning(f'Conexão com backend, Detalhes: {e}')            
        return
            
    try:
        response = requests.put(endpoint, json=payload, headers={'Authorization': f'Bearer {token}'}) 

        if response.status_code == 200:
            st.success("✅ Senha alterada com sucesso! Você pode precisar fazer login novamente.")
            time.sleep(3)
            st.session_state.clear()
            st.rerun()                    
        else:
            erro_json = response.json()
            msg = erro_json.get('detail', 'A senha atual está incorreta ou outro erro ocorreu.')
            st.error(f"❌ Erro ao alterar senha: {msg}")
            return
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de conexão com a API: {e}")
        return
    
def alterar_cadastro():
    try:
        get_token = requests.post('{API_URL}auth/token', {'username': st.session_state.get('user', ''), 'password': senha_atual}).json()
        if 'access_token' not in get_token:
            st.warning("Senha atual incorreta. Tente novamente.")
            return
    except Exception as e:
        print("Erro: ", e)
        st.warning(f'Conexão com backend, Detalhes: {e}')            
        return
    
    try:
        response = requests.put(endpoint, json=payload, headers={'Authorization': f'Bearer {token}'})
        
        if response.status_code == 200:
            st.success("✅ Detalhes do perfil atualizados com sucesso!")
            time.sleep(3)
            # Atualizar a sessão
            st.session_state.nome = novo_nome
            st.session_state.user = novo_login
            st.session_state.email = novo_email
            
            try:
                get_token = requests.post(f'{API_URL}auth/token', {'username': novo_login, 'password': senha_atual}).json()
                if 'access_token' in get_token:
                    st.session_state.logado = True
                    st.session_state.token = get_token['access_token']
                    st.session_state.nome = get_user(get_token['access_token'])['nome']
                    st.session_state.user = get_user(get_token['access_token'])['login']
                    st.session_state.email = get_user(get_token['access_token'])['email']
                    st.session_state.id = get_user(get_token['access_token'])['id']
                    st.rerun()
            except Exception as e:
                print("Erro: ", e)
                st.warning(f'Conexão com backend, Detalhes: {e}')            
                st.session_state.logado = False 

        else:
            erro_json = response.json()
            msg = erro_json.get('detail', 'Erro na atualização de detalhes.')
            st.error(f"❌ Erro na Atualização: {msg}")

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de conexão com a API: {e}") 

    return


# --- Verificações de Sessão ---
if not st.session_state.get('logado'):
    st.error("Você precisa estar logado para editar seu perfil.")
    st.stop()

user_id = st.session_state.get('id')
token = st.session_state.get('token')

if not user_id or not token:
    st.error("Erro de sessão: ID ou Token ausentes. Faça login novamente.")
    st.session_state.clear()
    st.rerun()

# ----------------------------------------------------
# 1. LAYOUT CENTRALIZADO
# ----------------------------------------------------
container_main = st.container(width="stretch", horizontal_alignment="center")
col_center = container_main.columns([1, 4, 1])[1]

col_center.header("✏️ Editar Perfil de Usuário")
col_center.markdown("---")
# ----------------------------------------------------
# 2. FORMULÁRIO 1: DETALHES DO PERFIL (Nome, Login, Email)
# ----------------------------------------------------
col_center.subheader("Informações Básicas")

with col_center.form("edicao_detalhes_form", clear_on_submit=False):    
    # Pré-preenchimento
    novo_nome = st.text_input("Nome Completo", value=st.session_state.get('nome', ''), max_chars=100)
    novo_login = st.text_input("Nome de Usuário (Login)", value=st.session_state.get('user', ''), max_chars=50)
    novo_email = st.text_input("E-mail", value=st.session_state.get('email', ''), max_chars=100)
    senha_atual = st.text_input("Senha Atual", type='password', max_chars=50)

    submitted_detalhes = st.form_submit_button("Salvar Detalhes", type="primary")

    if submitted_detalhes:

        payload = {"nome": novo_nome, "login": novo_login, "email": novo_email}
        endpoint = f'{API_URL}usuarios/{user_id}' 
        
        with st.spinner("Atualizando detalhes do perfil..."):
            alterar_cadastro()

# ----------------------------------------------------
# 3. FORMULÁRIO 2: ALTERAR SENHA
# ----------------------------------------------------
expandir = col_center.expander("🔒 Alterar Senha", expanded=False)
expandir.subheader("🔒 Alterar Senha")

with expandir.form("edicao_senha_form", clear_on_submit=True):
   
    # ⚠️ Este campo é crucial para a segurança!
    senha_atual = st.text_input("Senha Atual", type='password', max_chars=50)
    nova_senha = st.text_input("Nova Senha", type='password', max_chars=50)
    confirmar_senha = st.text_input("Confirme a Nova Senha", type='password', max_chars=50)
    
    submitted_senha = st.form_submit_button("Atualizar Senha", type="secondary")

    if submitted_senha:
        
        # 1. Validações de Frontend
        if not all([senha_atual, nova_senha, confirmar_senha]):
            st.error("Preencha todos os campos para alterar a senha.")
            st.stop()
            
        if nova_senha != confirmar_senha:
            st.error("A nova senha e a confirmação não coincidem.")
            st.stop()            
       
        payload = {
            "nome": st.session_state.get('nome'),
            "login": st.session_state.get('user'),
            "email": st.session_state.get('email'),
            "senha": nova_senha # <--- Enviamos a NOVA senha
        }
        
        # 3. Envio para a API (PUT)
        endpoint = f'{API_URL}usuarios/{user_id}' 
        
        with st.spinner("Atualizando senha..."):
            alterar_senha()