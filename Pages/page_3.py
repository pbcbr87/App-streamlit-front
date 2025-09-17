import streamlit as st
import requests
import pandas as pd
import numpy as np
from plotly import graph_objects as go
import plotly.express as px


if st.session_state['carteira_api'] == False:
    #resp = requests.get(f'https://pythonapi-production-6268.up.railway.app/Calcular/calcular/{st.session_state.id}', headers={'Authorization':f'Bearer {st.session_state.token}'})
    st.session_state['carteira_api'] = requests.get(f'https://pythonapi-production-6268.up.railway.app/carteira/pegar_carteira', headers={'Authorization':f'Bearer {st.session_state.token}'}).json()

if st.session_state['carteira_api'] == []:
    st.write('Carteira vazia ou não calculada')
if not st.session_state['carteira_api'] == []:
    df_carteira = pd.DataFrame(st.session_state['carteira_api'])

    df_carteira_front = pd.DataFrame()
    df_carteira_front['Código ativo'] = df_carteira['codigo_ativo']
    df_carteira_front['Categoria'] = df_carteira['categoria']
    df_carteira_front['País'] = df_carteira['pais']
    df_carteira_front['Nome'] = df_carteira['nome']
    df_carteira_front['Setor'] = df_carteira['setor']
    df_carteira_front['Qt'] = df_carteira['quant']
    df_carteira_front['Custo'] = df_carteira['custo_brl']
    df_carteira_front['Valor de mercado'] = df_carteira['valor_mercado_brl']
    df_carteira_front['Lucro'] = df_carteira['lucro_brl']
    df_carteira_front['Lucro %'] = df_carteira['%_lucro']
    df_carteira_front['Peso'] = df_carteira['peso']
    df_carteira_front['Nota'] = df_carteira['nota']
    df_carteira_front['Valor Planejado'] = df_carteira['valor_plan_brl']
    df_carteira_front['Aporte'] = df_carteira_front['Valor Planejado'] - df_carteira_front['Valor de mercado']
    df_carteira_front['Aporte %'] = df_carteira_front['Aporte']/df_carteira_front['Valor Planejado']
    
    df_carteira_st = (df_carteira_front.style.format(precision=2, thousands=".", decimal=",", subset=['Qt',
                                                                                                    'Custo',
                                                                                                    'Valor de mercado',
                                                                                                    'Lucro',
                                                                                                    'Valor Planejado',
                                                                                                    'Aporte'])
                                            .format(precision=0, thousands=".", decimal=",", subset=['Peso', 'Nota'])
                                            .format(precision=2, thousands=".", decimal=",", subset=['Lucro %', 'Aporte %'])
                                            )
    st.dataframe(df_carteira_st, hide_index=True, use_container_width=True,
                    column_config={
                        "Lucro %": st.column_config.NumberColumn("Lucro %", format="percent"),
                        "Aporte %": st.column_config.NumberColumn("Aporte %", format="percent")
                        })