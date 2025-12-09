import streamlit as st
import requests


# Configuração da URL da API
# API_URL = 'https://pythonapi-production-6268.up.railway.app/'
API_URL = 'python_api.railway.internal'
endpoint = f"{API_URL}usuarios/"
token = st.session_state.get('token')

# ----------------------------------------------------
# 1. LAYOUT CENTRALIZADO
# ----------------------------------------------------
container_main = st.container(width="stretch", horizontal_alignment="center")
col_center = container_main.columns([1, 4, 1])[1] 

col_center.header("👤 Criar Nova Conta")
col_center.markdown("Preencha seus dados para se registrar no sistema.")
# ----------------------------------------------------
# 2. FORMULÁRIO: Cria o formulário de cadastro
# ----------------------------------------------------
with col_center.form("cadastro_form", clear_on_submit=True):
    # Campos de entrada
    nome = st.text_input("Nome Completo", max_chars=100)
    login = st.text_input("Nome de Usuário (Login)", max_chars=50)
    email = st.text_input("Email", max_chars=100)
    senha = st.text_input("Senha", type='password', max_chars=50)
    confirmar_senha = st.text_input("Confirme a Senha", type='password', max_chars=50)
        
    # Botão de submissão
    submitted = st.form_submit_button("Registrar")

    if submitted: 
        # 1. Validação simples no frontend
        if not all([nome, login, senha, confirmar_senha]):
            st.error("Todos os campos devem ser preenchidos.")
            st.stop()
        if senha != confirmar_senha:
            st.error("As senhas não coincidem.")
            st.stop()
        # 2. Preparação dos dados
        dados_cadastro = {"nome": nome, "login": login, "email": email, "senha": senha }

        # 3. Chamada à API    
        with st.spinner("Registrando novo usuário..."):
            try:
                response = requests.post(endpoint, json=dados_cadastro, headers={'Authorization':f'Bearer {token}'})
                if response.status_code == 201:
                    st.success("✅ Conta criada com sucesso!")

                elif response.status_code == 400:
                    erro_json = response.json()
                    msg = erro_json.get('detail', 'Erro de validação desconhecido.')
                    st.error(f"❌ Erro no Cadastro: {msg}")
                
                elif response.status_code == 401:
                    st.error("❌ Não autorizado. Verifique suas credenciais.") 
                
                else:
                    st.error(f"❌ Erro no servidor (Status: {response.status_code}). Tente novamente mais tarde.")

            except requests.exceptions.RequestException as e:
                st.error(f"❌ Erro de conexão com a API: {e}")

