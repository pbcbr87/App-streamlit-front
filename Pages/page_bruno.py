import streamlit as st


st.header('Criado por Patrick Cangussu')

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Parâmetros das curvas IEC
iec_curves = {
    "Standard Inverse": {"k": 0.14, "alpha": 0.02},
    "Very Inverse": {"k": 13.5, "alpha": 1},
    "Extremely Inverse": {"k": 80, "alpha": 2},
    "Long Time Inverse": {"k": 120, "alpha": 1}
}

# Parâmetros das curvas IEEE
ieee_curves = {
    "Moderately Inverse": {"A": 0.0515, "B": 0.114, "p": 0.02},
    "Very Inverse": {"A": 19.61, "B": 0.491, "p": 2},
    "Extremely Inverse": {"A": 28.2, "B": 0.1217, "p": 2}
}

# Função para calcular tempo IEC
def calc_iec_time(I, Is, TMS, k, alpha):
    M = I / Is
    with np.errstate(divide='ignore', invalid='ignore'):
        t = TMS * k / (np.power(M, alpha) - 1)
        t[M <= 1] = np.nan
    return t

# Função para calcular tempo IEEE
def calc_ieee_time(I, Is, TD, A, B, p):
    M = I / Is
    with np.errstate(divide='ignore', invalid='ignore'):
        t = TD * (A / (np.power(M, p) - 1) + B)
        t[M <= 1] = np.nan
    return t

# Interface Streamlit
st.title("Gráfico de Curvas de Relés IDMT (IEC e IEEE)")

# Entradas do usuário
Is = st.number_input("Corrente de atuação (Is) [A]", min_value=1.0, value=100.0)
TMS = st.number_input("TMS (para curvas IEC)", min_value=0.01, value=0.1)
TD = st.number_input("TD (para curvas IEEE)", min_value=0.01, value=1.0)

selected_iec = st.multiselect("Selecionar curvas IEC", list(iec_curves.keys()), default=["Standard Inverse"])
selected_ieee = st.multiselect("Selecionar curvas IEEE", list(ieee_curves.keys()), default=["Moderately Inverse"])

# Corrente de falta para destacar ponto
highlight_current = st.number_input("Corrente de falta para destacar no gráfico [A]", min_value=Is * 1.01, value=Is * 5)

# Faixa de corrente
I = np.linspace(Is * 1.01, Is * 20, 500)

# Plotagem
fig, ax = plt.subplots()
for curve in selected_iec:
    params = iec_curves[curve]
    t = calc_iec_time(I, Is, TMS, params["k"], params["alpha"])
    ax.plot(I, t, label=f"IEC - {curve}")
    # Calcular ponto destacado
    t_point = calc_iec_time(np.array([highlight_current]), Is, TMS, params["k"], params["alpha"])[0]
    st.text(f"tempo de trip: {t_point} s")
    if not np.isnan(t_point):
        ax.plot(highlight_current, t_point, 'o', label=f"Ponto IEC - {curve}", markersize=8)

for curve in selected_ieee:
    params = ieee_curves[curve]
    t = calc_ieee_time(I, Is, TD, params["A"], params["B"], params["p"])
    ax.plot(I, t, label=f"IEEE - {curve}")
    # Calcular ponto destacado
    t_point = calc_ieee_time(np.array([highlight_current]), Is, TD, params["A"], params["B"], params["p"])[0]
    if not np.isnan(t_point):
        ax.plot(highlight_current, t_point, 'o', label=f"Ponto IEEE - {curve}", markersize=8)

ax.set_xlabel("Corrente de falta (A)")
ax.set_ylabel("Tempo de atuação (s)")
ax.set_title("Curvas de Tempo x Corrente para Relés IDMT")
ax.set_yscale("log")
ax.grid(True, which="both", linestyle="--", linewidth=0.5)
ax.legend()

st.pyplot(fig)