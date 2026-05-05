import streamlit as st
from datetime import time

def pantalla_programador():
    st.title("📅 Programador de Turnos")
    
    st.subheader("Configuración de Turnos Mensuales")
    
    with st.form("form_programador"):
        col1, col2 = st.columns(2)
        
        with col1:
            mes = st.selectbox("Mes a Programar", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            cantidad_personal = st.number_input("Cantidad de personas necesarias por turno", min_value=1, value=5)
        
        with col2:
            hora_inicio = st.time_input("Hora de Inicio Jornada", time(6, 0))
            hora_fin = st.time_input("Hora de Fin Jornada", time(14, 0))
            empresa_filtro = st.multiselect("Filtrar por Empresa", ["Cablemovil", "Greenmovil"], default="Cablemovil")

        btn_generar = st.form_submit_button("🚀 Generar Programación")

    if btn_generar:
        st.divider()
        st.subheader(f"Resultados preliminares para {mes}")
        st.warning("Aplicando Ley 2101: Reducción de jornada laboral a 42 horas semanales.")
        # Aquí conectaremos la lógica de asignación por Cédula y Cargo
        st.info(f"Buscando disponibilidad para cubrir {cantidad_personal} cupos con personal de {empresa_filtro}...")
