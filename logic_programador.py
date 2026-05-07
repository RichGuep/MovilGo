import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN Y GITHUB (Se mantiene igual que tu base) ---
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
        repo.update_file("malla_historica.xlsx", "Malla Saludable V5 - Balanceada", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. LÓGICA DE SALUD ---
def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"]: return True
    if hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold'

# --- 3. PANTALLA PRINCIPAL ---
def pantalla_programador():
    st.set_page_config(layout="wide")
    st.title("📅 Programador 24/7 - Configuración Personalizada")
    
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    
    repo = conectar_github()
    if not repo: return
    estado_ayer_dict = obtener_ultimo_estado_github(repo)

    # --- SECCIÓN DE CONFIGURACIÓN ---
    with st.sidebar:
        st.header("⚙️ Configuración de Descansos")
        descansos_config = {}
        for g in grupos_n:
            # Por defecto asignamos Sábado/Domingo como en tu código original
            default_day = 5 if "1" in g or "2" in g else 6 
            dia_sel = st.selectbox(f"Día Descanso {g}", dias_semana, index=default_day)
            descansos_config[g] = dias_semana.index(dia_sel)

        st.divider()
        c_f1, c_f2 = st.columns(2)
        f_ini = c_f1.date_input("Inicio", datetime.now())
        f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla Balanceada"):
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado_ayer_dict[g]["u"] for g in grupos_n}
        mem_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
        deudas = {g: estado_ayer_dict[g]["d"] for g in grupos_n}
        # Contador de turnos para balanceo
        stats_turnos = {g: {"T1": 0, "T2": 0, "T3": 0} for g in grupos_n}
        
        co_h = holidays.Colombia(years=[f_ini.year, f_fin.year])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # 1. Identificar quién descansa hoy según la configuración manual
            libranzas_hoy = [g for g, d in descansos_config.items() if d == dia_idx]
            
            # 2. Gestionar Compensatorios (Si es festivo, alguien podría ganar deuda o cobrarla)
            # Lógica simple: Si es festivo y trabajas, sumas deuda. Si no es tu día de descanso pero hay exceso de personal, descansas.
            
            activos = [g for g in grupos_n if g not in libranzas_hoy]
            turnos_hoy = {}

            # 3. Asignación con Balanceo y Salud
            # Ordenamos turnos necesarios: T1, T2, T3
            turnos_necesarios = ["T1", "T2", "T3"]
            
            # Priorizamos asignar a los grupos que menos han hecho ese turno específico
            for t_req in turnos_necesarios:
                # Filtrar candidatos que pueden hacer t_req por salud
                candidatos = [g for g in activos if g not in turnos_hoy and es_cambio_saludable(mem_t[g], t_req)]
                
                if candidatos:
                    # Elegir al que menos veces haya hecho este turno en el mes
                    elegido = min(candidatos, key=lambda x: stats_turnos[x][t_req])
                    turnos_hoy[elegido] = t_req
                    stats_turnos[elegido][t_req] += 1
                else:
                    # Si nadie puede por salud, forzar el menos perjudicial (ej. repetir turno anterior)
                    candidatos_emergencia = [g for g in activos if g not in turnos_hoy]
                    if candidatos_emergencia:
                        elegido = candidatos_emergencia[0]
                        turnos_hoy[elegido] = t_req
                        stats_turnos[elegido][t_req] += 1

            # 4. Consolidar resultados del día
            for g in grupos_n:
                if g in libranzas_hoy:
                    t_f = "DESC"
                elif g in turnos_hoy:
                    t_f = turnos_hoy[g]
                else:
                    t_f = "COMP" # Si sobran grupos (más de 3 activos)
                
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_t[g] = t_f
                mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- VISUALIZACIÓN Y AUDITORÍA ---
    if 'malla_generada' in st.session_state and st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        
        # Matriz Principal
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        st.subheader("📊 Malla de Turnos Generada")
        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # --- SECCIÓN DE AUDITORÍA (Lo que pediste) ---
        st.divider()
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("⚖️ Auditoría de Carga")
            # Contar turnos por grupo
            conteo = df_res.groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
            st.write("Distribución total de turnos en el periodo:")
            st.dataframe(conteo)
            
            # Alerta de desequilibrio
            if 'T3' in conteo.columns:
                max_noche = conteo['T3'].max()
                min_noche = conteo['T3'].min()
                if (max_noche - min_noche) > 2:
                    st.warning(f"⚠️ Desequilibrio en Noches: Diferencia de {max_noche - min_noche} turnos.")
                else:
                    st.success("✅ Turnos de noche equilibrados.")

        with col2:
            st.subheader("🛡️ Validación Legal")
            df_res['Semana'] = df_res['Fecha_Raw'].dt.isocalendar().week
            descansos_semana = df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Semana']).size().unstack(fill_value=0)
            
            st.write("Días libres por semana (Min 1):")
            def destacar_ley(val):
                color = 'red' if val < 1 else 'green'
                return f'color: {color}'
            
            st.dataframe(descansos_semana.style.map(destacar_ley))

        if st.button("💾 Confirmar y Sincronizar a GitHub"):
            guardar_malla_en_historico(df_res)

if __name__ == "__main__":
    pantalla_programador()
