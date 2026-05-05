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
            st.error("❌ No se encontró GITHUB_TOKEN en los Secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
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
        repo.update_file("malla_historica.xlsx", "Sincronización Cobertura Total", output.getvalue(), contents.sha)
        st.success("✅ Malla sincronizada.")
    except Exception as e:
        st.error(f"Error al sincronizar: {e}")

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
    sobrantes = masters + tecnicos_a + tecnicos_b
    for s in sobrantes: s['Grupo'] = "Reserva"
    grupos_finales.extend(sobrantes)
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
            df_c = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
            st.session_state.df_cable = df_c
        except: return
    
    if st.button("🎲 Mezclar Grupos"):
        st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
        st.rerun()
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 3. PROGRAMADOR CON COBERTURA OBLIGATORIA ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Cobertura Obligatoria")
    
    if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None
    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre Anterior"):
        estado_ayer_base = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_base)

    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla Obligatoria"):
        st.cache_data.clear()
        lista_fechas = []
        curr = f_inicio
        while curr <= f_fin:
            lista_fechas.append(curr); curr += timedelta(days=1)

        resultados = []
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        deudas = {g: 0 for g in grupos}
        memoria_hoy = estado_ayer_base.copy()
        co_holidays = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Definir Libranza (Solo 1 grupo por día)
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(deudas, key=deudas.get, reverse=True):
                    # Solo compensa si NO viene de T3 para asegurar descanso real
                    if deudas[g] > 0 and memoria_hoy[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación de Turnos (3 Grupos Activos)
            activos = [g for g in grupos if g != libranza]
            turnos_dia = {}
            
            # Reparto inicial basado en la semana
            for g in activos:
                idx_g = grupos.index(g)
                # Rotación base
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                # Protección T3 -> T1 (Si ayer hizo T3, hoy no puede hacer T1)
                if memoria_hoy[g] == "T3" and t_base == "T1":
                    t_base = "T3"
                turnos_dia[g] = t_base

            # --- MOTOR DE COBERTURA OBLIGATORIA ---
            # Verificamos que T1, T2 y T3 estén presentes
            for t_necesario in ["T1", "T2", "T3"]:
                if t_necesario not in turnos_dia.values():
                    # Si falta un turno, buscamos al grupo activo que tenga un turno repetido
                    for g_potencial in activos:
                        conteo_turno = list(turnos_dia.values()).count(turnos_dia[g_potencial])
                        if conteo_turno > 1:
                            # Validamos que el cambio no viole la salud (No pasar a T1 si viene de T3)
                            if not (memoria_hoy[g_potencial] == "T3" and t_necesario == "T1"):
                                turnos_dia[g_potencial] = t_necesario
                                break
            
            # Doble Verificación: Si después del ajuste sigue faltando un turno (caso extremo salud)
            # El sistema prioriza la cobertura sobre la rotación semanal
            for t_necesario in ["T1", "T2", "T3"]:
                if t_necesario not in turnos_dia.values():
                    for g_final in activos:
                         if not (memoria_hoy[g_final] == "T3" and t_necesario == "T1"):
                             turnos_dia[g_final] = t_necesario
                             break

            for g in grupos:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_dia.get(g, "T1")
                resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": pd.to_datetime(fecha)})
                memoria_hoy[g] = t_f

        df_nueva = pd.DataFrame(resultados)
        guardar_malla_en_historico(df_nueva)
        st.session_state.malla_generada = df_nueva
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
        st.subheader("🔍 Validador de Cumplimiento")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**✅ Descansos**")
            st.table(df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Turno']).size().unstack(fill_value=0))
        with c2:
            st.write("**🛡️ Auditoría de Cobertura Diaria**")
            alertas = []
            for fc in df_res["Fecha_Col"].unique():
                tv = df_res[df_res["Fecha_Col"] == fc]["Turno"].values
                for t in ["T1", "T2", "T3"]:
                    if t not in tv: alertas.append(f"{fc} (Falta {t})")
            
            if not alertas: st.success("¡Operación Blindada: T1, T2 y T3 cubiertos todos los días!")
            else: st.error(f"¡Atención! Huecos detectados: {', '.join(alertas)}")
