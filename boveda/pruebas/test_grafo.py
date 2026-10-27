"""Pruebas del grafo de mecanismos."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import Magnitud, Clase, parsear
from harness.hecho import ClaseHecho, Hecho, Poblacion
from harness.grafo import Arista, Grafo, Nivel, Nodo, Signo, TipoContradiccion

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def mini():
    """Cadena de 4 nodos con dos signos negativos: neto positivo."""
    g = Grafo()
    a = g.agregar_nodo(Nodo("farmaco X", Nivel.FARMACO))
    b = g.agregar_nodo(Nodo("enzima Y", Nivel.MOLECULAR))
    c = g.agregar_nodo(Nodo("metabolito Z", Nivel.CELULAR))
    d = g.agregar_nodo(Nodo("desenlace W", Nivel.CLINICO))
    g.agregar_arista(Arista(a, b, Signo.DISMINUYE, confianza=0.9))
    g.agregar_arista(Arista(b, c, Signo.DISMINUYE, confianza=0.8))
    g.agregar_arista(Arista(c, d, Signo.AUMENTA, confianza=0.7))
    return g, a, b, c, d


def test_propagacion_de_signo():
    g, a, b, c, d = mini()
    r = g.mejor_ruta(a, d)
    ok(r is not None, "debe encontrar la ruta")
    ok(r.signo == 1, f"dos disminuye y un aumenta dan neto +1: {r.signo}")
    ok(len(r) == 3, f"la ruta debe tener 3 aristas: {len(r)}")


def test_confianza_es_el_eslabon_mas_debil():
    g, a, b, c, d = mini()
    r = g.mejor_ruta(a, d)
    ok(abs(r.confianza - 0.7) < 1e-9,
       f"la confianza de la ruta es la minima de sus aristas: {r.confianza}")


def test_rutas_multiples_y_orden():
    g, a, b, c, d = mini()
    # atajo directo
    g.agregar_arista(Arista(a, d, Signo.DISMINUYE, confianza=0.95))
    rs = g.rutas(a, d)
    ok(len(rs) == 2, f"deben existir 2 rutas: {len(rs)}")
    ok(len(rs[0]) == 1, "las rutas se devuelven de la mas corta a la mas larga")
    mejor = g.mejor_ruta(a, d)
    ok(len(mejor) == 1 and mejor.confianza == 0.95,
       "la mejor ruta es la mas confiable")


def test_no_revisita_nodos():
    g = Grafo()
    a = g.agregar_nodo(Nodo("a", Nivel.FARMACO))
    b = g.agregar_nodo(Nodo("b", Nivel.CELULAR))
    c = g.agregar_nodo(Nodo("c", Nivel.CLINICO))
    g.agregar_arista(Arista(a, b, Signo.AUMENTA))
    g.agregar_arista(Arista(b, a, Signo.AUMENTA))   # ciclo
    g.agregar_arista(Arista(b, c, Signo.AUMENTA))
    rs = g.rutas(a, c)
    ok(len(rs) == 1, f"el ciclo no debe multiplicar las rutas simples: {len(rs)}")


def test_ciclo_negativo_es_normal_y_positivo_se_marca():
    g = Grafo()
    a = g.agregar_nodo(Nodo("renina", Nivel.MOLECULAR))
    b = g.agregar_nodo(Nodo("angiotensina II", Nivel.MOLECULAR))
    g.agregar_arista(Arista(a, b, Signo.AUMENTA))
    g.agregar_arista(Arista(b, a, Signo.DISMINUYE))   # retroalimentacion negativa
    ciclos = g.ciclos()
    ok(len(ciclos) >= 1, "debe encontrar el ciclo")
    ok(all(c.signo < 0 for c in ciclos), "la retroalimentacion negativa tiene signo -1")
    contras = g.contradicciones()
    ok(not [c for c in contras if c.tipo is TipoContradiccion.CICLO_POSITIVO],
       "un ciclo estabilizador no es una contradiccion")

    g2 = Grafo()
    x = g2.agregar_nodo(Nodo("x", Nivel.MOLECULAR))
    y = g2.agregar_nodo(Nodo("y", Nivel.MOLECULAR))
    g2.agregar_arista(Arista(x, y, Signo.AUMENTA))
    g2.agregar_arista(Arista(y, x, Signo.AUMENTA))    # amplificador
    contras2 = g2.contradicciones()
    ok(any(c.tipo is TipoContradiccion.CICLO_POSITIVO for c in contras2),
       f"un ciclo amplificador debe marcarse: {[c.tipo for c in contras2]}")


def test_aristas_opuestas_mismo_contexto():
    g = Grafo()
    a = g.agregar_nodo(Nodo("a", Nivel.FARMACO))
    b = g.agregar_nodo(Nodo("b", Nivel.CLINICO))
    g.agregar_arista(Arista(a, b, Signo.AUMENTA, contexto="ERC"))
    g.agregar_arista(Arista(a, b, Signo.DISMINUYE, contexto="ERC"))
    contras = g.contradicciones()
    ok(any(c.tipo is TipoContradiccion.ARISTAS_OPUESTAS for c in contras),
       "dos aristas de signo opuesto en el mismo contexto son contradiccion")
    ok(any(c.gravedad == "alta" for c in contras), "debe ser de gravedad alta")

    # el mismo par con contextos distintos NO es contradiccion: es matiz clinico
    g2 = Grafo()
    a2 = g2.agregar_nodo(Nodo("a", Nivel.FARMACO))
    b2 = g2.agregar_nodo(Nodo("b", Nivel.CLINICO))
    g2.agregar_arista(Arista(a2, b2, Signo.AUMENTA, contexto="ERC"))
    g2.agregar_arista(Arista(a2, b2, Signo.DISMINUYE, contexto="falla cardiaca"))
    ok(not [c for c in g2.contradicciones() if c.tipo is TipoContradiccion.ARISTAS_OPUESTAS],
       "contextos distintos permiten signos distintos")


def test_hecho_contra_ruta():
    g = Grafo()
    f = g.agregar_nodo(Nodo("farmaco X", Nivel.FARMACO))
    d = g.agregar_nodo(Nodo("desenlace W", Nivel.CLINICO))
    g.agregar_arista(Arista(f, d, Signo.AUMENTA, confianza=0.9))   # predice dano

    h = Hecho(
        enunciado="el farmaco X reduce el desenlace W",
        clase=ClaseHecho.EFECTO,
        poblacion=Poblacion(condicion="cualquiera"),
        magnitud=parsear("HR 0.61")[0],     # protector: signo -1
        intervencion="farmaco X",
        desenlace="desenlace W",
    )
    contras = g.contradicciones([h])
    ok(any(c.tipo is TipoContradiccion.HECHO_CONTRA_RUTA for c in contras),
       f"un HR protector contra una ruta de dano es contradiccion: {[c.tipo for c in contras]}")

    # con el signo correcto no hay contradiccion
    list(g.aristas.values())[0].signo = Signo.DISMINUYE
    ok(not [c for c in g.contradicciones([h]) if c.tipo is TipoContradiccion.HECHO_CONTRA_RUTA],
       "con el signo correcto no debe haber contradiccion")


def test_hecho_neutro_no_dispara():
    g = Grafo()
    f = g.agregar_nodo(Nodo("farmaco X", Nivel.FARMACO))
    d = g.agregar_nodo(Nodo("desenlace W", Nivel.CLINICO))
    g.agregar_arista(Arista(f, d, Signo.AUMENTA))
    h = Hecho("neutro", ClaseHecho.EFECTO, Poblacion("x"),
              magnitud=Magnitud(Clase.RAZON_RIESGO, 1.00),
              intervencion="farmaco X", desenlace="desenlace W")
    ok(not [c for c in g.contradicciones([h]) if c.tipo is TipoContradiccion.HECHO_CONTRA_RUTA],
       "un HR de 1.00 no afirma direccion: no debe disparar contradiccion")


def test_sinonimos_resuelven_nodo():
    g = Grafo()
    g.agregar_nodo(Nodo("inhibicion de SGLT2", Nivel.FARMACO,
                        sinonimos=["dapagliflozina", "iSGLT2"]))
    ok(g.nodo_por_nombre("dapagliflozina") is not None, "debe resolver por sinonimo")
    ok(g.nodo_por_nombre("DAPAGLIFLOZINA") is not None, "debe ser insensible a mayusculas")
    ok(g.nodo_por_nombre("metformina") is None, "no debe inventar nodos")


def test_distractores_del_mismo_nivel():
    g = Grafo()
    f = g.agregar_nodo(Nodo("farmaco", Nivel.FARMACO))
    buenos = [g.agregar_nodo(Nodo(f"celular {i}", Nivel.CELULAR)) for i in range(4)]
    d = g.agregar_nodo(Nodo("desenlace", Nivel.CLINICO))
    g.agregar_arista(Arista(f, buenos[0], Signo.AUMENTA))
    g.agregar_arista(Arista(buenos[0], d, Signo.AUMENTA))
    for b in buenos[1:]:
        g.agregar_arista(Arista(f, b, Signo.AUMENTA))

    r = g.mejor_ruta(f, d)
    ds = g.distractores(buenos[0], r, n=3)
    ok(len(ds) == 3, f"debe devolver 3 distractores: {ds}")
    ok("celular 0" not in ds, "el nodo correcto no puede ser su propio distractor")
    ok(all(x.startswith("celular") for x in ds),
       f"los distractores deben ser del mismo nivel de organizacion: {ds}")


def test_pregunta_de_ruta():
    g = Grafo()
    f = g.agregar_nodo(Nodo("farmaco", Nivel.FARMACO))
    m = g.agregar_nodo(Nodo("paso medio", Nivel.CELULAR))
    for i in range(3):
        g.agregar_nodo(Nodo(f"vecino {i}", Nivel.CELULAR))
    d = g.agregar_nodo(Nodo("desenlace", Nivel.CLINICO))
    g.agregar_arista(Arista(f, m, Signo.AUMENTA, anclas=["NCT1"]))
    g.agregar_arista(Arista(m, d, Signo.DISMINUYE, anclas=["PMC2"]))

    r = g.mejor_ruta(f, d)
    q = g.pregunta_de_ruta(r, posicion=1)
    ok(q is not None, "debe generar la pregunta")
    ok(q["correcta"] == "paso medio", f"la correcta debe ser el nodo oculto: {q}")
    ok(len(q["opciones"]) == 4, f"una correcta y tres distractores: {q['opciones']}")
    ok(q["opciones"][0] == "paso medio", "la correcta va primero antes de barajar")
    ok(1 <= q["dificultad"] <= 5, f"dificultad en rango: {q['dificultad']}")
    ok(set(q["anclas"]) == {"NCT1", "PMC2"},
       f"la pregunta hereda las anclas de sus aristas: {q['anclas']}")
    ok("aumenta" in q["enunciado"] and "disminuye" in q["enunciado"],
       f"el enunciado refleja los signos: {q['enunciado']}")

    ok(g.pregunta_de_ruta(r, posicion=0) is None, "no se puede ocultar el origen")
    ok(g.pregunta_de_ruta(r, posicion=2) is None, "no se puede ocultar el destino")


def test_arista_a_nodo_inexistente_falla():
    g = Grafo()
    a = g.agregar_nodo(Nodo("a", Nivel.FARMACO))
    try:
        g.agregar_arista(Arista(a, "Nfantasma", Signo.AUMENTA))
        ok(False, "debe rechazar una arista a un nodo que no existe")
    except KeyError:
        ok(True, "")


def test_explicar_es_legible():
    g, a, b, c, d = mini()
    txt = g.explicar(g.mejor_ruta(a, d))
    ok("farmaco X" in txt and "desenlace W" in txt, "la explicacion nombra los extremos")
    ok("Efecto neto" in txt, "la explicacion cierra con el efecto neto")
    ok(txt.count("\n") == 3, f"una linea por arista mas el neto: {txt.count(chr(10))}")


def main():
    for t in [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]:
        try:
            t()
        except Exception as e:
            FALLOS.append(f"{t.__name__} lanzo {type(e).__name__}: {e}")
    print(f"\n{PASES} aserciones pasaron, {len(FALLOS)} fallaron\n")
    for f in FALLOS:
        print("  FALLO:", f)
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
