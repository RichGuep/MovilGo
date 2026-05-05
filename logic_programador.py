import streamlit as st
import pandas as pd
import random
import io
from datetime import datetime, timedelta
from github import Github

# --- MÓDULO 1: GESTIÓN DE GRUPOS (Se hace una vez) ---
def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos - Cablemovil")
    st.info("Configura aquí la composición de los grupos (2-7-3) antes de ir al programador.")

    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            # Normalización rápida (ajusta según tus columnas reales)
            df_full = df_full.rename(columns={
                next(c for c in df_full.columns if 'cedu' in c.lower()): 'Cedula',
                next(c for c in df_full.columns if 'nomb' in c.lower()): 'Nombre',
                next(c for c in df_full.columns if 'carg' in c.lower()): 'Cargo',
                next(c for c in df_full.columns if 'empr' in c.lower()): 'Empresa'
            })
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            if 'Grupo' not in st.session_state.df_cable.columns: st.session_state.df_cable['Grupo'] = "Sin Asignar"
        except:
            st.error("Error cargando empleados.xlsx")
            return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎲 Mezclar Grupos Aleatoriamente"):
            # (Aquí va tu función asignar_grupos_aleatorio que ya definimos)
            from logic_programador import asignar_grupos_aleatorio # Asegúrate de tenerla en el mismo archivo
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with col2:
        if st.button("🚀 Sincronizar Grupos con GitHub"):
            # (Aquí va tu función guardar_en_github que ya definimos)
            from logic_programador import guardar_en_github
            if guardar_en_github(st.session_state.df_cable): st.success("Grupos guardados!")

    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)

# --- MÓDULO 2: PROGRAMADOR (Cálculo por fechas) ---
def pantalla_programador():
    st.title("📅 Programador de Turnos Operativos")
    
    st.subheader("Parámetros de Programación")
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        fecha_inicio = st.date_input("Fecha de Inicio", datetime.now())
    with col_f2:
        fecha_fin = st.date_input("Fecha de Fin", datetime.now() + timedelta(days=30))

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor a la de fin.")
        return

    # Generar lista de fechas
    lista_fechas = []
    curr = fecha_inicio
    while curr <= fecha_fin:
        lista_fechas.append(curr)
        curr += timedelta(days=1)

    if st.button("🚀 Generar Programación para este Rango"):
        st.divider()
        st.subheader(f"Calendario del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")
        
        # Lógica de asignación por fecha
        # (Aquí usamos la lógica de G1/G2 Sab y G3/G4 Dom que ya definimos)
        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        
        for fecha in lista_fechas:
            dia_semana = fecha.strftime('%a') # Mon, Tue...
            es_sabado = (fecha.weekday() == 5)
            es_domingo = (fecha.weekday() == 6)
            es_lunes = (fecha.weekday() == 0)

            for g_idx, grupo in enumerate(grupos):
                turno = ""
                # Descansos Contractuales
                if grupo in ["Grupo 1", "Grupo 2"] and es_sabado: turno = "DESC"
                elif grupo in ["Grupo 3", "Grupo 4"] and es_domingo: turno = "DESC"
                # Compensatorios Lunes
                elif es_lunes and grupo in ["Grupo 1", "Grupo 2"]: turno = "COMP"
                
                if turno == "":
                    # Rotación dinámica basada en la fecha para que cambien de turno
                    # Usamos el número de semana del año para rotar
                    semana_año = fecha.isocalendar()[1]
                    base = (g_idx + semana_año) % 4
                    opciones = ["T1", "T2", "T3", "REF"]
                    turno = opciones[base]
                
                resultados.append({
                    "Fecha": fecha.strftime('%d/%m/%Y'),
                    "Día": fecha.strftime('%A'),
                    "Grupo": grupo,
                    "Turno": turno
                })

        df_res = pd.DataFrame(resultados)
        
        # Mostrar por semanas para que no sea una tabla infinita
        for f_str in df_res["Fecha"].unique()[::7]: # Muestra bloques de 7 días
            bloque = df_res[df_res["Fecha"].isin(df_res["Fecha"].unique()[df_res["Fecha"].unique().tolist().index(f_str):df_res["Fecha"].unique().tolist().index(f_str)+7])]
            pivot = bloque.pivot(index="Grupo", columns="Fecha", values="Turno")
            
            def style_c(val):
                colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", 
                          "DESC": "#ff4b4b", "COMP": "#ffa500", "REF": "#bcbd22"}
                return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold;'
            
            st.dataframe(pivot.style.map(style_c), use_container_width=True)
