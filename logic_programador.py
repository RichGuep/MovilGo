import streamlit as st
import pandas as pd
import random
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO (MIX 2-7-3 Y GITHUB) ---

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
        repo.update_file(path="empleados.xlsx", message="Sincronización Final con Validador", content=output.getvalue(), sha=contents.sha, branch="main")
        return True
    except Exception as e:
        st.error(f"❌ Error GitHub: {e}"); return False

# --- 2. MÓDULOS DE PANTALLA ---

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

# --- 3. PROGRAMADOR CON VALIDADOR DE CUMPLIMIENTO ---

def pantalla_programador():
    st.title("📅 Programador 24/7 con Validador")
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue los grupos primero."); return

    co_holidays = holidays.Colombia(years=[2024, 2025, 2026])
    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=31))

    if st.button("🚀 Generar, Validar y Auditar"):
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
            col = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            libranza = None
            # Descansos Contractuales
            if dia == 5:
                libranza = "Grupo 1" if sem % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem % 2 == 0 else "Grupo 1"] += 1
            elif dia == 6:
                libranza = "Grupo 3" if sem % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem % 2 == 0 else "Grupo 3"] += 1
            else:
                # Compensatorios (Evitar dar COMP justo saliendo de T3)
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    if deudas[g] > 0 and historial[g] != "T3":
                        libranza = g
                        deudas[g] -= 1
                        break

            activos = [g for g in grupos if g != libranza]
            turnos_dia = {}
            for g in activos:
                idx_g = grupos.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem) % 3]
                # BLINDAJE DE SUEÑO T3 -> T1/T2
                if historial[g] == "T3" and t_base in ["T1", "T2"]:
                    t_base = "T3"
                turnos_dia[g] = t_base

            # AJUSTE COBERTURA (Solo un T3 y garantizar T1, T2)
            asignados = list(turnos_dia.values())
            while asignados.count("T3") > 1:
                for g in activos:
                    if turnos_dia[g] == "T3" and historial[g] != "T3":
                        turnos_dia[g] = "T1"
                        asignados = list(turnos_dia.values())
                        break
            
            for tr in ["T1", "T2", "T3"]:
                if tr not in asignados:
                    for g in activos:
                        if asignados.count(turnos_dia[g]) > 1:
                            if not (historial[g] == "T3" and tr == "T1"):
                                turnos_dia[g] = tr
                                asignados = list(turnos_dia.values())
                                break

            for g in grupos:
                turno_f = ("DESC" if dia >= 5 else "COMP") if g == libranza else turnos_dia.get(g, "T1")
                resultados.append({"Grupo": g, "Fecha_Col": col, "Turno": turno_f, "Fecha_Raw": fecha})
                historial[g] = turno_f

        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz de Programación")
        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # --- SECCIÓN DEL VALIDADOR ---
        st.divider()
        st.subheader("🔍 Validador de Cumplimiento Richard")
        
        col_aud1, col_aud2 = st.columns(2)

        with col_aud1:
            st.write("**✅ Auditoría de Descansos**")
            conteo = df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
            st.table(conteo)
            if any(v > 0 for v in deudas.values()):
                for g, d in deudas.items():
                    if d > 0: st.warning(f"Aún le debes {d} día(s) al {g}")

        with col_aud2:
            st.write("**🛡️ Verificación de Cobertura y Salud**")
            errores = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: errores.append(f"{fc} (Falta {t})")
                if list(tv).count("T3") > 1: errores.append(f"{fc} (Doble T3 ⚠️)")
            
            # Chequeo T3 -> T1
            violacion_sueno = False
            for g in grupos:
                h = df_res[df_res["Grupo"] == g]["Turno"].tolist()
                for i in range(1, len(h)):
                    if h[i-1] == "T3" and h[i] == "T1": 
                        errores.append(f"⚠️ {g} (T3 a T1)")
                        violacion_sueno = True

            if not errores:
                st.success("¡Cobertura Óptima y Bienestar Garantizado!")
            else:
                st.error(f"Se detectaron novedades: {', '.join(errores)}")
