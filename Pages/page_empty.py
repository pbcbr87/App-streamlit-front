import streamlit as st


pagina = st.empty()

if st.button('pagina'):
    pagina.markdown("Poof!")
    st.Page('Pages/page_bruno.py')

if st.button('pagina2'):
    pagina.markdown("opa!")