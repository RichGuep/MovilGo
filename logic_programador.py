import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONEXIÓN Y PERSISTENCIA GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except:
        return None

def obtener_ultimo_estado_github(repo):
    """Obtiene el cierre del mes anterior para dar continuidad"""
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
        repo.update_file("malla_historica.xlsx", "Malla Richard Final Completa", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except:
        pass

# --- 2. MOTOR DE SALUD Y HORARIOS ---

def es_rotacion_valida(ayer, hoy):
    """Bloquea saltos descendentes: Prohibido T3->T1, T3->T2, T2->T1"""
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    niveles = {"T1": 1, "T2": 2, "T3": 3}
    return niveles[hoy] >= niveles[ayer]

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

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
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            df.columns = df.columns.str.strip()
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except:
            st.error("Falta archivo empleados.xlsx")
            return
    
    if st.button("🎲 Mezclar Grupos"):
        st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
        st.rerun()
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PANTALLA: PROGRAMADOR ---

def pantalla_programador():
    st.title("📅 Programador Maestro Richard")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Carga empleados en Gestión de Grupos primero.")
        return

    repo = conectar_github()
    if not repo: return
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin (Proyección)", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla Richard"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        m_t = {g: estado_base[g]["u"] for g in grupos_n}
        m_n = {g: estado_base[g]["n"] for g in grupos_n}
        m_d = {g: estado_base[g]["d"] for g in grupos_n}
        col_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            d_idx = fecha.weekday()
            s_iso = fecha.isocalendar()[1]
            f_col = fecha.strftime('%a %d/%m')

            # --- A. LIBRANZAS Y COMPENSATORIOS ---
            lib = None
            if d_idx == 5: # Sábado
                lib = "Grupo 1" if s_iso % 2 == 0 else "Grupo 2"
                m_d["Grupo 2" if s_iso % 2 == 0 else "Grupo 1"] += 1
            elif d_idx == 6: # Domingo
                lib = "Grupo 3" if s_iso % 2 == 0 else "Grupo 4"
                m_d["Grupo 4" if s_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Prioridad legal: Pagar deuda en semana siguiente
                for g in sorted(grupos_n, key=lambda x: m_d[x], reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3":
                        lib = g; m_d[g] -= 1; break

            # --- B. ASIGNACIÓN INICIAL (CANDADO SALUD) ---
            activos = [g for g in grupos_n if g != lib]
            hoy_t = {}
            for g in activos:
                idx = grupos_n.index(g)
                sug = ["T1", "T2", "T3"][(idx + s_iso) % 3]
                
                # INERCIA: Si es salto hacia atrás, se mantiene en el turno de ayer
                if not es_rotacion_valida(m_t[g], sug):
                    sug = m_t[g]
                
                # Límite 6 noches seguidas
                if m_n[g] >= 6 and sug == "T3": sug = "T1"
                hoy_t[g] = sug

            # --- C. COBERTURA Y REFUERZO T2 ---
            for tr in ["T1", "T2", "T3"]:
                if tr not in hoy_t.values():
                    for gf in sorted(activos, key=lambda x: m_n[x]):
                        if list(hoy_t.values()).count(hoy_t[gf]) > 1:
                            if es_rotacion_valida(m_t[gf], tr):
                                hoy_t[gf] = tr; break

            # Prohibir Doble T3
            while list(hoy_t.values()).count("T3") > 1:
                for gn in activos:
                    if hoy_t[gn] == "T3" and m_t[gn] != "T3":
                        hoy_t[gn] = "T2"; break

            # Flotante a T2
            act_list = list(hoy_t.values())
            for ge in activos:
                if hoy_t[ge] != "T2" and act_list.count(hoy_t[ge]) > 1:
                    hoy_t[ge] = "T2"; act_list = list(hoy_t.values())

            # --- D. REGISTRO DETALLADO ---
            for g in grupos_n:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else hoy_t.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                n_a = m_n[g] + 1 if t_f == "T3" else 0
                
                personal = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in personal.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], 
                        "Cargo": p['Cargo'], "Cedula": p['Cedula'], "Hora Inicio": h_i, 
                        "Hora Fin": h_f, "Grupo": g, "Turno": t_f, "Fecha_Col": f_col,
                        "Mes": fecha.strftime('%B %Y'), "Fecha_Raw": pd.to_datetime(fecha),
                        "Noches_Acum": n_a, "Deuda_Compensatorio": m_d[g]
                    })
                m_t[g] = t_f; m_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz Grupal (Vista Rápida)")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        st.dataframe(mat.style.map(lambda v: f'background-color: {{"T1":"#1f77b4","T2":"#2ca02c","T3":"#7f7f7f","DESC":"#ff4b4b","COMP":"#ffa500"}.get(v,"#31333F")}; color:white'), use_container_width=True)

        st.subheader("📋 Malla Operativa Individual (Formato Richard)")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo"]], use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🔍 Auditoría Mensual de Descansos")
        res = df[df['Turno'].isin(['DESC', 'COMP'])].drop_duplicates(['Grupo', 'Fecha_Raw'])
        if not res.empty:
            st.table(res.groupby(['Mes', 'Grupo', 'Turno']).size().unstack(fill_value=0))
