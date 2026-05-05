import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONEXIÓN Y PERSISTENCIA GITHUB (MEMORIA HISTÓRICA) ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ No se encontró GITHUB_TOKEN en los Secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Obtiene el último turno de cada grupo desde el archivo histórico en GitHub"""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            registros_grupo = df_hist[df_hist['Grupo'] == g]
            if not registros_grupo.empty:
                ultimo_registro = registros_grupo.sort_values('Fecha_Raw').iloc[-1]
                estado[g] = ultimo_registro['Turno']
            else:
                estado[g] = "DESC"
        return estado
    except:
        return {g: "DESC" for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def guardar_malla_en_historico(df_nueva):
    """Une la nueva programación con el histórico y lo sube a GitHub"""
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
        
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            repo.update_file("malla_historica.xlsx", "Actualización Histórico Malla", output.getvalue(), contents.sha)
        except:
            repo.create_file("malla_historica.xlsx", "Creación Histórico Malla", output.getvalue())
        st.success("✅ Malla guardada y sincronizada en el histórico de GitHub.")
    except Exception as e:
        st.error(f"Error al sincronizar histórico: {e}")

# --- 2. MÓDULO: GESTIÓN DE GRUPOS ---

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

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎲 Mezclar Grupos"):
            st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
            st.rerun()
    with c2:
        if st.button("💾 Guardar Grupos en GitHub"):
            repo = conectar_github()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.df_cable.to_excel(writer, index=False)
            contents = repo.get_contents("empleados.xlsx")
            repo.update_file("empleados.xlsx", "Update Empleados", output.getvalue(), contents.sha)
            st.success("Grupos actualizados.")

    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True, hide_index=True)

# --- 3. MÓDULO: PROGRAMADOR ---

def pantalla_programador():
    st.title("📅 Programador 24/7 con Histórico")
    repo = conectar_github()
    if not repo: return

    # Carga de estado inicial desde GitHub
    with st.expander("👁️ Ver estado de cierre anterior (GitHub)", expanded=False):
        estado_ayer = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer)

    st.subheader("Rango de Programación")
    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Fecha Inicio", datetime.now())
    f_fin = c_f2.date_input("Fecha Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar y Sincronizar Malla"):
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        deudas = {g: 0 for g in grupos}
        co_holidays = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Definir libranzas
            libranza = None
            if dia_idx == 5: # Sab
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Dom
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Compensatorios (Evitar darlos justo tras un T3)
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    if deudas[g] > 0 and estado_ayer[g] != "T3":
                        libranza = g
                        deudas[g] -= 1
                        break

            # 2. Asignación de Turnos (Blindaje de Salud T3 -> T1)
            activos = [g for g in grupos if g != libranza]
            turnos_dia = {}
            for g in activos:
                idx_g = grupos.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # REGLA DE ORO: Si ayer terminó en T3, hoy NO puede ser T1
                if estado_ayer[g] == "T3" and t_base == "T1":
                    t_base = "T3"
                turnos_dia[g] = t_base

            # 3. Ajuste Cobertura (Solo un T3 y asegurar T1/T2)
            actuales = list(turnos_dia.values())
            while actuales.count("T3") > 1:
                for g in activos:
                    if turnos_dia[g] == "T3" and estado_ayer[g] != "T3":
                        turnos_dia[g] = "T2"
                        actuales = list(turnos_dia.values())
                        break

            # 4. Consolidar Día
            for g in grupos:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_dia.get(g, "T1")
                resultados.append({
                    "Grupo": g, 
                    "Fecha_Col": col_name, 
                    "Turno": t_f, 
                    "Fecha_Raw": pd.to_datetime(fecha)
                })
                estado_ayer[g] = t_f

        df_nueva = pd.DataFrame(resultados)
        guardar_malla_en_historico(df_nueva)

        # Matriz Visual
        matriz = df_nueva.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_nueva["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # --- VALIDADOR DE AUDITORÍA ---
        st.divider()
        st.subheader("🔍 Validador de Cumplimiento")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**✅ Descansos Otorgados**")
            st.table(df_nueva[df_nueva['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0))
        with c2:
            st.write("**🛡️ Auditoría de Salud y Cobertura**")
            alertas = []
            for fc in df_nueva["Fecha_Col"].unique():
                tv = df_nueva[df_nueva["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: alertas.append(f"{fc} (Falta {t})")
                if list(tv).count("T3") > 1: alertas.append(f"{fc} (Doble T3 ⚠️)")
            
            if not alertas: st.success("¡Operación Segura!")
            else: st.error(f"Alertas: {', '.join(alertas)}")
