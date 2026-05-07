import pandas as pd
import holidays
from datetime import datetime, timedelta

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]:
        return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    # Regla de Oro: Prohibido saltar hacia atrás (Ej: T3 a T1) sin descanso
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def generar_malla_balanceada(f_ini, f_fin, estado_ayer, descansos_config):
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    f_ini_dt = datetime.combine(f_ini, datetime.min.time())
    f_fin_dt = datetime.combine(f_fin, datetime.min.time())
    
    lista_fechas = [f_ini_dt + timedelta(days=x) for x in range((f_fin_dt - f_ini_dt).days + 1)]
    resultados = []
    
    mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
    mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
    deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
    
    # ESTADÍSTICAS PARA AUDITORÍA DE EQUILIBRIO
    stats_mensuales = {g: {"T1": 0, "T2": 0, "T3": 0, "DESC": 0} for g in grupos_n}
    
    co_h = holidays.Colombia(years=[f_ini_dt.year, f_fin_dt.year])

    for fecha_dt in lista_fechas:
        dia_idx = fecha_dt.weekday()
        es_fest = fecha_dt in co_h
        col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

        # 1. Aplicar día de descanso fijo configurado
        libranzas_hoy = [g for g, d in descansos_config.items() if d == dia_idx]
        activos = [g for g in grupos_n if g not in libranzas_hoy]
        
        turnos_hoy = {}
        
        # 2. ASIGNACIÓN PRIORITARIA POR CARGA (Equilibrio)
        # Primero asignamos T3 (el más pesado) al que menos noches lleve
        for t_req in ["T3", "T2", "T1"]:
            # Candidatos que: están activos, no tienen turno hoy y es saludable
            candidatos = [
                g for g in activos 
                if g not in turnos_hoy and es_cambio_saludable(mem_t[g], t_req)
            ]
            
            # Refinamiento de candidatos: Evitar que alguien supere 6 noches
            if t_req == "T3":
                candidatos = [g for g in candidatos if mem_n[g] < 6]

            if candidatos:
                # REGLA DE EQUILIBRIO: Elegir al que menos veces haya hecho este turno en el periodo
                elegido = min(candidatos, key=lambda x: stats_mensuales[x][t_req])
                turnos_hoy[elegido] = t_req
                stats_mensuales[elegido][t_req] += 1
            else:
                # RUTINA DE ESCAPE: Si nadie puede hacer el turno por salud, 
                # se fuerza un COMP para resetear el ciclo
                pass

        # 3. GESTIÓN DEL GRUPO SOBRANTE (Compensatorio)
        for g in grupos_n:
            if g in libranzas_hoy:
                t_f = "DESC"
                stats_mensuales[g]["DESC"] += 1
            elif g in turnos_hoy:
                t_f = turnos_hoy[g]
            else:
                # El grupo que sobra hoy gana un Compensatorio (descanso extra)
                t_f = "COMP"
                stats_mensuales[g]["DESC"] += 1
            
            n_a = mem_n[g] + 1 if t_f == "T3" else 0
            
            resultados.append({
                "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, 
                "Deuda_Compensatorio": deudas[g]
            })
            
            mem_t[g] = t_f
            mem_n[g] = n_a

    return pd.DataFrame(resultados)
