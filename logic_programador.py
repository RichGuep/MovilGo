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
        repo.update_file("malla_historica.xlsx", "Actualización Malla Completa", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. FUNCIONES DE APOYO Y HORARIOS ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"]: return True
    if hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia[hoy] >= jerarquia[ayer]

def obtener_horarios(turno):
    horarios = {
        "T1": ("05:30", "13:30"),
        "T2": ("13:30", "21:30"),
        "T3": ("21:30", "05:30"),
        "DESC": ("OFF", "OFF"),
        "COMP": ("OFF", "OFF")
    }
    return horarios.get(turno, ("-", "-"))

# --- 3. PANTALLA: GESTIÓN DE GRUPOS ---

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
    for s in (masters + tecnicos_a + tecnicos_b): s['Grupo'] = "Reserva"; grupos_finales.append(s)
    return pd.DataFrame(grupos_finales)

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
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    
    if st.button("🎲 Mezclar Grupos Aleatorio"):
        st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
        st.rerun()
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PANTALLA: PROGRAMADOR ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Proyección Legal Richard")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Carga los empleados en Gestión de Grupos primero.")
        return

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Ver Memoria de Cierre"):
        estado_base = obtener_ultimo_estado_github(repo)
        st.write(estado_base)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin (Proyección)", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla y Reportes"):
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

            # 1. Libranzas y Compensatorios (Prioridad Legal)
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Turnos con Salud (Ascendente)
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                turnos_hoy[g] = t_sug

            # 3. Cobertura Estricta y Refuerzo T2
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    for gf in sorted(activos, key=lambda x: mem_n[x]):
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            # Limpiar Doble Noche y enviar excedente a T2
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                for g_n in activos:
                    if turnos_hoy[g_n] == "T3" and mem_t[g_n] != "T3":
                        turnos_hoy[g_n] = "T2"; actuales = list(turnos_hoy.values()); break
            
            # 4. Registro Malla Grupal y Detallada
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                h_ini, h_fin = obtener_horarios(t_f)
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                
                personal_grupo = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in personal_grupo.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'),
                        "Fecha_Col": col_name,
                        "Mes": fecha.strftime('%B %Y'),
                        "Nombre": p['Nombre'],
                        "Cargo": p['Cargo'],
                        "Cedula": p['Cedula'],
                        "Hora Inicio": h_ini,
                        "Hora Fin": h_fin,
                        "Grupo": g,
                        "Turno": t_f,
                        "Fecha_Raw": pd.to_datetime(fecha),
                        "Noches_Acum": n_a,
                        "Deuda_Compensatorio": deudas[g]
                    })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df_full = st.session_state.malla_generada
        df_matriz = df_full.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        # --- VISTAS ---
        st.subheader("📊 Matriz de Turnos (Grupos)")
        matriz = df_matriz.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_matriz["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.subheader("📋 Malla Operativa (Individual)")
        st.dataframe(df_full[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo"]], use_container_width=True, hide_index=True)

        # --- VALIDADOR ---
        st.divider()
        st.subheader("🔍 Resumen de Auditoría Mensual")
        resumen_mes = df_full[df_full['Turno'].isin(['DESC', 'COMP'])].drop_duplicates(['Grupo', 'Fecha_Raw'])
        if not resumen_mes.empty:
            conteo = resumen_mes.groupby(['Mes', 'Grupo', 'Turno']).size().unstack(fill_value=0)
            st.table(conteo)
        
        # Alerta legal
        ultimas = df_full.drop_duplicates('Grupo', keep='last')
        for _, r in ultimas.iterrows():
            if r['Deuda_Compensatorio'] > 0:
                st.error(f"🚨 {r['Grupo']} termina con {r['Deuda_Compensatorio']} días sin compensar.")
