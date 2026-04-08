import streamlit as st


st.title(f"👋 Bem-vindo(a), {st.session_state.nome}!")
st.markdown("---") # Linha divisória para separar o cabeçalho

st.header("Detalhes da Sua Conta")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="🔑 Nome de Usuário", value=st.session_state.user if st.session_state.user else "N/A")
    
with col2:
    st.metric(label="📧 E-mail de Contato", value=st.session_state.email if st.session_state.email else "Não fornecido")

with col3:
    st.info("Status: **Online**")

# 3. Área de Ação Principal (Botões)
st.markdown("---")
st.subheader("Ações Rápidas")

# Colunas para alinhar os botões
btn_col1, btn_col2, _ = st.columns([1, 1, 4])

# Botão Sair (mantido, mas estilizado)
with btn_col1:
    # Assumindo que 'Pages/page_2.py' é a página principal da carteira
    if st.button('Ver Carteira', type="primary"): 
        st.switch_page("Pages/Carteira/page_2.py")

