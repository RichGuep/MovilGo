import streamlit as st
import pandas as pd
import os
from logic_programador import pantalla_programador

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
    st.sidebar.title("MovilGo v1.1")
    # Añadimos "Gestión de Grupos" como módulo independiente
    opcion = st.sidebar.radio("Menú Principal", ["Inicio", "Empleados", "Gestión de Grupos", "Programador"])

    if opcion == "Inicio":
        st.title("Bienvenido al Sistema MovilGo")
    
    elif opcion == "Empleados":
        # (Lógica de empleados que ya tienes)
        pass

    elif opcion == "Gestión de Grupos":
        from logic_programador import pantalla_gestion_grupos
        pantalla_gestion_grupos()

    elif opcion == "Programador":
        from logic_programador import pantalla_programador
        pantalla_programador()
