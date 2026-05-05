import streamlit as st
import pandas as pd
import random
import io
from datetime import time
from github import Github

def asignar_grupos_aleatorio(df_cable):
    """
    Lógica para armar grupos de 12 personas respetando:
    2 Master, 7 Tecnicos A, 3 Tecnicos B.
    """
    df = df_cable.copy()
    
    # Separación por perfiles (búsqueda flexible en la columna Cargo)
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1

    # Construcción de grupos exactos
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): 
            p = masters.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(7): 
            p = tecnicos_a.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(3): 
            p = tecnicos_b.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        num_grupo += 1

    # Manejo de personal restante
    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes:
        s['Grupo'] = "Reserva"
    
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def guardar_en_github(df):
    """
    Sincroniza el DataFrame directamente con el archivo empleados.xlsx en GitHub.
    """
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token de GitHub no configurado en Secrets.")
            return False
            
        token = st.secrets["GITHUB_TOKEN"]
        g = Github(token)
        
        # --- AJUSTA ESTO CON TUS DATOS ---
        repo_name = "TU_USUARIO/TU_REPOSITORIO" 
        repo = g.get_repo(repo_name)
        
        # Convertir a Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        content = output.getvalue()

        # Obtener SHA del archivo actual para actualizarlo
        contents = repo.get_contents("empleados.xlsx")
        
        repo.update_file(
            path="empleados.xlsx",
            message="Actualización automática de grupos - MovilGo",
            content=content,
            sha=contents.sha,
            branch="main"
        )
        return True
    except Exception as e:
        st.error(f"❌ Error de conexión con GitHub: {e}")
        return False

def pantalla_programador():
    st.title("📅 Programador MovilGo - Cablemovil")

    # 1. CARGA Y NORMALIZACIÓN (Blindaje contra KeyError)
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            
            # Normalizar nombres de columnas
            mapeo = {
                'Cedula': [c for c in df_full.columns if 'cedu' in c.lower() or 'id' in c.lower()],
                'Nombre': [c for c in df_full.columns if 'nomb' in c.lower()],
                'Cargo': [c for c in df_full.columns if 'carg' in c.lower()],
                'Empresa': [c for c in df_full.columns if 'empr' in c.lower()]
            }
            for oficial, encontrados in mapeo.items():
                if encontrados: df_full = df_full.rename(columns={encontrados[0]: oficial})
            
            # Filtro por empresa
            df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            if 'Grupo' not in df_cable.columns: df_cable['Grupo'] = "Sin Asignar"
            
            st.session_state.df_cable = df_cable
        except Exception as e:
            st.error(f"Error al cargar Excel: {e}")
            return

    # 2. ACCIONES RÁPIDAS
    st.info("🕒 T1: 05:30-13:30 | T2: 13:30-21:30 | T3: 21:30-05:30")
    
    col_acc1, col_acc2, col_acc3 = st.columns(3)
    with col_acc1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with col_acc2:
        if st.button("🗑️ Resetear Todo"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"
            st.rerun()
    with col_acc3:
        if st.button("🚀 Sincronizar con GitHub"):
            with st.spinner("Subiendo a la nube..."):
                if guardar_en_github(st.session_state.df_cable):
                    st.success("¡Archivo en GitHub actualizado!")

    # 3. EDITOR DE GRUPOS
    st.subheader("📋 Asignación Manual y Revisión")
    columnas_edit = ['Cedula', 'Nombre', 'Cargo', 'Grupo']
    cols_existentes = [c for c in columnas_edit if c in st.session_state.df_cable.columns]

    df_temp = st.data_editor(
        st.session_state.df_cable[cols_existentes],
        column_config={
            "Grupo": st.column_config.SelectboxColumn(
                "Grupo",
                options=["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4", "Reserva", "Sin Asignar"],
                required=True
            ),
            "Cedula": st.column_config.Column(disabled=True),
            "Nombre": st.column_config.Column(disabled=True),
            "Cargo": st.column_config.Column(disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        key="editor_grupos_final"
    )

    # Botón para confirmar cambios manuales del editor
    if st.button("💾 Aplicar Cambios Manuales"):
        for idx in df_temp.index:
            st.session_state.df_cable.at[idx, 'Grupo'] = df_temp.at[idx, 'Grupo']
        st.success("Cambios aplicados localmente.")

    # 4. CUADRO DE VALIDACIÓN LABORAL
    st.divider()
    st.subheader("📊 Resumen de Cumplimiento (Mix 2-7-3)")
    
    df_v = st.session_state.df_cable
    resumen = []
    lista_g = [g for g in df_v['Grupo'].unique() if "Grupo" in str(g)]
    
    for g in sorted(lista_g):
        subset = df_v[df_v['Grupo'] == g]
        m = len(subset[subset['Cargo'].str.contains('Master', case=False, na=False)])
        a = len(subset[subset['Cargo'].str.contains('Tecnico A', case=False, na=False)])
        b = len(subset[subset['Cargo'].str.contains('Tecnico B', case=False, na=False)])
        
        resumen.append({
            "Grupo": g,
            "Total": len(subset),
            "Masters(2)": m,
            "Tec A(7)": a,
            "Tec B(3)": b,
            "Cumple": "✅ SI" if (m==2 and a==7 and b==3) else "❌ NO"
        })
    
    if resumen:
        st.table(pd.DataFrame(resumen))
    else:
        st.write("No hay grupos configurados aún.")
