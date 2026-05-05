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
            st.error("❌ Token GITHUB_TOKEN no configurado en los Secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Obtiene el último turno y el historial de noches para dar continuidad"""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            registros = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
            if not registros.empty:
                ultimo_reg = registros.iloc[-1]
                estado[g] = {
                    "ultimo_turno": ultimo_reg['Turno'],
                    "noches_seguidas": int(ultimo_reg.get('Noches_Acum', 0)) if ultimo_reg['Turno'] == "T3" else 0
                }
            else:
                estado[g] = {"ultimo_turno": "DESC", "noches_seguidas": 0}
        return estado
    except:
        return {g: {"ultimo_turno": "DESC", "noches_seguidas": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

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
        repo.update_file("malla_historica.xlsx", "Actualización Malla - Blindaje Fatiga", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar histórico: {e}")

# --- 2. GESTIÓN DE GRUPOS ---

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

# --- 3. PROGRAMADOR PROFESIONAL ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Blindaje de Fatiga")
    grupos_nombres = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre del Ciclo Anterior (Memoria)"):
        estado_ayer_dict = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_dict)

    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio de Malla", datetime.now())
    f_fin = c_f2.date_input("Fin de Malla", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Programación Segura"):
        st.cache_data.clear()
        lista_fechas = [f_inicio + timedelta(days=x) for x in range((f_fin - f_inicio).days + 1)]

        resultados = []
        deudas = {g: 0 for g in grupos_nombres}
        # Desglosamos el estado anterior
        memoria_turno = {g: estado_ayer_dict[g]["ultimo_turno"] for g in grupos_nombres}
        noches_seguidas = {g: estado_ayer_dict[g]["noches_seguidas"] for g in grupos_nombres}
        
        co_holidays = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Gestión de Libranzas
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Prioridad a quien lleva más noches para que descanse
                for g in sorted(grupos_nombres, key=lambda x: (noches_seguidas[x], deudas[x]), reverse=True):
                    if deudas[g] > 0 and memoria_turno[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación de Turnos (3 Activos)
            activos = [g for g in grupos_nombres if g != libranza]
            turnos_dia = {}
            
            for g in activos:
                idx_g = grupos_nombres.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # REGLA ORO 1: Blindaje T3 -> T1/T2 (No cambio brusco)
                if memoria_turno[g] == "T3" and t_base in ["T1", "T2"]:
                    t_base = "T3"
                
                # REGLA ORO 2: Límite de 7 noches seguidas
                if noches_seguidas[g] >= 7 and t_base == "T3":
                    t_base = "T1" # Forzamos salida del ciclo nocturno
                
                turnos_dia[g] = t_base

            # 3. Motor de Cobertura Obligatoria e Intercambio
            for t_req in ["T1", "T2", "T3"]:
                if t_req not in turnos_dia.values():
                    # Buscamos quién puede cubrirlo con menor riesgo
                    for g_c in sorted(activos, key=lambda x: noches_seguidas[x]):
                        if list(turnos_dia.values()).count(turnos_dia[g_c]) > 1:
                            if not (memoria_turno[g_c] == "T3" and t_req in ["T1", "T2"]):
                                turnos_dia[g_c] = t_req; break

            # 4. Registro y actualización de contadores
            for g in grupos_nombres:
                if g == libranza:
                    t_final = "DESC" if dia_idx >= 5 else "COMP"
                else:
                    t_final = turnos_dia.get(g, "T1")
                
                # Actualizar contador de noches
                n_acum = noches_seguidas[g] + 1 if t_final == "T3" else 0
                noches_seguidas[g] = n_acum

                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_final, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_acum
                })
                memoria_turno[g] = t_final

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df_m = st.session_state.malla_generada
        matriz = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res_cols := df_m["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.divider()
        st.subheader("🔍 Validador de Seguridad Richard")
        c1, c2 = st.columns(2)
        with c2:
            alertas = []
            for fc in df_m["Fecha_Col"].unique():
                tv = df_m[df_m["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: alertas.append(f"{fc} (Falta {t})")
            
            for g in grupos_nombres:
                h = df_m[df_m["Grupo"] == g].to_dict('records')
                for i in range(1, len(h)):
                    if h[i-1]['Turno'] == "T3" and h[i]['Turno'] in ["T1", "T2"]:
                        alertas.append(f"⚠️ {g} Choque Horario brusco")
                    if h[i]['Noches_Acum'] > 7:
                        alertas.append(f"⚠️ {g} Exceso de noches (>7)")

            if not alertas: st.success("¡Operación Segura, Humana y Cobertura Total!")
            else: st.error(f"Novedades detectadas: {', '.join(set(alertas))}")
