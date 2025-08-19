import streamlit as st


pagina = st.empty()

if st.button('pagina'):
    pagina.markdown("Poof!")
    st.switch_page('Pages/page_bruno.py')

if st.button('pagina2'):
    pagina.markdown("opa!")