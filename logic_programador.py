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
        repo.update_file("malla_historica.xlsx", "Malla Blindaje Legal", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado con éxito.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 3. PROGRAMADOR CON BLINDAJE LEGAL ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Blindaje Legal Semanal")
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
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla Legal Richard"):
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
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # 1. IDENTIFICAR QUIÉN DEBE LIBRAR HOY (Leyes de Richard)
            libranza = None
            
            # Sábado y Domingo son descansos de ley por ciclo
            if dia_idx == 5: # Sábado
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Domingo
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # DÍAS DE SEMANA: Obligatorio pagar compensatorios pendientes
                # Buscamos quién tiene deuda y NO está en T3 (para respetar el sueño post-noche)
                candidatos = sorted(grupos_n, key=lambda x: deudas[x], reverse=True)
                for g in candidatos:
                    if deudas[g] > 0:
                        # Si trabajó anoche (T3), no puede compensar hoy mismo por ley de fatiga
                        if mem_t[g] != "T3":
                            libranza = g
                            deudas[g] -= 1
                            break

            # 2. ASIGNACIÓN DE TURNOS A LOS ACTIVOS
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                # Rotación base
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # Regla de Oro: Si viene de T3, se queda en T3 o descansa (no T1/T2)
                if mem_t[g] == "T3" and t_base in ["T1", "T2"]:
                    t_base = "T3"
                
                # Límite de 6 noches
                if mem_n[g] >= 6 and t_base == "T3":
                    t_base = "T1"
                
                turnos_hoy[g] = t_base

            # 3. MOTOR DE COBERTURA Y REFUERZO T2
            # Paso A: Asegurar T1, T2, T3
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    for gf in sorted(activos, key=lambda x: mem_n[x]):
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if not (mem_t[gf] == "T3" and tr == "T1"):
                                turnos_hoy[gf] = tr; break

            # Paso B: Eliminar Doble Noche y enviar a T2 (Regla Richard)
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                for g_n in activos:
                    if turnos_hoy[g_n] == "T3" and mem_t[g_n] != "T3":
                        turnos_hoy[g_n] = "T2"
                        actuales = list(turnos_hoy.values())
                        break
                # Si persiste por inercia de T3, forzar al que menos noches lleve
                if actuales.count("T3") > 1:
                    g_f = sorted(activos, key=lambda x: mem_n[x])[0]
                    turnos_hoy[g_f] = "T2"
                    actuales = list(turnos_hoy.values())

            # Paso C: Cualquier grupo extra va a T2 (Refuerzo Flotante)
            for g_e in activos:
                if turnos_hoy[g_e] != "T2" and actuales.count(turnos_hoy[g_e]) > 1:
                    turnos_hoy[g_e] = "T2"
                    actuales = list(turnos_hoy.values())

            # 4. REGISTRO Y ACTUALIZACIÓN DE MEMORIA
            for g in grupos_n:
                if g == libranza:
                    t_f = "DESC" if dia_idx >= 5 else "COMP"
                    n_a = 0
                else:
                    t_f = turnos_hoy.get(g, "T1")
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

    # --- VALIDADOR ORIGINAL ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.divider()
        st.subheader("🔍 Validador de Auditoría Legal Richard")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**✅ Verificación de Descansos**")
            conteo = df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
            st.table(conteo)
            
            # Alerta si alguien termina con deuda (significa que no se le pudo pagar en el rango)
            ultimas = df_res.drop_duplicates('Grupo', keep='last')
            for _, r in ultimas.iterrows():
                if r['Deuda_Compensatorio'] > 0:
                    st.error(f"🚨 {r['Grupo']} termina con {r['Deuda_Compensatorio']} compensatorio(s) sin pagar!")

        with c2:
            st.write("**🛡️ Auditoría de Salud y Cobertura**")
            alertas = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                if "T3" not in tv: alertas.append(f"{fc} (Sin Noche)")
                if list(tv).count("T3") > 1: alertas.append(f"{fc} (Doble Noche)")

            if not alertas: st.success("¡Operación Blindada! T3 único y Ley de Descanso cumplida.")
            else: st.warning(f"Novedades: {', '.join(set(alertas[:5]))}")
