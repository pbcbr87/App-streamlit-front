import streamlit as st
import requests
from decimal import Decimal
import pandas as pd
import numpy as np



def page_empty():
    resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'})
    if resp.status_code == 200:
        dict_resp = resp.json()

    for item in dict_resp:
        for item_key in item.keys():       
            try:
                item[item_key] = Decimal(item[item_key])
            except Exception:
                pass
        df_carteira_front = pd.DataFrame(dict_resp)
        for i in df_carteira_front['valor_plan_brl']:
            print(i, type(i))
        df_carteira_front['Aporte %'] = np.where(df_carteira_front['valor_plan_brl'] == 0,  'Valor', Decimal('0'))
    print(df_carteira_front['Aporte %'])

st.text('Ola')
st.button('Clique aqui', on_click=page_empty)