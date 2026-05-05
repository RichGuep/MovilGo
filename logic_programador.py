import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO ---

def asignar_grupos_aleatorio(df_cable):
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
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Sincronización con Excepciones", content=output.getvalue(), sha=contents.sha, branch="main")
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
        except Exception as e: st.error(f"Error: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos Aleatorio"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Sincronizado!")
    with c3:
        if st.button("🗑️ Resetear Grupos"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()
    
    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados")

# --- 3. PROGRAMADOR CON PARAMETRIZADOR DE EXCEPCIONES ---

def pantalla_programador():
    st.title("📅 Programador 24/7 con Excepciones")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue los grupos primero."); return

    # --- NUEVA SECCIÓN: PARAMETRIZADOR DE DESCANSOS ESPECIALES ---
    with st.expander("🛠️ Parametrizador de Descansos Especiales (Novedades)"):
        st.write("Usa esta sección para forzar descansos a grupos específicos.")
        if 'excepciones' not in st.session_state:
            st.session_state.excepciones = []

        col_ex1, col_ex2, col_ex3 = st.columns(3)
        g_exc = col_ex1.selectbox("Grupo", ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"])
        f_exc_ini = col_ex2.date_input("Inicio Descanso", datetime.now())
        f_exc_fin = col_ex3.date_input("Fin Descanso", datetime.now())

        if st.button("➕ Añadir Regla de Descanso"):
            # Guardamos el rango de fechas en una lista
            rango = []
            curr_e = f_exc_ini
            while curr_e <= f_exc_fin:
                rango.append(curr_e.strftime('%Y-%m-%d'))
                curr_e += timedelta(days=1)
            st.session_state.excepciones.append({"grupo": g_exc, "fechas": rango})
            st.success(f"Regla añadida para {g_exc}")

        if st.session_state.excepciones:
            st.write("**Reglas activas:**")
            for i, exc in enumerate(st.session_state.excepciones):
                st.info(f"{exc['grupo']} descansa del {exc['fechas'][0]} al {exc['fechas'][-1]}")
            if st.button("🗑️ Limpiar todas las reglas"):
                st.session_state.excepciones = []
                st.rerun()

    # --- GENERACIÓN DE MATRIZ ---
    co_holidays = holidays.Colombia(years=[2024, 2025, 2026])
    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio Matriz", datetime.now())
    f_fin = c_f2.date_input("Fin Matriz", datetime.now() + timedelta(days=31))

    if st.button("🚀 Generar Matriz con Reglas"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        deudas = {g: 0 for g in grupos}
        historial = {g: "DESC" for g in grupos}

        for fecha in lista_fechas:
            dia = fecha.weekday()
            sem = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            f_str = fecha.strftime('%Y-%m-%d')
            col = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. ¿Quién libra hoy por REGLA MANUAL (EXCEPCIÓN)?
            libranza_manual = []
            for exc in st.session_state.excepciones:
                if f_str in exc['fechas']:
                    libranza_manual.append(exc['grupo'])

            # 2. ¿Quién libra hoy por ROTACIÓN AUTOMÁTICA?
            libranza_auto = None
            if dia == 5: # Sab
                libranza_auto = "Grupo 1" if sem % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem % 2 == 0 else "Grupo 1"] += 1
            elif dia == 6: # Dom
                libranza_auto = "Grupo 3" if sem % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem % 2 == 0 else "Grupo 3"] += 1
            else:
                # Compensatorios (Evitar saliendo de T3)
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    if deudas[g] > 0 and historial[g] != "T3" and g not in libranza_manual:
                        libranza_auto = g
                        deudas[g] -= 1
                        break

            # 3. Consolidar todos los que NO trabajan hoy
            todos_los_que_libran = set(libranza_manual)
            if libranza_auto: todos_los_que_libran.add(libranza_auto)

            # 4. Asignación de turnos a los activos
            activos = [g for g in grupos if g not in todos_los_que_libran]
            turnos_dia = {}
            
            for g in activos:
                idx_g = grupos.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem) % 3]
                if historial[g] == "T3" and t_base in ["T1", "T2"]: t_base = "T3" # Bienestar
                turnos_dia[g] = t_base

            # Ajuste de Cobertura (Garantizar T1, T2, T3)
            asignados = list(turnos_dia.values())
            # Regla: Máximo un T3
            while asignados.count("T3") > 1:
                for g in activos:
                    if turnos_dia[g] == "T3" and historial[g] != "T3":
                        turnos_dia[g] = "T1"
                        asignados = list(turnos_dia.values())
                        break
            
            # Garantizar cobertura mínima si hay suficientes activos
            if len(activos) >= 3:
                for tr in ["T1", "T2", "T3"]:
                    if tr not in asignados:
                        for g in activos:
                            if asignados.count(turnos_dia[g]) > 1:
                                if not (historial[g] == "T3" and tr == "T1"):
                                    turnos_dia[g] = tr
                                    asignados = list(turnos_dia.values())
                                    break

            for g in grupos:
                if g in todos_los_que_libran:
                    turno_f = "EXC" if g in libranza_manual else ("DESC" if dia >= 5 else "COMP")
                else:
                    turno_f = turnos_dia.get(g, "T1")
                
                resultados.append({"Grupo": g, "Fecha_Col": col, "Turno": turno_f, "Fecha_Raw": fecha})
                historial[g] = turno_f

        # --- Visualización y Validador ---
        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500", "EXC": "#9467bd"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz con Excepciones Aplicadas")
        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # Validador Richard
        st.divider()
        c_aud1, c_aud2 = st.columns(2)
        with c_aud1:
            st.write("**✅ Auditoría de Descansos Totales**")
            st.table(df_res[df_res['Turno'].isin(['DESC', 'COMP', 'EXC'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0))
        with c_aud2:
            st.write("**🛡️ Verificación de Cobertura Diaria**")
            errores = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: 
                        # Si hay muchos descansos manuales, avisar que no se pudo cubrir
                        errores.append(f"{fc} (Falta {t})")
            if not errores: st.success("¡Cobertura Total!")
            else: st.warning(f"Ojo: La cobertura se afectó por descansos manuales en: {', '.join(errores)}")
