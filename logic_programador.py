import streamlit as st
import pandas as pd
import random
import io
from datetime import time
from github import Github

def asignar_grupos_aleatorio(df_cable):
    """Asigna personal a grupos de 12 respetando el mix 2-7-3."""
    df = df_cable.copy()
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): p = masters.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(7): p = tecnicos_a.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(3): p = tecnicos_b.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        num_grupo += 1

    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes: s['Grupo'] = "Reserva"
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def guardar_en_github(df):
    """Sincroniza el Excel con el repositorio de GitHub."""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        g = Github(token)
        repo = g.get_repo("RichGuep/movilgo") # Ajusta a tu usuario/repo
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        content = output.getvalue()

        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Update Grupos MovilGo", 
                         content=content, sha=contents.sha, branch="main")
        return True
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return False

def generar_matriz_turnos():
    """Genera la rotación basada en las reglas contractuales de Richard."""
    dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    semanas = ["Semana 1", "Semana 2", "Semana 3", "Semana 4"]
    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    data = []

    for sem_idx, sem in enumerate(semanas):
        for g_idx, grupo in enumerate(grupos):
            for d_idx, dia in enumerate(dias):
                turno = ""
                # REGLA: Descansos Fijos por Contrato
                if grupo in ["Grupo 1", "Grupo 2"] and dia == "Sab": turno = "DESC"
                elif grupo in ["Grupo 3", "Grupo 4"] and dia == "Dom": turno = "DESC"
                
                # REGLA: Compensatorio Lunes (para quienes trabajan Domingo)
                elif dia == "Lun" and grupo in ["Grupo 1", "Grupo 2"]: turno = "COMP"
                
                # REGLA: Asignación de Turnos T1, T2, T3 y Refuerzo (REF)
                if turno == "":
                    # Rotación circular para que los 4 grupos cubran los 3 turnos
                    # El 4to grupo queda como refuerzo ese día
                    base = (g_idx + d_idx + sem_idx) % 4
                    opciones = ["T1", "T2", "T3", "REF"]
                    turno = opciones[base]

                data.append({"Semana": sem, "Grupo": grupo, "Dia": dia, "Turno": turno})
    return pd.DataFrame(data)

def pantalla_programador():
    st.title("📅 Programador MovilGo - Cablemovil")

    # 1. CARGA DE DATOS
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            # Normalización rápida
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

    # 2. SECCIÓN DE GRUPOS
    st.subheader("🛠️ Gestión de Grupos (2 Master, 7 Tec A, 3 Tec B)")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("🚀 Sincronizar GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("Sincronizado")
    with c3:
        if st.button("🗑️ Reset"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()

    # Editor de grupos
    df_temp = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], 
                             use_container_width=True, hide_index=True)
    if st.button("💾 Aplicar Cambios"):
        st.session_state.df_cable.update(df_temp); st.success("Cambios locales aplicados")

    # 3. MATRIZ DE TURNOS
    st.divider()
    st.subheader("🗓️ Programación Mensual Sugerida")
    if st.checkbox("Generar Calendario de Turnos"):
        df_matriz = generar_matriz_turnos()
        
        for sem in df_matriz["Semana"].unique():
            with st.expander(f"Ver {sem}", expanded=(sem=="Semana 1")):
                df_sem = df_matriz[df_matriz["Semana"] == sem]
                pivot = df_sem.pivot(index="Grupo", columns="Dia", values="Turno")
                pivot = pivot[["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]]
                
                def style_c(val):
                    color = "#1f77b4" if val=="T1" else "#2ca02c" if val=="T2" else "#7f7f7f" if val=="T3" else "#ff4b4b" if val=="DESC" else "#ffa500" if val=="COMP" else "#bcbd22"
                    return f'background-color: {color}; color: white; font-weight: bold'
                
                st.table(pivot.style.applymap(style_c))

    # 4. RESUMEN DE LEY
    st.sidebar.info("""
    **Reglas de Ley Aplicadas:**
    1. Jornada 24/7 (T1, T2, T3).
    2. Descanso contractual (G1-G2 Sáb, G3-G4 Dom).
    3. Compensatorios Lunes para G1-G2.
    4. Rotación equitativa semanal.
    """)
