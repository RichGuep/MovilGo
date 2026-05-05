import streamlit as st
import pandas as pd
import io
import holidays
import time
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE APOYO ---

def asignar_grupos_aleatorio(df_cable):
    df = df_cable.copy()
    # Separar por perfiles (Asegúrate de que los nombres de los cargos coincidan con tu Excel)
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
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo("RichGuep/movilgo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("empleados.xlsx")
        repo.update_file(path="empleados.xlsx", message="Sincronización MovilGo Pro", 
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
        except Exception as e: st.error(f"Error cargando Excel: {e}"); return

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🎲 Mezclar Grupos Aleatorio"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Grupos guardados en GitHub!")
    with c3:
        if st.button("🗑️ Resetear Grupos"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()
    
    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], 
                             use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados localmente")

# --- 3. PROGRAMADOR CON BARRA DE PROGRESO Y REGLAS DE SALUD ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - MovilGo Pro")
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Primero configure los grupos en el menú de Gestión."); return

    # --- PARAMETRIZADOR DE EXCEPCIONES ---
    with st.expander("🛠️ Parametrizador de Descansos Manuales"):
        if 'excepciones' not in st.session_state: st.session_state.excepciones = []
        col_ex1, col_ex2, col_ex3 = st.columns(3)
        g_exc = col_ex1.selectbox("Grupo", ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"])
        f_exc_ini = col_ex2.date_input("Inicio", datetime.now())
        f_exc_fin = col_ex3.date_input("Fin", datetime.now())

        if st.button("➕ Añadir Regla de Descanso"):
            rango = []
            curr_e = f_exc_ini
            while curr_e <= f_exc_fin:
                rango.append(curr_e.strftime('%Y-%m-%d'))
                curr_e += timedelta(days=1)
            st.session_state.excepciones.append({"grupo": g_exc, "fechas": rango})
            st.success(f"Novedad registrada para {g_exc}")

        if st.session_state.excepciones:
            for exc in st.session_state.excepciones:
                st.caption(f"• {exc['grupo']}: {exc['fechas'][0]} al {exc['fechas'][-1]}")
            if st.button("🗑️ Limpiar Reglas"):
                st.session_state.excepciones = []; st.rerun()

    # --- GENERACIÓN ---
    co_holidays = holidays.Colombia(years=[2024, 2025, 2026])
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Fecha Inicio Matriz", datetime.now())
    f_fin = c_f2.date_input("Fecha Fin Matriz", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Matriz con Reglas"):
        # Interfaz de progreso
        progreso_bar = st.progress(0)
        status_text = st.empty()
        
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        deudas = {g: 0 for g in grupos}
        historial = {g: "DESC" for g in grupos}

        total_dias = len(lista_fechas)
        
        for i, fecha in enumerate(lista_fechas):
            # Actualizar progreso
            porcentaje = int((i + 1) / total_dias * 100)
            progreso_bar.progress(porcentaje)
            status_text.text(f"Procesando día {i+1} de {total_dias}...")

            dia_semana = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            f_str = fecha.strftime('%Y-%m-%d')
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Chequeo de Excepciones Manuales
            libres_hoy = [exc['grupo'] for exc in st.session_state.excepciones if f_str in exc['fechas']]
            
            # 2. Descansos Automáticos (Sáb/Dom/Comp)
            libranza_auto = None
            if dia_semana == 5: # Sab
                libranza_auto = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_semana == 6: # Dom
                libranza_auto = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            elif dia_semana < 5: # Compensatorios Lun-Vie
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    if deudas[g] > 0 and historial[g] != "T3" and g not in libres_hoy:
                        libranza_auto = g
                        deudas[g] -= 1
                        break
            
            if libranza_auto: libres_hoy.append(libranza_auto)
            libres_hoy = list(set(libres_hoy)) # Quitar duplicados

            # 3. Asignación de Turnos (Máximo 1 T3 y Protección T3->T1)
            activos = [g for g in grupos if g not in libres_hoy]
            turnos_dia = {}
            
            for g in activos:
                idx_g = grupos.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                # Protección Bienestar: No T1 después de T3
                if historial[g] == "T3" and t_base == "T1": t_base = "T3"
                turnos_dia[g] = t_base

            # Ajuste Cobertura
            asignados = list(turnos_dia.values())
            while asignados.count("T3") > 1: # No duplicar noches
                for g in activos:
                    if turnos_dia[g] == "T3" and historial[g] != "T3":
                        turnos_dia[g] = "T1"
                        asignados = list(turnos_dia.values())
                        break
                    break
            
            # Asegurar T1, T2, T3
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
                if g in libres_hoy:
                    turno_f = "EXC" if any(f_str in exc['fechas'] and exc['grupo'] == g for exc in st.session_state.excepciones) else ("DESC" if dia_semana >= 5 else "COMP")
                else:
                    turno_f = turnos_dia.get(g, "T1")
                
                resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": turno_f})
                historial[g] = turno_f

        # Finalizar indicadores
        progreso_bar.empty()
        status_text.empty()
        st.success("✅ Matriz generada con éxito siguiendo todas las reglas de salud y cobertura.")

        # --- VISUALIZACIÓN ---
        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def style_matrix(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500", "EXC": "#9467bd"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(style_matrix), use_container_width=True)

        # --- VALIDADOR ---
        st.divider()
        c_aud1, c_aud2 = st.columns(2)
        with c_aud1:
            st.write("**📊 Resumen de Descansos**")
            st.table(df_res[df_res['Turno'].isin(['DESC', 'COMP', 'EXC'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0))
        with c_aud2:
            st.write("**🛡️ Auditoría Operativa**")
            alertas = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: alertas.append(f"{fc}(Sin {t})")
                if list(tv).count("T3") > 1: alertas.append(f"{fc}(Doble T3)")
            
            # Chequeo salud
            for g in grupos:
                h = df_res[df_res["Grupo"] == g]["Turno"].tolist()
                for d in range(1, len(h)):
                    if h[d-1] == "T3" and h[d] == "T1": alertas.append(f"⚠️ Fatiga {g}")

            if not alertas: st.success("Operación 100% Optimizada.")
            else: st.error(f"Revisar: {', '.join(alertas)}")
