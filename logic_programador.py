import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA Y MEMORIA GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
            if not regs.empty:
                u = regs.iloc[-1]
                estado[g] = {
                    "u": u['Turno'], 
                    "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                    "d": int(u.get('Deuda_Compensatorio', 0))
                }
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def guardar_malla_en_historico(df_nueva):
    repo = conectar_github()
    if not repo: return
    try:
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Malla Rotacion Ascendente", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. MOTOR DE VALIDACIÓN DE ROTACIÓN ASCENDENTE ---

def es_cambio_saludable(turno_ayer, turno_hoy):
    """
    Define si el cambio de turno respeta la rotación ascendente (retraso de fase).
    T1 (Mañana) -> T2 (Tarde) -> T3 (Noche) -> DESC/COMP
    Cualquier salto hacia atrás (T3 a T1, T2 a T1, T3 a T2) es FALSO.
    """
    if turno_ayer in ["DESC", "COMP"]: return True # Tras descanso se puede reiniciar ciclo
    if turno_hoy in ["DESC", "COMP"]: return True  # Ir a descanso siempre es saludable
    
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    
    # Solo permitir si el valor de hoy es mayor o igual al de ayer (Ascendente)
    if jerarquia[turno_hoy] >= jerarquia[turno_ayer]:
        return True
    return False

# --- 3. PROGRAMADOR PROFESIONAL ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Rotación Ascendente (Salud)")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre Anterior"):
        estado_base = obtener_ultimo_estado_github(repo)
        st.write(estado_base)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin (Hasta 6 meses)", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla Saludable"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado_base[g]["u"] for g in grupos_n}
        mem_n = {g: estado_base[g]["n"] for g in grupos_n}
        deudas = {g: estado_base[g]["d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_fest = fecha in co_h
            col_name = f"{fecha.strftime('%a %d/%m')}"

            # 1. Gestión de Descansos (Prioridad para reiniciar ciclo)
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Pagar deudas obligatoriamente para resetear rotación si es necesario
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación de Turnos con Filtro Ascendente
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                # Sugerencia por rotación matemática
                t_sugerido = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # VALIDACIÓN DE SALUD: Si el cambio es descendente, forzamos inercia
                if not es_cambio_saludable(mem_t[g], t_sugerido):
                    t_sugerido = mem_t[g] # Mantiene el turno actual hasta que llegue un descanso
                
                # Control extra: No más de 6 noches
                if mem_n[g] >= 6 and t_sugerido == "T3":
                    t_sugerido = "T1" # Esto generará una alerta en el validador para que Richard lo vea
                
                turnos_hoy[g] = t_sugerido

            # 3. Motor de Cobertura y Unicidad de T3
            # Garantizar T1, T2, T3
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    for gf in sorted(activos, key=lambda x: mem_n[x]):
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            # Solo permite el cambio si es ascendente
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break

            # Forzar T2 si hay sobras (Regla Richard) y eliminar Doble T3
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                for g_n in activos:
                    if turnos_hoy[g_n] == "T3" and mem_t[g_n] != "T3":
                        turnos_hoy[g_n] = "T2"
                        actuales = list(turnos_hoy.values())
                        break

            # 4. Registro
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.divider()
        st.subheader("🔍 Validador Richard: Salud y Proyección")
        c1, c2 = st.columns(2)
        with c2:
            alertas = []
            for g in grupos_n:
                h = df_res[df_res["Grupo"] == g].to_dict('records')
                for i in range(1, len(h)):
                    # Validador Estricto de Richard
                    if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                        alertas.append(f"⚠️ {g}: Salto {h[i-1]['Turno']} -> {h[i]['Turno']} el {h[i]['Fecha_Col']}")
            
            if not alertas: st.success("¡Rotación Ascendente Perfecta! El personal dormirá mejor.")
            else: st.error(f"Se detectaron rotaciones descendentes: {', '.join(set(alertas[:5]))}")
