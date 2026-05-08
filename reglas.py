def obtener_descanso(dia_semana, descansos):

    for grupo, d in descansos.items():
        if d == dia_semana:
            return grupo

    return None


def asignar_tr(grupo_descanso, personas, tr_counter):

    grupo_personas = [
        p for p in personas if p["grupo"] == grupo_descanso
    ]

    if not grupo_personas:
        return None

    seleccion = min(
        grupo_personas,
        key=lambda p: tr_counter.get(p["nombre"], 0)
    )

    tr_counter[seleccion["nombre"]] = tr_counter.get(seleccion["nombre"], 0) + 1

    return {
        "Fecha": None,
        "Grupo": grupo_descanso,
        "Turno": "TR",
        "Persona_TR": seleccion["nombre"]
    }
