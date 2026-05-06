import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA Y MEMORIA ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except: return None

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

# --- 2. MOTOR DE SALUD (BLOQUEO T3-T1) ---

def es_cambio_seguro(ayer, hoy):
    """
    Bloquea saltos hacia atrás: T3->T1, T3->T2, T2->T1.
    T1=1, T2=2, T3=3. Hoy debe ser >= Ayer.
    """
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia[hoy] >= jerarquia[ayer]

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30"),
         "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("-", "-"))

# --- 3. PANTALLA GESTIÓN ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PROGRAMADOR CON BLINDAJE ---

def pantalla_programador():
    st.title("📅 Programador Richard - Blindaje T3 a T1")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue empleados primero.")
        return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla con Bloqueo de Saltos"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado_base[g]["u"] for g in grupos_n}
        mem_n = {g: estado_base[g]["n"] for g in grupos_n}
        deudas = {g: estado_base[g]["d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            
            # 1. Libranzas y Compensatorios (Prioridad Legal)
            lib = None
            if d_idx == 5:
                lib = "Grupo 1" if s_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if s_iso % 2 == 0 else "Grupo 1"] += 1
            elif d_idx == 6:
                lib = "Grupo 3" if s_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if s_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Cobro de deudas (Pagar compensatorios)
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        lib = g; deudas[g] -= 1; break

            # 2. Asignación inicial con Candado de Salud
            activos = [g for g in grupos_n if g != lib]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + s_iso) % 3]
                
                # APLICAR BLINDAJE: Si el cambio no es seguro, inercia (mismo de ayer)
                if not es_cambio_seguro(mem_t[g], t_sug):
                    t_sug = mem_t[g]
                
                # Límite 6 noches
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                
                turnos_hoy[g] = t_sug

            # 3. Cobertura Estricta (Asegurar T1, T2, T3)
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    # Solo grupos que pueden cubrir sin saltos prohibidos
                    for gf in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_seguro(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            # 4. Registro y actualización de memoria
            for g in grupos_n:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else turnos_hoy.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                
                personal = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in personal.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'),
                        "Noches_Acum": n_a, "Deuda": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                mem_t[g], mem_n[g] = t_f, n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df = st.session_state.malla_generada
        df_res = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz de Turnos (Resumen)")
        mat = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo_t(v):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(v, "#31333F")}; color: white; font-weight: bold'
        st.dataframe(mat.style.map(estilo_t), use_container_width=True)

        st.subheader("📋 Malla Operativa Detallada")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo"]], hide_index=True)
