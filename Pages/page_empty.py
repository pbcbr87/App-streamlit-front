import streamlit as st


pagina = st.empty()

if st.button('pagina'):
    pagina.markdown("Poof!")

if st.button('pagina2'):
    pagina.markdown("opa!")