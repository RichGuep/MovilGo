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
    st.sidebar.title("MovilGo v1.0")
    opcion = st.sidebar.radio("Menú Principal", ["Inicio", "Empleados", "Programador"])

    if opcion == "Inicio":
        st.title("Bienvenido al Sistema MovilGo")
        st.write("Gestión operativa de planta de personal.")

    elif opcion == "Empleados":
        st.title("👥 Base de Datos de Personal")
        
        if os.path.exists("empleados.xlsx"):
            df = pd.read_excel("empleados.xlsx")
            
            st.info("Puedes editar los datos (Nombre, Cargo, Salario, etc.) directamente en la tabla.")
            # Editor configurado con tus columnas
            df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 Guardar Cambios en Excel"):
                df_editado.to_excel("empleados.xlsx", index=False)
                st.success("¡Archivo 'empleados.xlsx' actualizado correctamente!")
        else:
            st.error("No se encontró el archivo 'empleados.xlsx'. Por favor, colócalo en la misma carpeta que este script.")

    elif opcion == "Programador":
        pantalla_programador()
