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
    """Sincroniza el Excel con el repositorio de GitHub."""
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token 'GITHUB_TOKEN' no encontrado.")
            return False
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Actualización Grupos", 
                         content=output.getvalue(), sha=contents.sha, branch="main")
        return True
    except Exception as e:
        st.error(f"❌ Error GitHub: {e}"); return False

# --- 2. MÓDULO: GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos - Cablemovil")
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
            st.error(f"Error: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Guardado!")
    with c3:
        if st.button("🗑️ Reset"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()

    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados")

# --- 3. MÓDULO: PROGRAMADOR CON COMPENSATORIO FLEXIBLE ---

def pantalla_programador():
    st.title("📅 Programador Operativo 24/7")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Configure los grupos primero."); return

    co_holidays = holidays.Colombia(years=[datetime.now().year, datetime.now().year + 1])

    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Matriz Operativa"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos_lista = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        
        # RASTREO DE DEUDAS DE COMPENSATORIO
        # Guardamos cuántos días le debemos a cada grupo
        dias_pendientes = {g: 0 for g in grupos_lista}

        for fecha in lista_fechas:
            dia_idx = fecha.weekday() # 0=Lun, 5=Sab, 6=Dom
            es_fin_semana = dia_idx >= 5
            es_festivo = fecha in co_holidays
            sem_par = (fecha.isocalendar()[1] % 2 == 0)

            grupo_que_libra_hoy = None

            # --- A. ASIGNACIÓN DE DESCANSOS CONTRACTUALES ---
            if dia_idx == 5: # Sábado
                grupo_que_libra_hoy = "Grupo 1" if sem_par else "Grupo 2"
                quien_trabaja = "Grupo 2" if sem_par else "Grupo 1"
                dias_pendientes[quien_trabaja] += 1 # Gana un COMP
            
            elif dia_idx == 6: # Domingo
                grupo_que_libra_hoy = "Grupo 3" if sem_par else "Grupo 4"
                quien_trabaja = "Grupo 4" if sem_par else "Grupo 3"
                dias_pendientes[quien_trabaja] += 1 # Gana un COMP

            # --- B. ASIGNACIÓN DE COMPENSATORIOS FLEXIBLES (Lunes a Viernes) ---
            else:
                # Buscamos quién tiene deudas pendientes (Prioridad al que más se le debe)
                # Solo permitimos que descanse 1 grupo por día para no dejar huecos
                for g in sorted(dias_pendientes, key=dias_pendientes.get, reverse=True):
                    if dias_pendientes[g] > 0:
                        grupo_que_libra_hoy = g
                        dias_pendientes[g] -= 1 # Se salda 1 día
                        break

            # --- C. REPARTICIÓN DE TURNOS ---
            activos = [g for g in grupos_lista if g != grupo_que_libra_hoy]
            col_name = f"{fecha.strftime('%a').capitalize()} {fecha.strftime('%d/%m')}"
            if es_festivo: col_name += " 🇨🇴"

            for g_name in grupos_lista:
                if g_name == grupo_que_libra_hoy:
                    turno = "DESC" if es_fin_semana else "COMP"
                else:
                    pos = activos.index(g_name)
                    shift = (fecha.day + fecha.month) % 3 # Rotación más variada
                    turno = ["T1", "T2", "T3"][(pos + shift) % 3]
                
                resultados.append({"Grupo": g_name, "Fecha_Col": col_name, "Turno": turno})

        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        def style_c(val):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz de Cobertura Flexible 24/7")
        st.dataframe(matriz.style.map(style_c), use_container_width=True)
        st.info("💡 Nota: Los compensatorios (COMP) se asignan automáticamente de Lunes a Viernes al primer grupo disponible con días pendientes.")
