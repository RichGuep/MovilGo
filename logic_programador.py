import streamlit as st
import pandas as pd
import random
from datetime import time

def asignar_grupos_aleatorio(df_cable):
    """
    Mezcla y asigna grupos de 12 (2 Master, 7 Tec A, 3 Tec B).
    """
    df = df_cable.copy()
    
    # Separar por categorías con búsqueda flexible
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')

    grupos_finales = []
    num_grupo = 1

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
    for s in sobrantes:
        s['Grupo'] = "Reserva"
    
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def pantalla_programador():
    st.title("📅 Programador MovilGo - Cablemovil")

    # 1. CARGA Y NORMALIZACIÓN DE DATOS
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            
            mapeo = {
                'Cedula': [c for c in df_full.columns if 'cedu' in c.lower() or 'id' in c.lower()],
                'Nombre': [c for c in df_full.columns if 'nomb' in c.lower()],
                'Cargo': [c for c in df_full.columns if 'carg' in c.lower()],
                'Empresa': [c for c in df_full.columns if 'empr' in c.lower()]
            }
            
            for oficial, encontrados in mapeo.items():
                if encontrados:
                    df_full = df_full.rename(columns={encontrados[0]: oficial})
            
            # Filtro por Cablemovil
            df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            
            # Inicializar columna Grupo si no existe
            if 'Grupo' not in df_cable.columns:
                df_cable['Grupo'] = "Sin Asignar"
            
            st.session_state.df_cable = df_cable

        except Exception as e:
            st.error(f"⚠️ Error al cargar Excel: {e}")
            return

    # 2. ACCIONES
    st.info("🕒 T1: 05:30-13:30 | T2: 13:30-21:30 | T3: 21:30-05:30")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("🗑️ Resetear"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"
            st.rerun()

    # 3. EDITOR DE TABLA
    # Aseguramos que 'Grupo' esté presente antes de editar
    if 'Grupo' not in st.session_state.df_cable.columns:
        st.session_state.df_cable['Grupo'] = "Sin Asignar"

    columnas_edit = ['Cedula', 'Nombre', 'Cargo', 'Grupo']
    # Filtrar solo las que existen para evitar error visual
    cols_validas = [c for c in columnas_edit if c in st.session_state.df_cable.columns]

    df_editado = st.data_editor(
        st.session_state.df_cable[cols_validas],
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
        key="editor_grupos_cable"
    )

    if st.button("💾 Guardar Cambios"):
        # Sincronizar el editor con el estado global
        for idx in df_editado.index:
            st.session_state.df_cable.at[idx, 'Grupo'] = df_editado.at[idx, 'Grupo']
        st.success("Cambios sincronizados.")
        st.rerun()

    # 4. RESUMEN DE VALIDACIÓN (Aquí fallaba antes)
    st.divider()
    st.subheader("📊 Validación de Grupos")
    
    df_actual = st.session_state.df_cable.copy()
    
    # RE-VERIFICACIÓN CRÍTICA DE COLUMNA GRUPO
    if 'Grupo' not in df_actual.columns:
        st.warning("Configura los grupos primero.")
    else:
        resumen = []
        # Obtenemos los grupos únicos ignorando vacíos
        lista_grupos = [g for g in df_actual['Grupo'].unique() if "Grupo" in str(g)]
        
        for g in sorted(lista_grupos):
            subset = df_actual[df_actual['Grupo'] == g]
            m = len(subset[subset['Cargo'].str.contains('Master', case=False, na=False)])
            a = len(subset[subset['Cargo'].str.contains('Tecnico A', case=False, na=False)])
            b = len(subset[subset['Cargo'].str.contains('Tecnico B', case=False, na=False)])
            
            resumen.append({
                "Grupo": g,
                "Total": len(subset),
                "Masters(2)": m,
                "Tec A(7)": a,
                "Tec B(3)": b,
                "Estado": "✅" if (m==2 and a==7 and b==3) else "❌"
            })
        
        if resumen:
            st.table(pd.DataFrame(resumen))
        else:
            st.write("Haz clic en 'Mezclar Grupos' para comenzar.")
