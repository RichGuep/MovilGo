import streamlit as st
import pandas as pd
from logic_programador import pantalla_programador

# Configuración de la página
st.set_page_config(page_title="MovilGo", layout="wide", page_icon="🚌")

# --- LÓGICA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def login():
    st.title("🔐 Acceso MovilGo")
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if usuario == "admin" and clave == "movil123": # Puedes cambiar estas credenciales
            st.session_state['autenticado'] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# --- CONTROL DE NAVEGACIÓN ---
if not st.session_state['autenticado']:
    login()
else:
    st.sidebar.title("Menú MovilGo")
    opcion = st.sidebar.radio("Seleccione una opción", ["Inicio", "Empleados", "Programador"])

    if opcion == "Inicio":
        st.title("Bienvenido Richard")
        st.write("Sistema de programación de turnos para Greenmóvil.")

    elif opcion == "Empleados":
        st.title("👥 Base de Datos de Personal")
        try:
            # Aquí cargamos tu archivo empleados.xlsx
            df = pd.read_excel("empleados.xlsx")
            st.info("Puedes editar la tabla directamente y presionar Guardar.")
            
            # Editor interactivo
            df_editado = st.data_editor(df, num_rows="dynamic")
            
            if st.button("💾 Guardar Cambios"):
                df_editado.to_excel("empleados.xlsx", index=False)
                st.success("¡Base de datos actualizada!")
        except Exception as e:
            st.error("Error: No se encontró el archivo 'empleados.xlsx'. Asegúrate de subirlo a la carpeta del proyecto.")

    elif opcion == "Programador":
        pantalla_programador()
