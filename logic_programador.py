import streamlit as st
from datetime import time

def pantalla_programador():
    st.title("📅 Programador de Turnos")
    
    with st.container():
        st.subheader("Parámetros de Entrada")
        col1, col2 = st.columns(2)
        
        with col1:
            mes = st.selectbox("Mes a programar", ["Mayo", "Junio", "Julio", "Agosto"])
            cant_personas = st.number_input("Conductores necesarios", min_value=1, value=5)
        
        with col2:
            h_inicio = st.time_input("Inicio del Turno", time(6, 0))
            h_fin = st.time_input("Fin del Turno", time(14, 0))
    
    st.divider()
    
    if st.button("🚀 Generar Programación"):
        st.info(f"Procesando programación para {mes}...")
        st.warning("Validando jornada semanal de 42 horas (Reforma Laboral)...")
        # Aquí irá el algoritmo que cruza los datos con el Excel
