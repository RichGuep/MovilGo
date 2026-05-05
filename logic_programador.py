import streamlit as st
import pandas as pd
import random
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO ---

def asignar_grupos_aleatorio(df_cable):
    """Mezcla y asigna personal respetando el mix contractual 2-7-3."""
    df = df_cable.copy()
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

    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes: s['Grupo'] = "Reserva"
    grupos_finales.extend(sobrantes)
    return pd.DataFrame(grupos_finales)

def guardar_en_github(df):
    """Sincroniza el Excel directamente con el repositorio de GitHub."""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token 'GITHUB_TOKEN' no encontrado en Secrets.")
            return False
        
        g = Github(st.secrets["GITHUB_TOKEN"])
        # IMPORTANTE: Reemplaza con tu usuario/repositorio real
        repo = g.get_repo("RichGuep/movilgo")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(
            path="empleados.xlsx", 
            message="Sincronización de grupos - MovilGo", 
            content=output.getvalue(), 
            sha=contents.sha, 
            branch="main"
        )
        return True
    except Exception as e:
        st.error(f"❌ Error GitHub: {e}")
        return False

# --- 2. MÓDULO: GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos - Cablemovil")
    st.info("Configura la estructura 2-7-3. Recuerda guardar en GitHub para que el programador lea los datos.")

    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            mapeo = {'Cedula': 'cedu', 'Nombre': 'nomb', 'Cargo': 'carg', 'Empresa': 'empr'}
            for oficial, clave in mapeo.items():
                col = [c for c in df_full.columns if clave in c.lower()]
                if col: df_full = df_full.rename(columns={col[0]: oficial})
            
            df_c = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            if 'Grupo' not in df_c.columns: df_c['Grupo'] = "Sin Asignar"
            st.session_state.df_cable = df_c
        except Exception as e:
            st.error(f"⚠️ Error cargando base de datos: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Sincronizado con éxito!")
    with c3:
        if st.button("🗑️ Resetear"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()

    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], 
                             use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados localmente")

# --- 3. MÓDULO: PROGRAMADOR 24/7 CON COMPENSATORIOS REALES ---

def pantalla_programador():
    st.title("📅 Programador Operativo 24/7")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Carga la base de datos en 'Gestión de Grupos'.")
        return

    co_holidays = holidays.Colombia(years=[datetime.now().year, datetime.now().year + 1])

    st.subheader("Parámetros del Periodo")
    col_f1, col_f2 = st.columns(2)
    f_inicio = col_f1.date_input("Fecha Inicio", datetime.now())
    f_fin = col_f2.date_input("Fecha Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Matriz de Programación"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos_lista = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        
        # Diccionario para rastrear quién trabajó su sábado y debe compensar el lunes
        debe_compensar = {g: False for g in grupos_lista}

        for fecha in lista_fechas:
            es_sab = (fecha.weekday() == 5)
            es_dom = (fecha.weekday() == 6)
            es_lun = (fecha.weekday() == 0)
            es_festivo = fecha in co_holidays
            sem_par = (fecha.isocalendar()[1] % 2 == 0)

            # LÓGICA DE DESCANSOS: Garantizar 3 grupos activos siempre
            grupo_que_libra_hoy = None
            
            if es_sab:
                # Intercalamos G1 y G2 (Descanso contractual Sábado)
                grupo_que_libra_hoy = "Grupo 1" if sem_par else "Grupo 2"
                # El que NO libra hoy, TRABAJA su descanso -> Se le anota COMP para el lunes
                quien_trabaja_hoy = "Grupo 2" if sem_par else "Grupo 1"
                debe_compensar[quien_trabaja_hoy] = True
            
            elif es_dom:
                # Intercalamos G3 y G4 (Descanso contractual Domingo)
                grupo_que_libra_hoy = "Grupo 3" if sem_par else "Grupo 4"
            
            elif es_lun:
                # El Lunes descansa el que trabajó el Sábado anterior (Compensatorio)
                for g in ["Grupo 1", "Grupo 2"]:
                    if debe_compensar[g]:
                        grupo_que_libra_hoy = g
                        debe_compensar[g] = False # Se salda la deuda
                        break

            # Preparar activos para repartir T1, T2, T3
            activos_del_dia = [g for g in grupos_lista if g != grupo_que_libra_hoy]
            
            # Nombre de la columna
            dia_str = fecha.strftime('%a').capitalize()
            col_name = f"{dia_str} {fecha.strftime('%d/%m')}"
            if es_festivo: col_name += " 🇨🇴"

            for g_name in grupos_lista:
                if g_name == grupo_que_libra_hoy:
                    turno = "COMP" if es_lun else "DESC"
                else:
                    # Repartición de turnos entre los 3 grupos activos
                    pos = activos_del_dia.index(g_name)
                    # Rotación semanal para que no repitan siempre el mismo horario
                    shift = fecha.isocalendar()[1] % 3
                    turno = ["T1", "T2", "T3"][(pos + shift) % 3]
                
                resultados.append({"Grupo": g_name, "Fecha_Col": col_name, "Turno": turno})

        # --- RENDERIZADO ---
        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        def style_c(val):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz Unificada de Cobertura")
        st.dataframe(matriz.style.map(style_c), use_container_width=True)
