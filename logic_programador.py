import streamlit as st
import pandas as pd
import random
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
        repo.update_file(path="empleados.xlsx", message="Sincronización Salud", content=output.getvalue(), sha=contents.sha, branch="main")
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
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar en GitHub"):
            if guardar_en_github(st.session_state.df_cable): st.success("¡Sincronizado!")
    with c3:
        if st.button("🗑️ Reset"):
            st.session_state.df_cable['Grupo'] = "Sin Asignar"; st.rerun()

    df_edit = st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)
    if st.button("Aplicar Cambios Manuales"):
        st.session_state.df_cable.update(df_edit); st.success("Cambios aplicados")

# --- 3. MÓDULO: PROGRAMADOR CON BLOQUEO DE T3-T1 ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Protección de Sueño")
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue los grupos primero."); return

    co_holidays = holidays.Colombia(years=[datetime.now().year, datetime.now().year + 1])
    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=31))

    if st.button("🚀 Generar Matriz Protegida"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos_lista = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        dias_pendientes = {g: 0 for g in grupos_lista}
        ultimo_turno = {g: "DESC" for g in grupos_lista}

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            num_semana = fecha.isocalendar()[1]
            sem_par = (num_semana % 2 == 0)
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Definir descansos/compensatorios
            grupo_que_libra_hoy = None
            if dia_idx == 5: # Sab
                grupo_que_libra_hoy = "Grupo 1" if sem_par else "Grupo 2"
                dias_pendientes["Grupo 2" if sem_par else "Grupo 1"] += 1
            elif dia_idx == 6: # Dom
                grupo_que_libra_hoy = "Grupo 3" if sem_par else "Grupo 4"
                dias_pendientes["Grupo 4" if sem_par else "Grupo 3"] += 1
            elif dia_idx < 5:
                # Prioridad compensar al que salió de T3 para que descanse
                for g in sorted(dias_pendientes, key=dias_pendientes.get, reverse=True):
                    if dias_pendientes[g] > 0:
                        # LE DAMOS EL COMP JUSTO AL SALIR DE T3 (Ideal para resetear sueño)
                        grupo_que_libra_hoy = g
                        dias_pendientes[g] -= 1
                        break

            # 2. Asignación de Turnos con REGLA DE ORO: NO T3 -> T1
            turnos_dia = {}
            grupos_activos = [g for g in grupos_lista if g != grupo_que_libra_hoy]
            
            for g_name in grupos_activos:
                idx_grupo = grupos_lista.index(g_name)
                idx_turno = (idx_grupo + num_semana) % 3
                turno_sug = ["T1", "T2", "T3"][idx_turno]

                # BLOQUEO INNEGOCIABLE: Si ayer hizo T3, hoy NO puede hacer T1 ni T2
                if ultimo_turno[g_name] == "T3" and turno_sug in ["T1", "T2"]:
                    # Forzamos que se quede en T3 o que el sistema busque otra opción
                    # Pero para garantizar descanso, el validador buscará que otro cubra el día
                    turno_sug = "T3" 
                
                turnos_dia[g_name] = turno_sug

            # 3. Cobertura Dinámica (Solo un T3 y garantizar T1, T2)
            final_turnos = list(turnos_dia.values())
            # Si hay Doble T3 por protección de sueño, intentamos mover uno a T2 solo si es seguro
            while final_turnos.count("T3") > 1:
                for g_act in grupos_activos:
                    if turnos_dia[g_act] == "T3" and ultimo_turno[g_act] != "T3":
                        turnos_dia[g_act] = "T2" # Lo movemos a tarde para dar más margen
                        final_turnos = list(turnos_dia.values())
                        break
                    break # Si todos vienen de T3, se quedan así (emergencia de salud)

            # Garantizar T1, T2, T3 una vez
            for t_req in ["T1", "T2", "T3"]:
                if t_req not in final_turnos:
                    for g_act in grupos_activos:
                        if final_turnos.count(turnos_dia[g_act]) > 1:
                            # Validar que el cambio sea humano
                            if not (ultimo_turno[g_act] == "T3" and t_req == "T1"):
                                turnos_dia[g_act] = t_req
                                final_turnos = list(turnos_dia.values())
                                break

            # 4. Registro Final
            for g_name in grupos_lista:
                if g_name == grupo_que_libra_hoy:
                    t_f = "DESC" if dia_idx >= 5 else "COMP"
                else:
                    t_f = turnos_dia.get(g_name, "T1")
                
                resultados.append({"Grupo": g_name, "Fecha_Col": col_name, "Turno": t_f})
                ultimo_turno[g_name] = t_f

        # --- VISUALIZACIÓN ---
        df_res = pd.DataFrame(resultados)
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        def style_c(val):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.subheader("📊 Matriz con Blindaje T3-T1")
        st.dataframe(matriz.style.map(style_c), use_container_width=True)

        # Auditoría
        st.divider()
        c_aud1, c_aud2 = st.columns(2)
        with c_aud2:
            st.write("**🛡️ Auditoría de Cobertura y Salud**")
            alertas = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: alertas.append(f"{fc} (Falta {t})")
            
            # Chequeo de salud T3 -> T1
            for g in grupos_lista:
                h_grupo = df_res[df_res["Grupo"] == g]["Turno"].tolist()
                for d in range(1, len(h_grupo)):
                    if h_grupo[d-1] == "T3" and h_grupo[d] == "T1":
                        alertas.append(f"⚠️ Violación de Sueño en {g}")

            if not alertas: st.success("¡Programación 100% Segura y Cubierta!")
            else: st.error(f"Revisar: {', '.join(alertas)}")
