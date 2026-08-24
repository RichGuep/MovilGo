import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
import os
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# =========================================================
# 1. CONSTANTES Y ESTILOS GLOBALES GREENMOVIL
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia(years=range(2025, 2030))

COLORES_MAP = {
    "SOPORTE": "#E8DAEF", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053", "DISPONIBLE": "#EAEDED"
}

def style_malla_green(df_pivot):
    styles = pd.DataFrame('', index=df_pivot.index, columns=df_pivot.columns)
    
    turnos_unicos = []
    for col in df_pivot.columns:
        turnos_unicos.extend(df_pivot[col].astype(str).unique().tolist())
    turnos_unicos = list(set(turnos_unicos))
    
    paleta_dinamica = ["#D6EAF8", "#D5F5E3", "#FADBD8", "#FCF3CF", "#D7BDE2", "#A3E4D7", "#F9E79F", "#F5CBA7"]
    mapa_dinamico = {}
    idx_color = 0
    for t in turnos_unicos:
        if t not in COLORES_MAP and t not in ["DESCANSO", "COMPENSADO"] and "PENDIENTE" not in t:
            mapa_dinamico[t] = paleta_dinamica[idx_color % len(paleta_dinamica)]
            idx_color += 1

    for col in df_pivot.columns:
        es_fin_semana = False
        es_festivo = False
        try:
            fecha_dt = pd.to_datetime(col)
            if fecha_dt.weekday() in [5, 6]: es_fin_semana = True
            if fecha_dt in festivos_co: es_festivo = True
        except: pass

        for idx in df_pivot.index:
            val = str(df_pivot.at[idx, col]).strip()
            
            if "PENDIENTE" in str(idx): 
                bg, txt = "#E74C3C", "white"
            elif val in COLORES_MAP: 
                bg, txt = COLORES_MAP[val], ("white" if val in ["DESCANSO", "COMPENSADO"] else "#17202A")
            elif val in mapa_dinamico: 
                bg, txt = mapa_dinamico[val], "#17202A"
            else: 
                bg, txt = ("#1B2631" if val in ["DESCANSO", "COMPENSADO"] else "#f8f9fa"), ("white" if val in ["DESCANSO", "COMPENSADO"] else "#17202A")
                
            border = "2px solid #E67E22" if es_festivo else ("1.5px solid #7F8C8D" if es_fin_semana else "0.5px solid #D5DBDB")
            styles.at[idx, col] = f'background-color: {bg}; color: {txt}; font-weight: 700; border: {border};'
    return df_pivot.style.apply(lambda _: styles, axis=None)

# =========================================================
# 2. CONEXIONES: DATA WAREHOUSE Y BASE DE DATOS LOCAL
# =========================================================
# 🔴 ATENCIÓN: PON AQUÍ TU CONTRASEÑA DEL DATA WAREHOUSE
URL_DWH = "postgresql://richard.guevara:G8#Rh25@10.0.22.78:5432/GRMDW"
load_dotenv(override=True)
URL_LOCAL = os.getenv("DATABASE_URL", "postgresql://postgres:Rc130523@localhost:5432/movilgo").replace('"', '').replace("'", "")

try: engine_dwh = create_engine(URL_DWH, connect_args={'client_encoding': 'utf8'})
except: engine_dwh = None

try: 
    engine_local = create_engine(URL_LOCAL)
    
    # 🌟 MOTOR DE AUTO-CREACIÓN DE TABLAS (GREENMOVIL)
    def inicializar_tablas_greenmovil():
        try:
            with engine_local.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS green_personal_activo (
                        "Cedula" VARCHAR(50),
                        "Nombre" VARCHAR(100),
                        "Cargo" VARCHAR(100),
                        "Sede" VARCHAR(100),
                        "Email" VARCHAR(100),
                        "EquipoAsignado" VARCHAR(100)
                    )
                """))
        except Exception as e:
            print(f"Aviso de Inicialización BD (Greenmovil): {e}")

    inicializar_tablas_greenmovil() # Ejecutamos la validación al arrancar

except: engine_local = None

def guardar_local(df, nombre_tabla):
    try:
        df.to_sql(nombre_tabla, engine_local, if_exists="replace", index=False)
        return True
    except Exception as e:
        st.error(f"Error escribiendo en BD Local: {e}")
        return False

def guardar_malla_historico(df, nombre_tabla, inicio, fin):
    inicio_str = inicio.strftime('%Y-%m-%d')
    fin_str = fin.strftime('%Y-%m-%d')
    try:
        try:
            df_existente = pd.read_sql(f"SELECT * FROM {nombre_tabla}", engine_local)
            df_existente['Fecha_str'] = pd.to_datetime(df_existente['Fecha']).dt.strftime('%Y-%m-%d')
            mask = ~((df_existente['Fecha_str'] >= inicio_str) & (df_existente['Fecha_str'] <= fin_str))
            df_limpio = df_existente[mask].drop(columns=['Fecha_str'])
        except:
            df_limpio = pd.DataFrame()

        df_nuevo = df.copy()
        df_nuevo['Fecha'] = pd.to_datetime(df_nuevo['Fecha']).dt.strftime('%Y-%m-%d')
        df_final = pd.concat([df_limpio, df_nuevo], ignore_index=True)
        
        df_final.to_sql(nombre_tabla, engine_local, if_exists="replace", index=False)
        return True
    except Exception as e:
        return False

# =========================================================
# 3. UTILIDADES HTML / PDF / MAILING
# =========================================================
def generar_html_imprimible(df_pivot, titulo):
    html_content = f"""
    <html>
    <head>
        <title>{titulo}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            h1 {{ color: #145a4f; text-align: center; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 6px; text-align: center; }}
            th {{ background-color: #145a4f; color: white; }}
            .DESCANSO {{ background-color: #1B2631; color: white; font-weight: bold; }}
            .COMPENSADO {{ background-color: #2E4053; color: white; font-weight: bold; }}
            .PENDIENTE {{ background-color: #E74C3C; color: white; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>{titulo}</h1>
        <p>Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        {df_pivot.to_html(classes='table', border=0)}
        <script>
            document.querySelectorAll('td').forEach(function(td) {{
                if(td.innerText.trim() === 'DESCANSO') td.className = 'DESCANSO';
                if(td.innerText.trim() === 'COMPENSADO') td.className = 'COMPENSADO';
                if(td.innerText.includes('PENDIENTE')) td.className = 'PENDIENTE';
            }});
        </script>
    </body>
    </html>
    """
    b64 = base64.b64encode(html_content.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="Malla_{titulo.replace(" ", "_")}.html" target="_blank" style="text-decoration:none; color:white; background-color:#145a4f; padding:8px 12px; border-radius:8px;">📄 Descargar Vista Imprimible (Ctrl+P para PDF)</a>'
    return href

def enviar_correos_masivos(df_reporte, df_personal, mes_anio, remitente, password):
    if 'Fecha' in df_reporte.columns:
        df_reporte['Fecha_str'] = pd.to_datetime(df_reporte['Fecha']).dt.strftime('%d-%b')
    else: return False, "Error: El reporte no tiene columna de Fecha."

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
    except Exception as e:
        return False, f"Error de conexión SMTP: {e}"

    enviados = 0
    for _, emp in df_personal.iterrows():
        nombre = emp['Nombre']
        email_destino = emp.get('Email', None)
        
        if pd.isna(email_destino) or "@" not in str(email_destino): continue

        malla_empleado = df_reporte[df_reporte['Nombre'] == nombre]
        if malla_empleado.empty: continue
        
        tabla_turnos = "<table style='border-collapse: collapse; width: 100%;'><tr><th style='border: 1px solid #ddd; padding: 8px; background-color:#145a4f; color:white;'>Fecha</th><th style='border: 1px solid #ddd; padding: 8px; background-color:#145a4f; color:white;'>Turno Asignado</th></tr>"
        for _, row in malla_empleado.iterrows():
            turno_val = row['Turno realizado']
            color_bg = "#f2f2f2" if turno_val in ["DESCANSO", "COMPENSADO"] else "#ffffff"
            tabla_turnos += f"<tr style='background-color: {color_bg};'><td style='border: 1px solid #ddd; padding: 8px;'>{row['Fecha_str']}</td><td style='border: 1px solid #ddd; padding: 8px;'><b>{turno_val}</b></td></tr>"
        tabla_turnos += "</table>"

        html = f"""
        <html><body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                <div style="background-color: #145a4f; padding: 20px; text-align: center;">
                    <h2 style="color: white; margin: 0;">MovilGo - Operaciones Greenmovil</h2>
                </div>
                <div style="padding: 20px;">
                    <p>Hola <b>{nombre}</b>,</p>
                    <p>Tu programación operativa para el periodo <b>{mes_anio}</b> ha sido publicada oficialmente. A continuación, el detalle de tus turnos:</p>
                    <br>{tabla_turnos}<br>
                    <p style="font-size: 12px; color: #7f8c8d;">Recuerda presentarte a tu turno con anticipación. Correo generado automáticamente.</p>
                </div>
            </div>
        </body></html>
        """
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"📅 Tu Programación de Turnos - {mes_anio}"
        msg['From'] = remitente
        msg['To'] = email_destino
        msg.attach(MIMEText(html, "html"))
        
        try:
            server.sendmail(remitente, email_destino, msg.as_string())
            enviados += 1
        except: pass

    server.quit()
    return True, f"Se enviaron {enviados} correos exitosamente."

# =========================================================
# 4. EXTRACCIÓN DE PERSONAL GREENMOVIL (DWH)
# =========================================================
def pantalla_personal_green():
    st.markdown("## 👥 Extracción de Personal (Data Warehouse)")
    st.info("Conexión directa a **GRMDW**. Se extraerán empleados activos y sus correos corporativos.")

    if st.button("🔄 Conectar y Extraer Personal Activo"):
        with st.spinner("Conectando al DWH y extrayendo tabla DimEmpleados..."):
            try:
                query = 'SELECT * FROM public."DimEmpleados"'
                df_dwh = pd.read_sql(query, engine_dwh)
                col_estado = "EstadoEmpleado" if "EstadoEmpleado" in df_dwh.columns else ("estadoempleado" if "estadoempleado" in df_dwh.columns else None)
                if col_estado: df_dwh = df_dwh[df_dwh[col_estado] == 'A']
                
                st.session_state.df_dwh_raw = df_dwh
                st.success(f"✅ ¡Extracción exitosa! {len(df_dwh)} empleados activos traídos a memoria.")
            except Exception as e:
                st.error(f"⚠️ Error de extracción: {e}")

    if 'df_dwh_raw' in st.session_state and not st.session_state.df_dwh_raw.empty:
        df_raw = st.session_state.df_dwh_raw
        st.write("---")
        st.markdown("### 🔍 Mapeo y Filtrado")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        cols = df_raw.columns.tolist()
        
        col_nom = c1.selectbox("Columna Nombre:", cols, index=cols.index("NombreEmpleado") if "NombreEmpleado" in cols else 0)
        col_cargo = c2.selectbox("Columna Cargo:", cols, index=cols.index("Cargo") if "Cargo" in cols else 0)
        idx_ced = cols.index("CodEmpleado") if "CodEmpleado" in cols else (cols.index("Cod Empleado") if "Cod Empleado" in cols else 0)
        col_ced = c3.selectbox("Columna Cédula:", cols, index=idx_ced)
        col_empresa = c4.selectbox("Columna Sede:", cols, index=cols.index("CodEmpresa") if "CodEmpresa" in cols else 0)
        idx_email = cols.index("EmailEmpresa") if "EmailEmpresa" in cols else 0
        col_email = c5.selectbox("Columna Correo:", cols, index=idx_email)

        f1, f2 = st.columns(2)
        filtro_empresa = f1.selectbox("Filtrar por Sede:", ["Todas"] + df_raw[col_empresa].astype(str).unique().tolist())
        filtro_cargo = f2.multiselect("Filtrar Cargos Específicos:", df_raw[col_cargo].astype(str).unique().tolist())

        df_filtrado = df_raw.copy()
        if filtro_empresa != "Todas": df_filtrado = df_filtrado[df_filtrado[col_empresa].astype(str) == filtro_empresa]
        if filtro_cargo: df_filtrado = df_filtrado[df_filtrado[col_cargo].astype(str).isin(filtro_cargo)]

        st.dataframe(df_filtrado, use_container_width=True)

        if st.button("💾 Crear Plantilla Operativa Local"):
            df_limpio = pd.DataFrame({
                "Cedula": df_filtrado[col_ced],
                "Nombre": df_filtrado[col_nom],
                "Cargo": df_filtrado[col_cargo],
                "Sede": df_filtrado[col_empresa],
                "Email": df_filtrado[col_email], 
                "EquipoAsignado": "Grupo Único" 
            })
            guardar_local(df_limpio, "green_personal_activo")
            st.session_state.df_green_activo = df_limpio
            st.success("✅ Personal guardado en la BD Local. ¡Ve a Mallas Operaciones!")

def pantalla_parametrizador_green():
    st.info("Este módulo ha sido integrado en **📅 Mallas Operaciones** para que configures todo en una sola pantalla.")

# =========================================================
# 5. NÚCLEO ALGORÍTMICO Y EDITOR CONTEXTUAL
# =========================================================
def calcular_metricas_reforma(inicio_str, fin_str):
    if pd.isna(inicio_str) or pd.isna(fin_str) or "OFF" in inicio_str or "OFF" in fin_str: 
        return 0.0, 0.0, 0.0
    fmt = "%H:%M:%S" if len(inicio_str.split(":")) == 3 else "%H:%M"
    try:
        t_i, t_f = datetime.strptime(inicio_str, fmt), datetime.strptime(fin_str, fmt)
        min_i, min_f = t_i.hour * 60 + t_i.minute, t_f.hour * 60 + t_f.minute
        minutos_totales = min_f - min_i if min_f >= min_i else (1440 - min_i) + min_f
        total_horas = minutos_totales / 60.0
        minutos_nocturnos = sum(1 for m in range(min_i, min_i + int(minutos_totales)) if (m % 1440) >= 1140 or (m % 1440) < 360)
        return round(total_horas, 2), round(max(0.0, total_horas - 7.0), 2), round(minutos_nocturnos / 60.0, 2)
    except: return 0.0, 0.0, 0.0

@st.dialog("🛠️ Analizador y Editor Contextual de Turnos", width="large")
def popup_forzar_green(fecha_solicitada, sujeto_sel, opciones_turnos, df_malla):
    st.markdown(f"### 🎯 Ajuste de Malla para: **{sujeto_sel}**")
    st.markdown(f"**Fecha Operativa:** `{fecha_solicitada}`")
    
    fecha_dt = pd.to_datetime(fecha_solicitada)
    ini_v = (fecha_dt - timedelta(days=4)).strftime('%Y-%m-%d')
    fin_v = (fecha_dt + timedelta(days=4)).strftime('%Y-%m-%d')

    st.write("---")
    st.markdown("#### ⏳ Panorama Operativo del Equipo (-4 y +4 días)")
    st.caption("Revisa cómo están tus otros empleados para evitar huecos al hacer este cambio.")
    
    df_malla['Fecha_str'] = pd.to_datetime(df_malla['Fecha']).dt.strftime('%Y-%m-%d')
    df_v = df_malla[(df_malla['Fecha_str'] >= ini_v) & (df_malla['Fecha_str'] <= fin_v)].copy()
    df_v = df_v[~df_v['Sujeto'].str.contains("PENDIENTE", na=False)] # Filtramos las alertas de la vista
    
    if not df_v.empty:
        piv_v = df_v.pivot(index="Sujeto", columns="Fecha_str", values="Turno").fillna("DESCANSO")
        st.dataframe(style_malla_green(piv_v), use_container_width=True)

    st.write("---")
    st.markdown(f"#### 👥 Estado de Cobertura el día {fecha_solicitada}")
    df_dia = df_malla[df_malla['Fecha_str'] == fecha_solicitada]
    if not df_dia.empty:
        resumen = df_dia['Turno'].value_counts().reset_index()
        resumen.columns = ['Turno', 'Personal Asignado']
        st.dataframe(resumen.set_index('Turno').T, use_container_width=True)

    st.write("---")
    nuevo_turno = st.selectbox("🆕 Selecciona el Nuevo Turno a Asignar:", opciones_turnos + ["DESCANSO", "COMPENSADO", "SOPORTE"], index=0)
    
    if st.button("🔄 Aplicar y Sobrescribir Turno", type="primary"):
        st.session_state.green_manual[(sujeto_sel, fecha_solicitada)] = nuevo_turno
        st.success("¡Ajuste aplicado exitosamente! Cierra esta ventana y vuelve a previsualizar la malla.")
        st.rerun()

def generar_malla_green(inicio, fin, sujetos, dict_grupos, t_nombres_lv, t_nombres_sd, df_q_lv, df_q_sd, descansos_ini, conceder_comp, tipo_ciclo, tipo_rotacion, accion_sob, mod_descanso):
    filas, deudas = [], {s: 0 for s in sujetos}

    def get_quota(turno, is_weekend, grupo=None):
        df_q = df_q_sd if is_weekend else df_q_lv
        if df_q.empty or turno not in df_q["Turno"].values: return 0
        row = df_q[df_q["Turno"] == turno]
        if "Total Requerido" in df_q.columns: return int(row["Total Requerido"].values[0])
        return int(row[grupo].values[0]) if grupo in df_q.columns else 0

    for fecha in pd.date_range(inicio, fin):
        dia_n, sem = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1]
        delta_meses = (fecha.year - inicio.year) * 12 + (fecha.month - inicio.month)
        is_weekend, fecha_str = fecha.weekday() >= 5, fecha.strftime('%Y-%m-%d')

        desp = delta_meses if tipo_ciclo == "Mensual" else (delta_meses // 3 if tipo_ciclo == "Trimestral" else 0)
        d_rot = sem if tipo_rotacion == "Semanal" else (sem // 2 if tipo_rotacion == "Quincenal" else (delta_meses if tipo_rotacion == "Mensual" else 0))

        # 🌟 NUEVA LÓGICA: SABATINO/DOMINICAL CON EQUILIBRIO MATEMÁTICO
        d_vivos = {}
        for idx_s, s in enumerate(sujetos):
            if "Sabatino" in mod_descanso: 
                # Esto garantiza que la mitad del grupo descansa sábado y la otra domingo, y rotan la siguiente semana.
                d_vivos[s] = "Domingo" if (sem + idx_s) % 2 != 0 else "Sábado"
            else: 
                d_vivos[s] = DIAS_ES[(DIAS_ES.index(descansos_ini[s]) + desp) % 7]

        turnos_hoy = t_nombres_sd if is_weekend else t_nombres_lv
        deseados = {s: turnos_hoy[(idx_s + d_rot) % len(turnos_hoy)] for idx_s, s in enumerate(sujetos)} if turnos_hoy else {}
        asig = {s: "DESCANSO" for s, d in d_vivos.items() if d == dia_n}
        
        # 🌟 CAUSACIÓN DEL COMPENSATORIO POR LEY
        if dia_n == "Domingo" and conceder_comp:
            for s in [x for x in sujetos if x not in asig]: deudas[s] += 1
        
        # 🌟 DISTRIBUCIÓN DETERMINISTA DEL COMPENSATORIO EN LA SEMANA (L-V)
        if not is_weekend and conceder_comp:
            s_deuda = [s for s, d in deudas.items() if d > 0 and s not in asig]
            dia_idx = fecha.weekday()
            for s in s_deuda:
                target_day = (len(str(s)) + sem) % 5 # Fórmula para dispersarlos de Lunes a Viernes
                if dia_idx == target_day or dia_idx == 4: # El viernes obliga a cobrarlo si no lo tomó antes
                    asig[s] = "COMPENSADO"
                    deudas[s] -= 1

        activos = [s for s in sujetos if s not in asig]
        t_asig = {}

        if turnos_hoy:
            if "Total Requerido" in (df_q_sd.columns if is_weekend else df_q_lv.columns):
                for t_name in turnos_hoy:
                    req, asignados = get_quota(t_name, is_weekend), 0
                    for s in [s for s in activos if deseados[s] == t_name]:
                        if asignados < req: t_asig[s] = t_name; activos.remove(s); asignados += 1
                    while asignados < req and activos: s = activos.pop(0); t_asig[s] = t_name; asignados += 1
                    if asignados < req:
                        for lst in [[s for s, t in asig.items() if t == "COMPENSADO"], [s for s, t in asig.items() if t == "DESCANSO"]]:
                            while asignados < req and lst: s = lst.pop(0); del asig[s]; deudas[s] += 1; t_asig[s] = t_name; asignados += 1
                    if asignados < req: filas.append({"Fecha": fecha, "Sujeto": f"⚠️ PENDIENTE CUBRIR (Faltan {req - asignados})", "Grupo": "🚨 ALERTA", "Turno": t_name})
            else:
                for t_name in turnos_hoy:
                    for g in list(set(dict_grupos.values())):
                        req_g = get_quota(t_name, is_weekend, g)
                        if req_g == 0: continue
                        asignados, pool_g = 0, [s for s in activos if dict_grupos[s] == g]
                        for s in [s for s in pool_g if deseados[s] == t_name]:
                            if asignados < req_g: t_asig[s] = t_name; activos.remove(s); asignados += 1
                        while asignados < req_g and pool_g: s = pool_g.pop(0); activos.remove(s); t_asig[s] = t_name; asignados += 1
                        if asignados < req_g:
                            for lst in [[s for s, t in asig.items() if t == "COMPENSADO" and dict_grupos[s] == g], [s for s, t in asig.items() if t == "DESCANSO" and dict_grupos[s] == g]]:
                                while asignados < req_g and lst: s = lst.pop(0); del asig[s]; deudas[s] += 1; t_asig[s] = t_name; asignados += 1
                        if asignados < req_g: filas.append({"Fecha": fecha, "Sujeto": f"⚠️ PENDIENTE CUBRIR (Faltan {req_g - asignados})", "Grupo": g, "Turno": t_name})

        for s in activos: t_asig[s] = "DESCANSO" if accion_sob == "Descansar" else "SOPORTE"
        
        # Validación extra de deudas
        if dia_n == "Domingo" and conceder_comp:
            for s in [s for s, t in t_asig.items() if t not in ["DESCANSO", "COMPENSADO"]]: deudas[s] += 1
            
        for s, t in t_asig.items(): asig[s] = t
        
        for s in sujetos: 
            final = asig.get(s, "DESCANSO")
            if "green_manual" in st.session_state and (s, fecha_str) in st.session_state.green_manual:
                final = st.session_state.green_manual[(s, fecha_str)]
            filas.append({"Fecha": fecha, "Sujeto": s, "Grupo": dict_grupos[s], "Turno": final})

    return pd.DataFrame(filas)

def generar_reporte_green(df_final, config_h, df_base, descansos_ini, mod_descanso, modo_prog):
    filas = []
    df_reales = df_final[~df_final['Sujeto'].str.contains("PENDIENTE", na=False)].copy()
    df_reales['Fecha'] = pd.to_datetime(df_reales['Fecha'])
    
    for _, row in df_base.iterrows():
        # 🌟 ESCUDO DE SEGURIDAD PARA LA SEDE
        n = row['Nombre']
        c = row['Cargo']
        sed = row.get('Sede', 'N/A') # Si no existe la Sede, pone N/A
        ced = row.get('Cedula', 'N/A')
        grp = row['EquipoAsignado']
        
        sujeto_b = grp if "Grupos" in modo_prog else n
        df_sub = df_reales[df_reales['Sujeto'] == sujeto_b]
        
        for _, m in df_sub.iterrows():
            t, f = m['Turno'], m['Fecha']
            
            if "green_manual" in st.session_state and (sujeto_b, f.strftime('%Y-%m-%d')) in st.session_state.green_manual:
                t = st.session_state.green_manual[(sujeto_b, f.strftime('%Y-%m-%d'))]

            info = config_h.get(t, {"Inicio": "OFF", "Fin": "OFF", "Alm": False})
            hp, he, hn = calcular_metricas_reforma(info["Inicio"], info["Fin"])
            if info.get("Alm", False) and hp > 0: hp, he = max(0.0, hp - 1.0), max(0.0, hp - 7.0)
            
            dia_asignado = "Sabatino/Dominical" if "Sabatino" in mod_descanso else descansos_ini.get(sujeto_b, "N/A")

            filas.append({
                "Fecha": f.strftime('%Y-%m-%d'), "Nombre": n, "Equipo": grp, "Cargo": c, "Sede": sed,
                "Día Descanso Base": dia_asignado, "Turno realizado": t,
                "Entrada": info["Inicio"], "Salida": info["Fin"],
                "Hrs Prog": hp, "Hrs Extras": he, "Recargos Noc": hn,
                "Semana": f.isocalendar()[1]
            })
    return pd.DataFrame(filas)

# =========================================================
# 6. MÓDULO PRINCIPAL: MALLAS GREENMOVIL
# =========================================================
def pantalla_mallas_green():
    if "green_manual" not in st.session_state: st.session_state.green_manual = {}
    
    st.markdown("## 📅 Motor de Mallas y Nómina (Greenmovil)")
    
    try: df_activos = pd.read_sql("SELECT * FROM green_personal_activo", engine_local)
    except: df_activos = pd.DataFrame()
    
    if df_activos.empty:
        st.warning("⚠️ Ve a la pestaña 'Personal', conéctate al Data Warehouse y extrae tu personal primero.")
        return

    c_cargo, c_hora = st.columns(2)
    cargo_sel = c_cargo.selectbox("🎯 Filtrar y Programar por Cargo:", df_activos['Cargo'].unique())
    valor_hora = c_hora.number_input("💰 Valor Hora Ordinaria Proyectada ($):", min_value=0, value=6500, step=500, help="Sirve para proyectar el costo de nómina.")
    
    df_cargo = df_activos[df_activos['Cargo'] == cargo_sel].copy()

    st.write("---")
    st.markdown(f"### 🏗️ Conformación de Equipos para {cargo_sel}")
    
    # 🌟 CREACIÓN DE COLUMNAS FANTASMA POR SEGURIDAD
    if 'EquipoAsignado' not in df_cargo.columns: df_cargo['EquipoAsignado'] = "Grupo Único"
    if 'Sede' not in df_cargo.columns: df_cargo['Sede'] = "N/A"
    if 'Email' not in df_cargo.columns: df_cargo['Email'] = ""
        
    df_cargo_edit = st.data_editor(
        df_cargo[['Cedula', 'Nombre', 'Cargo', 'Sede', 'Email', 'EquipoAsignado']],
        column_config={"EquipoAsignado": st.column_config.TextColumn("🏷️ Nombre del Equipo", required=True)},
        use_container_width=True, hide_index=True, key=f"editor_eq_{cargo_sel}"
    )

    modo_prog = st.radio("🎯 Nivel de Asignación:", ["Por Individuo (Rotación y descanso propio)", "Por Grupos (El equipo hereda turnos)"])
    sujetos = df_cargo_edit['EquipoAsignado'].unique().tolist() if "Grupos" in modo_prog else df_cargo_edit['Nombre'].tolist()
    dict_grupos = dict(zip(df_cargo_edit['Nombre'], df_cargo_edit['EquipoAsignado']))
    grupos_unicos = df_cargo_edit['EquipoAsignado'].unique().tolist()

    st.write("---")
    st.markdown("### ⚙️ Parametrizador de Turnos Desacoplados")
    c_tlv, c_tsd = st.columns(2)
    num_t_lv = c_tlv.number_input("Cantidad de Turnos (L-V):", 0, 18, 2)
    num_t_sd = c_tsd.number_input("Cantidad de Turnos (S-D):", 0, 18, 1)

    st.markdown("**1. Configura Horarios (L-V)**")
    df_t_lv_base = pd.DataFrame({"Turno": [f"Turno LV {i+1}" for i in range(num_t_lv)], "Inicio": ["08:00"]*num_t_lv, "Fin": ["17:00"]*num_t_lv, "Descuenta Almuerzo": [True]*num_t_lv})
    df_t_lv = st.data_editor(df_t_lv_base, hide_index=True, key="dt_lv", use_container_width=True) if num_t_lv > 0 else pd.DataFrame()

    st.markdown("**2. Configura Horarios Especiales (S-D)**")
    df_t_sd_base = pd.DataFrame({"Turno": [f"Turno FDS {i+1}" for i in range(num_t_sd)], "Inicio": ["08:00"]*num_t_sd, "Fin": ["14:00"]*num_t_sd, "Descuenta Almuerzo": [False]*num_t_sd})
    df_t_sd = st.data_editor(df_t_sd_base, hide_index=True, key="dt_sd", use_container_width=True) if num_t_sd > 0 else pd.DataFrame()

    st.write("---")
    st.markdown("### 📊 Matriz de Requerimientos (Cuotas)")
    modo_cuotas = st.radio("Nivel de Asignación de Cuotas:", ["Global (Requisito total)", "Por Equipos (Requisito específico por equipo)"])
    cols_q = ["Turno"] + (grupos_unicos if "Equipos" in modo_cuotas else ["Total Requerido"])
    
    st.markdown("**Cuotas Lunes a Viernes:**")
    df_q_lv_base = pd.DataFrame(columns=cols_q)
    if not df_t_lv.empty:
        df_q_lv_base["Turno"] = df_t_lv["Turno"]
        for c in cols_q[1:]: df_q_lv_base[c] = 1
    df_q_lv = st.data_editor(df_q_lv_base, hide_index=True, key="dq_lv", use_container_width=True) if not df_t_lv.empty else pd.DataFrame()

    st.markdown("**Cuotas Sábado y Domingo:**")
    df_q_sd_base = pd.DataFrame(columns=cols_q)
    if not df_t_sd.empty:
        df_q_sd_base["Turno"] = df_t_sd["Turno"]
        for c in cols_q[1:]: df_q_sd_base[c] = 1
    df_q_sd = st.data_editor(df_q_sd_base, hide_index=True, key="dq_sd", use_container_width=True) if not df_t_sd.empty else pd.DataFrame()

    config_h, turnos_totales = {}, []
    if not df_t_lv.empty:
        turnos_totales.extend(df_t_lv["Turno"].tolist())
        for _, r in df_t_lv.iterrows(): config_h[r["Turno"]] = {"Inicio": r["Inicio"], "Fin": r["Fin"], "Alm": r["Descuenta Almuerzo"]}
    if not df_t_sd.empty:
        turnos_totales.extend(df_t_sd["Turno"].tolist())
        for _, r in df_t_sd.iterrows(): config_h[r["Turno"]] = {"Inicio": r["Inicio"], "Fin": r["Fin"], "Alm": r["Descuenta Almuerzo"]}

    st.write("---")
    st.markdown("### 📅 Estrategia de Descanso de Ley y Rotación")
    c_r1, c_r2, c_r3 = st.columns(3)
    sob = c_r1.radio("Acción Personal Sobrante:", ["Descansar", "Turno Soporte"])
    comp = c_r2.checkbox("⚖️ Pagar Domingos (Compensatorio)", True)
    c_rot = c_r3.selectbox("🔄 Rotación de Turnos:", ["Semanal", "Quincenal", "Mensual", "Turno Fijo"])
    
    mod_descanso = st.radio("Modalidad de descanso:", ["Día Fijo", "Rotación Sabatino/Dominical (Turno Inteligente)"])
    c_ciclo = "Fijo"
    desc_data = {}
    
    if "Día Fijo" in mod_descanso:
        c_ciclo = st.selectbox("🔄 Desplazamiento del Día Fijo:", ["Fijo sin rotación", "Mensual", "Trimestral"])
        cols_d = st.columns(4)
        for idx, s in enumerate(sujetos): desc_data[s] = cols_d[idx % 4].selectbox(s, DIAS_ES, index=6, key=f"gdesc_{s}")
    else:
        st.success("✅ **Modo Sabatino/Dominical Activado:** El sistema alternará los descansos automáticamente.")
        for s in sujetos: desc_data[s] = "Domingo" 

    config_h["SOPORTE"] = {"Inicio": "08:00", "Fin": "17:00", "Alm": True} if sob == "Turno Soporte" else {"Inicio": "OFF", "Fin": "OFF", "Alm": False}
    config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF", "Alm": False}

    st.markdown("---")
    ci, cf = st.columns(2)
    inicio = ci.date_input("Inicio Malla", date(2026, 7, 1), key="i_g")
    fin = cf.date_input("Fin Malla", date(2026, 7, 31), key="f_g")

    if st.button("👁️ PREVISUALIZAR MALLA GREENMOVIL", type="primary"):
        t_lv_list = df_t_lv["Turno"].tolist() if not df_t_lv.empty else []
        t_sd_list = df_t_sd["Turno"].tolist() if not df_t_sd.empty else []
        st.session_state.green_malla = generar_malla_green(inicio, fin, sujetos, dict_grupos, t_lv_list, t_sd_list, df_q_lv, df_q_sd, desc_data, comp, c_ciclo, c_rot, sob, mod_descanso)

    if 'green_malla' in st.session_state and not st.session_state.green_malla.empty:
        t_lv_list = df_t_lv["Turno"].tolist() if not df_t_lv.empty else []
        t_sd_list = df_t_sd["Turno"].tolist() if not df_t_sd.empty else []
        df_fin = generar_malla_green(inicio, fin, sujetos, dict_grupos, t_lv_list, t_sd_list, df_q_lv, df_q_sd, desc_data, comp, c_ciclo, c_rot, sob, mod_descanso)
        st.session_state.green_malla = df_fin
        
        t_malla = f"green_malla_{cargo_sel.lower().replace(' ', '_')}"
        t_nom = f"green_nomina_{cargo_sel.lower().replace(' ', '_')}"

        st.write("---")
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("💾 1. GUARDAR EN BD Y EXPORTAR"):
                if guardar_malla_historico(df_fin, t_malla, inicio, fin):
                    guardar_malla_historico(generar_reporte_green(df_fin, config_h, df_cargo_edit, desc_data, mod_descanso, modo_prog), t_nom, inicio, fin)
                    st.success("✅ ¡Guardado en PostgreSQL exitosamente!")
        with c_btn2:
            with st.popover("📩 2. Enviar Malla por Correo"):
                st.info("Ingresa tu credencial SMTP (Ej: Contraseña de App de Gmail)")
                remitente = st.text_input("Tu Correo Remitente", key="rm_g")
                pwd = st.text_input("Contraseña App", type="password", key="pw_g")
                if st.button("🚀 Enviar a Personal"):
                    if remitente and pwd:
                        with st.spinner("Conectando con el servidor..."):
                            df_rep = generar_reporte_green(df_fin, config_h, df_cargo_edit, desc_data, mod_descanso, modo_prog)
                            exito, msj = enviar_correos_masivos(df_rep, df_cargo_edit, f"{inicio.strftime('%B %Y')}", remitente, pwd)
                            if exito: st.success(msj)
                            else: st.error(msj)
                    else: st.warning("Completa las credenciales.")

        st.subheader("📋 Malla Operativa (Macro)")
        piv = df_fin.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        piv.columns = [p.strftime('%Y-%m-%d') for p in piv.columns]
        
        st.markdown(generar_html_imprimible(piv, f"Malla Operativa - {cargo_sel} - {inicio.strftime('%b %Y')}"), unsafe_allow_html=True)
        st.dataframe(style_malla_green(piv), use_container_width=True)

        # 🌟 NUEVO EDITOR CONTEXTUAL 
        st.write("---")
        with st.expander("🔍 Editor Visual Avanzado (Pop-up Interactivo)"):
            c_f1, c_f2 = st.columns(2)
            f_sel = c_f1.selectbox("📅 Seleccione la Fecha a auditar:", list(piv.columns))
            s_sel = c_f2.selectbox("👤 Seleccione la Entidad:", list(piv.index))
            if st.button("⚙️ Abrir Panel de Edición Contextual", use_container_width=True): 
                popup_forzar_green(f_sel, s_sel, turnos_totales, df_fin)

        st.subheader("📈 Auditoría, Nómina y Proyección de Costos")
        t1, t2, t3 = st.tabs(["📊 Dashboard Financiero", "📋 Reporte Nómina", "🔍 Auditoría de Huecos Operativos"])
        rep = generar_reporte_green(df_fin, config_h, df_cargo_edit, desc_data, mod_descanso, modo_prog)
        
        with t1:
            if not rep.empty:
                total_horas = rep['Hrs Prog'].sum()
                total_extras = rep['Hrs Extras'].sum()
                costo_proyectado = total_horas * valor_hora
                costo_extras = total_extras * (valor_hora * 1.25)
                
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric("💰 Costo Base Proyectado", f"${costo_proyectado:,.0f} COP")
                c_m2.metric("📈 Costo de Horas Extras", f"${costo_extras:,.0f} COP")
                c_m3.metric("⏱️ Índice de Trabajo (Hrs/Emp)", f"{(total_horas/len(df_cargo_edit)):.1f} h")
                
                rep['Costo ($)'] = (rep['Hrs Prog'] * valor_hora) + (rep['Hrs Extras'] * valor_hora * 1.25)
                st.bar_chart(rep.groupby("Nombre")['Costo ($)'].sum().reset_index(), x="Nombre", y="Costo ($)")

        with t2: st.dataframe(rep, use_container_width=True)
        with t3:
            df_huecos = df_fin[df_fin['Sujeto'].str.contains("PENDIENTE", na=False)]
            if not df_huecos.empty: st.error(f"🚨 Tienes {len(df_huecos)} huecos operativos.")
            st.dataframe(df_fin.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0), use_container_width=True)