import streamlit as st
import pandas as pd

# Configuracion de pagina
st.set_page_config(page_title="MovilGo", layout="wide", page_icon="🚌")

# --- LÓGICA DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🔐 Acceso MovilGo")
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            if usuario == "admin" and clave == "movil123":
                st.session_state['autenticado'] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# --- CUERPO DE LA APP ---
if not st.session_state['autenticado']:
    login()
else:
    # IMPORTACIÓN DENTRO DEL CUERPO PARA EVITAR ERRORES DE CARGA INICIAL
    import logic_programador as lp

    st.sidebar.title("MovilGo v1.1")
    opcion = st.sidebar.radio("Menú Principal", ["Inicio", "Gestión de Grupos", "Programador"])

    if opcion == "Inicio":
        st.title("Bienvenido al Sistema MovilGo")
        st.info("Seleccione un módulo en el menú de la izquierda para comenzar.")
    
    elif opcion == "Gestión de Grupos":
        lp.pantalla_gestion_grupos()

    elif opcion == "Programador":
        lp.pantalla_programador()
