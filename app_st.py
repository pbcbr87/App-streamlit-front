import streamlit as st
import requests

#deixar visivel as session:
st.write(st.session_state)


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

# Faixa de corrente
I = np.linspace(Is * 1.01, Is * 20, 500)

# Plotagem
fig, ax = plt.subplots()
for curve in selected_iec:
    params = iec_curves[curve]
    t = calc_iec_time(I, Is, TMS, params["k"], params["alpha"])
    ax.plot(I, t, label=f"IEC - {curve}")

for curve in selected_ieee:
    params = ieee_curves[curve]
    t = calc_ieee_time(I, Is, TD, params["A"], params["B"], params["p"])
    ax.plot(I, t, label=f"IEEE - {curve}")

ax.set_xlabel("Corrente de falta (A)")
ax.set_ylabel("Tempo de atuação (s)")
ax.set_title("Curvas de Tempo x Corrente para Relés IDMT")
ax.set_yscale("log")
ax.grid(True, which="both", linestyle="--", linewidth=0.5)
ax.legend()

st.pyplot(fig)



#função para pegar o token de autenticação
@st.cache_data
def get_user(tk):
    usuario = requests.get(f'https://pythonapi-production-6268.up.railway.app/usuarios/', headers={'Authorization':f'Bearer {tk}'}).json()
    return usuario

#Delcarar sessions
if 'logado' not in st.session_state:    
    st.session_state.logado = False

if st.session_state.logado == False:
    st.session_state.user = None
    st.session_state.id = None
    st.session_state.token = None
    st.session_state.nome = None

if "user" not in st.session_state:    
    st.session_state.user = None
    st.session_state.id = None
    st.session_state.token = None
    st.session_state.nome = None

#Pagina de login
def login():
    st.header("Log in")
    
    user_input = st.text_input('User')
    senha_input = st.text_input('Senha')

    if st.button("Log in"):
        if (len(user_input) > 0) and (len(senha_input) > 0):
            try:
                get_token = requests.post('https://pythonapi-production-6268.up.railway.app/auth/token', {'username': user_input, 'password': senha_input}).json()
                if 'access_token' in get_token:
                    st.session_state.logado = True
                    st.session_state.token = get_token['access_token']
                    st.session_state.nome = get_user(get_token['access_token'])['nome']
                    st.session_state.user = get_user(get_token['access_token'])['login']
                    st.session_state.id = get_user(get_token['access_token'])['id']
                    st.rerun()
            except Exception as e:
                print("Erro: ", e)
                st.warning(f'Conexão com backend, Detalhes: {e}')            
                st.session_state.logado = False               
        else:
            st.warning('Usuário ou senha vazio')
     
#Pagina de logout
def home():
    st.text(f'Bem Vindo {st.session_state.nome}')
    st.text(f'User: {st.session_state.user}')
    st.text(f'Id: {st.session_state.id}')

    if st.button('Home'):
        st.session_state.logado = False
        st.session_state.user = None
        st.session_state.id = None
        st.session_state.token = None
        st.session_state.nome = None
        st.rerun()


#Extrutura de nevegação:
if st.session_state.logado == False:
    pg = st.navigation([st.Page(login)])
else:
    pg = st.navigation([st.Page(home,title='inicio'), st.Page(f'Pages/page_1.py', title='Operações'), st.Page('Pages/page_2.py', title='Carteira')])    
pg.run()






