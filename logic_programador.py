import streamlit as st
import pandas as pd
import random
import io
from datetime import datetime, timedelta
from github import Github

# --- FUNCIONES DE APOYO (Lógica Pura) ---

def asignar_grupos_aleatorio(df_cable):
    """Mezcla y asigna personal respetando el mix 2-7-3."""
    df = df_cable.copy()
    # Separar por perfiles
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1
    # Armar grupos de 12
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): 
            p = masters.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(7): 
            p = tecnicos_a.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(3): 
            p = tecnicos_b.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        num_grupo += 1

    # Sobrantes
    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes: s['Grupo'] = "Reserva"
    
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def guardar_en_github(df):
    """Sincroniza con GitHub usando Secrets."""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("Falta GITHUB_TOKEN en los Secrets de Streamlit.")
            return False
        
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo") # REVISA QUE SEA TU REPO
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Update Grupos MovilGo", 
                         content=output.getvalue(), sha=contents.sha, branch="main")
        return True
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return False

# --- MÓDULO: GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos - Cablemovil")
    
    # Carga inicial
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            # Normalización de columnas
            mapeo = {
                'Cedula': [c for c in df_full.columns if 'cedu' in c.lower()],
                'Nombre': [c for c in df_full.columns if 'nomb' in c.lower()],
                'Cargo': [c for c in df_full.columns if 'carg' in c.lower()],
                'Empresa': [c for c in df_full.columns if 'empr' in c.lower()]
            }
            for oficial, encontrados in mapeo.items():
                if encontrados: df_full = df_full.rename(columns={encontrados[0]: oficial})
            
            df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            if 'Grupo' not in df_cable.columns: df_cable['Grupo'] = "Sin Asignar"
            st.session_state.df_cable = df_cable
        except Exception as e:
            st.error(f"Error cargando base de datos: {e}")
            return

    # Botones de acción
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with col2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable):
                st.success("Grupos guardados en GitHub.")
    with col3:
        if st.button("🗑️ Resetear"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"
            st.rerun()

    # Editor de tabla
    df_temp = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], 
                             use_container_width=True, hide_index=True)
    
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_temp)
        st.success("Cambios aplicados localmente.")

# --- MÓDULO: PROGRAMADOR ---

def pantalla_programador():
    st.title("📅 Programador de Turnos")
    
    if 'df_cable' not in st.session_state or st.session_state.df_cable['Grupo'].unique().tolist() == ['Sin Asignar']:
        st.warning("⚠️ Primero configura los grupos en el menú 'Gestión de Grupos'.")
        return

    st.subheader("Rango de Fechas")
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        f_inicio = st.date_input("Inicio", datetime.now())
    with c_f2:
        f_fin = st.date_input("Fin", datetime.now() + timedelta(days=7))

    if st.button("🚀 Generar Calendario Operativo"):
        # Lógica de matriz de turnos
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr)
            curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        
        for fecha in lista_fechas:
            es_sab = (fecha.weekday() == 5)
            es_dom = (fecha.weekday() == 6)
            es_lun = (fecha.weekday() == 0)
            sem_anio = fecha.isocalendar()[1]

            for g_idx, g_name in enumerate(grupos):
                turno = ""
                # Reglas contractuales de Richard
                if g_name in ["Grupo 1", "Grupo 2"] and es_sab: turno = "DESC"
                elif g_name in ["Grupo 3", "Grupo 4"] and es_dom: turno = "DESC"
                elif es_lun and g_name in ["Grupo 1", "Grupo 2"]: turno = "COMP"
                
                if turno == "":
                    # Rotación dinámica
                    idx_t = (g_idx + sem_anio) % 4
                    opciones = ["T1", "T2", "T3", "REF"]
                    turno = opciones[idx_t]
                
                resultados.append({"Fecha": fecha.strftime('%d/%m'), "Día": fecha.strftime('%a'), "Grupo": g_name, "Turno": turno})

        df_res = pd.DataFrame(resultados)
        pivot = df_res.pivot(index="Grupo", columns="Fecha", values="Turno")
        
        def style_c(val):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500", "REF": "#bcbd22"}
            return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold;'
        
        st.dataframe(pivot.style.map(style_c), use_container_width=True)
