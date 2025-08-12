import streamlit as st
import requests
import pandas as pd

st.title('Carteira')

resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})

carteira = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/pegar_carteira/', headers={'Authorization':f'Bearer {st.session_state.token}'})

df_carteira = pd.DataFrame(carteira.json())
df_carteira['%'] = 100 * df_carteira['custo_brl'] / df_carteira['custo_brl'].sum()

df_carteira = (df_carteira.style.format(precision=2, thousands=".", decimal=",", subset=['quant', 'custo_brl', 'custo_usd'])
                                .format(precision=0, thousands=".", decimal=",", subset=['peso', 'nota'])
                                .format(precision=2, thousands=".", decimal=",", subset=['%']))

st.dataframe(df_carteira, hide_index=True, column_config={
            "%": st.column_config.NumberColumn(
            "% (BRL)",
            help="Proporcação do ativo na carteira em BRL"
        )

    })
