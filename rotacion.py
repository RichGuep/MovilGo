def rotar_grupos(grupos, semana):

    if semana % 2 == 0:
        return grupos[:2], grupos[2:]
    else:
        return grupos[2:], grupos[:2]
