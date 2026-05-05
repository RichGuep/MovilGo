import streamlit as st
import pandas as pd
from datetime import time

def pantalla_programador():
    st.title("📅 Programador Especializado: Cablemovil")
    
    # 1. Cargar datos de empleados
    try:
        df = pd.read_excel("empleados.xlsx")
        # Filtrar solo Cablemovil
        df_cable = df[df['Empresa'] == 'Cablemovil'].copy()
    except:
        st.error("Primero carga la base de datos en el menú Empleados.")
        return

    # 2. Parametrizador de Grupos
    st.subheader("🛠️ Configuración de Grupos")
    
    with st.expander("Definición de Reglas de Grupo", expanded=True):
        st.write("**Composición requerida por grupo (12 personas):**")
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("Masters", "2")
        col_r2.metric("Técnicos A", "7")
        col_r3.metric("Técnicos B", "3")

    # 3. Definición de Turnos
    st.subheader("⏰ Horarios de Trabajo")
    turnos = {
        "T1": "05:30 AM - 01:30 PM",
        "T2": "01:30 PM - 09:30 PM",
        "T3": "09:30 PM - 05:30 AM"
    }
    st.json(turnos)

    # 4. Asignación de Grupos
    st.subheader("📋 Asignación de Personal a Grupos")
    
    # Creamos una columna temporal de Grupo si no existe
    if 'Grupo' not in df_cable.columns:
        df_cable['Grupo'] = "Sin Asignar"

    # Editor para que Richard asigne quién va en qué grupo
    df_grupos = st.data_editor(
        df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], 
        column_config={
            "Grupo": st.column_config.SelectboxColumn(
                "Grupo",
                options=["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4", "Sin Asignar"],
                required=True,
            )
        },
        use_container_width=True,
        key="editor_grupos"
    )

    # 5. Validación de la composición del grupo
    if st.button("Validar Composición de Grupos"):
        for g in df_grupos['Grupo'].unique():
            if g == "Sin Asignar": continue
            
            sub_g = df_grupos[df_grupos['Grupo'] == g]
            count_m = len(sub_g[sub_g['Cargo'].str.contains('Master', na=False)])
            count_a = len(sub_g[sub_g['Cargo'].str.contains('Técnico A', na=False)])
            count_b = len(sub_g[sub_g['Cargo'].str.contains('Técnico B', na=False)])
            total = len(sub_g)

            st.write(f"### Análisis {g}")
            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"Total: {total}/12")
            c2.warning(f"Masters: {count_m}/2")
            c3.info(f"Tec A: {count_a}/7")
            c4.success(f"Tec B: {count_b}/3")

            if total == 12 and count_m == 2 and count_a == 7 and count_b == 3:
                st.success(f"✅ {g} cumple con la normativa.")
            else:
                st.error(f"❌ {g} no cumple con la estructura requerida.")
