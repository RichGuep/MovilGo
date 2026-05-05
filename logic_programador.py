import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA GITHUB ---

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
                # Recuperamos turno, noches y deudas pendientes
                estado[g] = {
                    "u": u['Turno'], 
                    "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                    "d": int(u.get('Deuda_Compensatorio', 0)) # Deudas de días trabajados
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
        repo.update_file("malla_historica.xlsx", "Malla con Compensatorios Obligatorios", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- 2. PROGRAMADOR CON COMPENSATORIOS SEMANALES ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Compensatorios Obligatorios")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre Anterior"):
        estado_base = obtener_ultimo_estado_github(repo)
        st.write(estado_base)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla con Compensatorios"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Inicialización de memoria desde GitHub
        memoria_t = {g: estado_base[g]["u"] for g in grupos_n}
        memoria_n = {g: estado_base[g]["n"] for g in grupos_n}
        deudas = {g: estado_base[g]["d"] for g in grupos_n}
        
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday() # 0=Lun, 5=Sáb, 6=Dom
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_h
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. LÓGICA DE LIBRANZAS Y COMPENSATORIOS
            libranza = None
            
            if dia_idx == 5: # Sábado: Libranza por ciclo, el otro grupo genera deuda
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Domingo: Libranza por ciclo, el otro grupo genera deuda
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Días de semana: PRIORIDAD MÁXIMA a pagar deudas de la semana pasada
                # Ordenamos por deuda (el que más debe descansa primero) y que NO venga de T3
                candidatos_descanso = sorted(grupos_n, key=lambda x: (deudas[x], memoria_n[x]), reverse=True)
                for g in candidatos_descanso:
                    if deudas[g] > 0 and memoria_t[g] != "T3":
                        libranza = g
                        deudas[g] -= 1
                        break

            # 2. ASIGNACIÓN DE TURNOS ACTIVOS
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # Protección T3 (Salud)
                if memoria_t[g] == "T3" and t_base in ["T1", "T2"]: t_base = "T3"
                # Límite noches (6 días)
                if memoria_n[g] >= 6 and t_base == "T3": t_base = "T1"
                
                turnos_hoy[g] = t_base

            # 3. MOTOR DE COBERTURA (Garantizar T1, T2, T3 sin duplicar Noche)
            # Asegurar T3 Único
            while list(turnos_hoy.values()).count("T3") > 1:
                for g_act in activos:
                    if turnos_hoy[g_act] == "T3" and memoria_t[g_act] != "T3":
                        turnos_hoy[g_act] = "T2"
                        break
            
            # Garantizar que nada falte
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    for gf in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if not (memoria_t[gf] == "T3" and tr == "T1"):
                                turnos_hoy[gf] = tr
                                break

            # 4. REGISTRO DIARIO
            for g in grupos_n:
                if g == libranza:
                    t_final = "DESC" if dia_idx >= 5 else "COMP"
                    n_acum = 0
                else:
                    t_final = turnos_hoy.get(g, "T1")
                    n_acum = memoria_n[g] + 1 if t_final == "T3" else 0
                
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_final, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_acum,
                    "Deuda_Compensatorio": deudas[g]
                })
                memoria_t[g] = t_final
                memoria_n[g] = n_acum

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    # --- VISUALIZACIÓN ---
    if st.session_state.malla_generada is not None:
        df_m = st.session_state.malla_generada
        matriz = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_m["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.subheader("🛡️ Reporte de Deudas Richard")
        ultimas_deudas = df_m.drop_duplicates('Grupo', keep='last')[['Grupo', 'Deuda_Compensatorio']]
        st.table(ultimas_deudas)
        
        alertas = []
        for g in grupos_n:
            if deudas[g] > 0: alertas.append(f"Pendiente compensatorio {g}")
        if not alertas: st.success("✅ Todas las deudas de descanso saldadas.")
        else: st.warning(f"⚠️ {', '.join(alertas)}")
