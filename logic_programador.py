import streamlit as st
import pandas as pd
import random
from datetime import time

def asignar_grupos_aleatorio(df_cable):
    """
    Lógica para armar grupos de 12 personas respetando:
    2 Master, 7 Tecnicos A, 3 Tecnicos B.
    """
    # Limpieza de datos básica para asegurar match de cargos
    df = df_cable.copy()
    
    # Separar por categorías usando filtros de texto
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1

    # Bucle de construcción de grupos
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): 
            p = masters.pop()
            p['Grupo'] = f"Grupo {num_grupo}"
            grupos_finales.append(p)
            
        for _ in range(7): 
            p = tecnicos_a.pop()
            p['Grupo'] = f"Grupo {num_grupo}"
            grupos_finales.append(p)
            
        for _ in range(3): 
            p = tecnicos_b.pop()
            p['Grupo'] = f"Grupo {num_grupo}"
            grupos_finales.append(p)
        
        num_grupo += 1

    # Manejo de sobrantes
    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes:
        s['Grupo'] = "Sin Asignar / Reserva"
    
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def pantalla_programador():
    st.title("📅 Programador MovilGo - Cablemovil")

    # 1. Carga de datos desde el Excel (usando el estado de la sesión)
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            # Filtramos solo la empresa que nos interesa para este módulo
            st.session_state.df_cable = df_full[df_full['Empresa'] == 'Cablemovil'].copy()
        except Exception as e:
            st.error(f"⚠️ No se pudo cargar 'empleados.xlsx'. Asegúrate de que el archivo existe. Error: {e}")
            return

    # 2. Definición de Turnos (Referencia visual)
    st.info("🕒 **Horarios Establecidos:** T1 (05:30-13:30) | T2 (13:30-21:30) | T3 (21:30-05:30)")

    # 3. Acciones de Grupos
    st.subheader("🛠️ Configuración de Grupos de Trabajo")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("🎲 Mezclar y Asignar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.success("Grupos generados exitosamente.")

    with col2:
        if st.button("🗑️ Limpiar Grupos"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"
            st.rerun()

    # 4. Visualización y Edición Manual
    st.write("### Distribución del Personal")
    
    # Configuramos el editor para que solo la columna 'Grupo' sea editable
    df_editado = st.data_editor(
        st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']],
        column_config={
            "Grupo": st.column_config.SelectboxColumn(
                "Asignación de Grupo",
                options=["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4", "Sin Asignar / Reserva"],
                required=True,
            ),
            "Cedula": st.column_config.Column(disabled=True),
            "Nombre": st.column_config.Column(disabled=True),
            "Cargo": st.column_config.Column(disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        key="editor_grupos"
    )

    # Actualizamos el estado de la sesión con cambios manuales si los hay
    if st.button("💾 Validar y Guardar Selección"):
        st.session_state.df_cable.update(df_editado)
        st.success("Cambios guardados en la memoria de la sesión.")

    # 5. Resumen de Validación Laboral
    st.divider()
    st.subheader("📊 Validación de Perfiles por Grupo")
    
    if 'Grupo' in st.session_state.df_cable.columns:
        resumen = []
        for g in sorted(st.session_state.df_cable['Grupo'].unique()):
            if "Sin Asignar" in g: continue
            
            data_g = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
            m = len(data_g[data_g['Cargo'].str.contains('Master', case=False, na=False)])
            a = len(data_g[data_g['Cargo'].str.contains('Tecnico A', case=False, na=False)])
            b = len(data_g[data_g['Cargo'].str.contains('Tecnico B', case=False, na=False)])
            
            resumen.append({
                "Grupo": g,
                "Total": len(data_g),
                "Masters (Req: 2)": m,
                "Tec A (Req: 7)": a,
                "Tec B (Req: 3)": b,
                "Estado": "✅ OK" if (m==2 and a==7 and b==3) else "⚠️ Incompleto"
            })
        
        if resumen:
            st.table(pd.DataFrame(resumen))
        else:
            st.write("No hay grupos asignados aún.")

    # 6. Programación Mensual (Visualización de Turnos)
    st.divider()
    st.subheader("🗓️ Asignación de Turnos Semanales")
    st.write("Define qué turno le corresponde a cada grupo en las semanas del mes:")
    
    semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
    grupos_activos = [g for g in st.session_state.df_cable['Grupo'].unique() if "Grupo" in g]
    
    if grupos_activos:
        # Crear una matriz de turnos para los grupos
        cols_sem = st.columns(len(semanas))
        for i, sem in enumerate(cols_sem):
            sem.write(f"**{semanas[i]}**")
            for grp in sorted(grupos_activos):
                st.selectbox(f"{grp} - {semanas[i]}", ["T1", "T2", "T3", "Descanso"], key=f"turno_{grp}_{i}")
    else:
        st.info("Asigna grupos primero para ver la programación de turnos.")
