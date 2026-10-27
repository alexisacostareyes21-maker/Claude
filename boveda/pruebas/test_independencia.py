"""Pruebas de los controles de independencia.

El caso central es el que la investigacion adversarial identifico como la prueba
irrefutable de copia: un umbral que no existe en la ventana de inscripcion de
ningun ensayo."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import Clase, Magnitud, parsear
from harness.hecho import Ancla, ClaseHecho, Hecho, Poblacion, TipoAncla
from harness.independencia import (
    HallazgoIndependencia, Justificacion, OrigenSeleccion, clave_de_orden,
    coincide_byte_a_byte, gradacion_ajena, orden_canonico, orden_es_derivado,
    reformular_como_ventana, revisar, revisar_gradacion, revisar_justificacion,
    umbral_sintetico,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def ancla_ventana(nct="NCT03036150", inf=25.0, sup=75.0, verificada=True):
    """Un ancla con la ventana de elegibilidad real del ensayo."""
    m = Magnitud(Clase.TFG, inf, "ml/min/1.73m2", ic_inf=inf, ic_sup=sup)
    return Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador=nct, magnitud=m,
                 fecha_consulta="2026-03-15", verificada=verificada)


def hecho_umbral(valor, anclas=None, clase=ClaseHecho.UMBRAL):
    h = Hecho(enunciado=f"Iniciar un iSGLT2 si el eGFR es mayor o igual a {valor:g}.",
              clase=clase, poblacion=Poblacion(condicion="ERC con albuminuria"),
              magnitud=Magnitud(Clase.TFG, valor, "ml/min/1.73m2"),
              intervencion="iSGLT2", desenlace="progresion renal",
              anclas=anclas if anclas is not None else [ancla_ventana()])
    h.diagnostico["justificacion"] = Justificacion(
        OrigenSeleccion.PERFIL_ENARM, "dominio de alto peso en el examen", 0.8).dict()
    return h


# ---------------------------------------------- el caso que mata al producto
def test_umbral_que_no_existe_en_ningun_ensayo():
    """CREDENCE inscribio 30-90, DAPA-CKD inscribio 25-75. El 20 solo existe en
    la guia, y por eso publicarlo es la prueba mas directa de la copia."""
    h = hecho_umbral(20.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    f = umbral_sintetico(h)
    ok(f is not None, "un umbral de 20 con una ventana de 25 a 75 debe detectarse")
    ok(f.codigo == "UMBRAL_SINTETICO", f"codigo: {f.codigo}")
    ok(f.gravedad == "alta", "es de gravedad alta: bloquea")
    ok("25" in f.detalle and "75" in f.detalle,
       f"el detalle debe mostrar lo que SI dice la fuente: {f.detalle}")


def test_umbral_que_si_esta_en_la_fuente_pasa():
    h = hecho_umbral(25.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    ok(umbral_sintetico(h) is None,
       "un umbral que coincide con el limite inferior de la ventana si es un dato")


def test_sin_tolerancia_relativa():
    """La tolerancia es justo lo que dejaria pasar un 20 como 25 'equivalente'."""
    h = hecho_umbral(24.9, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    ok(umbral_sintetico(h) is not None,
       "24.9 no es 25: aqui la pregunta no es equivalencia clinica sino procedencia")
    ok(not coincide_byte_a_byte(24.99, [ancla_ventana(inf=25.0)]),
       "coincide_byte_a_byte no debe tener tolerancia relativa")
    ok(coincide_byte_a_byte(25.0, [ancla_ventana(inf=25.0)]), "el valor exacto si coincide")


def test_ancla_sin_verificar_no_respalda_un_umbral():
    h = hecho_umbral(25.0, anclas=[ancla_ventana(inf=25.0, verificada=False)])
    ok(umbral_sintetico(h) is not None,
       "un ancla sin verificar no puede respaldar el umbral")


def test_umbral_sin_anclas():
    h = hecho_umbral(20.0, anclas=[])
    f = umbral_sintetico(h)
    ok(f is not None, "un umbral sin ninguna ancla es sintetico por definicion")
    ok("nada" in f.detalle, f"debe decir que no hay anclas: {f.detalle}")


def test_otras_clases_no_se_bloquean():
    """La regla aplica a umbrales y ventanas, no a tamanos de efecto: un HR
    legitimamente no coincide con nada de la ventana de elegibilidad."""
    h = Hecho("un iSGLT2 reduce la progresion", ClaseHecho.EFECTO,
              Poblacion("ERC"), magnitud=parsear("HR 0.61")[0],
              anclas=[ancla_ventana()])
    ok(umbral_sintetico(h) is None, "un hecho de clase EFECTO no pasa por esta regla")


# ---------------------------------------------- la reparacion
def test_reformular_como_ventana():
    h = hecho_umbral(20.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    reformular_como_ventana(h)
    ok(h.clase is ClaseHecho.CRITERIO, f"deja de ser un umbral: {h.clase}")
    ok(h.magnitud.valor == 25.0 and h.magnitud.valor_sup == 75.0,
       f"la magnitud pasa a ser la ventana real: {h.magnitud}")
    ok("NCT03036150" in h.enunciado, f"el enunciado debe citar el registro: {h.enunciado}")
    ok("no emite un umbral" in h.enunciado,
       f"debe declarar explicitamente que ORIONS no emite el umbral: {h.enunciado}")
    ok(umbral_sintetico(h) is None, "despues de reformular ya no debe detectarse")


def test_reformular_sin_ancla_no_inventa():
    h = hecho_umbral(20.0, anclas=[])
    reformular_como_ventana(h)
    ok(h.veredicto == "ROJO", "sin ancla no se puede reformular: va a revision")
    ok("no se puede reformular" in h.diagnostico["independencia"],
       f"debe explicarlo: {h.diagnostico['independencia']}")


# ---------------------------------------------- gradaciones
def test_detecta_gradaciones():
    casos = [
        "esta recomendacion tiene evidencia A",
        "clase I, nivel B de recomendacion",
        "nivel GRADE 1A para esta intervencion",
        "GRADE certeza moderada",
        "recomendacion fuerte a favor",
        "grado B segun el panel",
    ]
    for c in casos:
        ok(gradacion_ajena(c), f"debe detectar la gradacion en: {c!r}")

    limpios = [
        "en 4304 pacientes el desenlace renal compuesto se redujo",
        "el intervalo de confianza fue estrecho y el efecto consistente",
        "tres anclas independientes respaldan esta cifra",
    ]
    for c in limpios:
        ok(not gradacion_ajena(c), f"no debe marcar un texto propio: {c!r}")


def test_revisar_gradacion_bloquea():
    h = hecho_umbral(25.0)
    h.enunciado = "Iniciar un iSGLT2 en ERC con albuminuria (evidencia A)."
    f = revisar_gradacion(h)
    ok(f is not None and f.gravedad == "alta",
       "reproducir la gradacion de una guia debe bloquear")
    ok("campos mecanicos" in f.detalle,
       f"el detalle debe decir con que sustituirla: {f.detalle}")


# ---------------------------------------------- seleccion
def test_seleccion_sin_justificar():
    h = hecho_umbral(25.0)
    h.diagnostico.pop("justificacion")
    f = revisar_justificacion(h)
    ok(f is not None, "un hecho sin justificacion de inclusion debe marcarse")
    ok(f.codigo == "SELECCION_SIN_JUSTIFICAR", f"codigo: {f.codigo}")
    ok("107" in f.detalle, f"debe citar la base legal: {f.detalle}")


def test_seleccion_heredada_de_una_guia():
    for frase in ("porque la guia lo incluye", "segun la ADA es prioritario",
                  "la ESC lo recomienda en su seccion 7"):
        h = hecho_umbral(25.0)
        h.diagnostico["justificacion"] = {"origen": "perfil_enarm", "evidencia": frase}
        f = revisar_justificacion(h)
        ok(f is not None and f.codigo == "SELECCION_HEREDADA",
           f"debe detectar la justificacion heredada: {frase!r} -> {f}")
        ok(f.gravedad == "alta", "apelar a una guia para justificar la inclusion bloquea")


def test_justificacion_propia_pasa():
    h = hecho_umbral(25.0)
    for origen in OrigenSeleccion:
        h.diagnostico["justificacion"] = Justificacion(
            origen, "carga de enfermedad medida en ENSANUT", 0.7).dict()
        ok(revisar_justificacion(h) is None,
           f"una justificacion propia debe pasar: {origen.value}")


# ---------------------------------------------- disposicion
def mk(hr, ic=None, fecha="2026-01-01"):
    m = Magnitud(Clase.RAZON_RIESGO, hr)
    if ic:
        m.ic_inf, m.ic_sup = ic
    h = Hecho(f"efecto {hr}", ClaseHecho.EFECTO, Poblacion("x"),
              magnitud=m, intervencion=f"i{hr}", desenlace=f"d{hr}",
              anclas=[Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador=f"NCT{hr}",
                            magnitud=m, fecha_consulta=fecha, verificada=True)])
    h.diagnostico["justificacion"] = Justificacion(
        OrigenSeleccion.DENSIDAD_ANCLA, "hay registro con resultados", 0.5).dict()
    return h


def test_orden_por_magnitud_de_efecto():
    a, b, c = mk(0.61), mk(0.90), mk(0.40)
    orden = orden_canonico([a, b, c])
    ok([h.magnitud.valor for h in orden] == [0.40, 0.61, 0.90],
       f"debe ordenar por magnitud del efecto, de mayor a menor: "
       f"{[h.magnitud.valor for h in orden]}")


def test_desempate_por_precision():
    estrecho = mk(0.61, ic=(0.58, 0.64))
    ancho = mk(0.61, ic=(0.35, 0.95))
    orden = orden_canonico([ancho, estrecho])
    ok(orden[0] is estrecho,
       "a igual efecto gana el intervalo mas estrecho, que es el mas preciso")


def test_sin_intervalo_va_despues():
    con = mk(0.61, ic=(0.51, 0.72))
    sin = mk(0.61)
    orden = orden_canonico([sin, con])
    ok(orden[0] is con, "un hecho sin intervalo de confianza va despues, no antes")


def test_sin_magnitud_al_final():
    con = mk(0.61)
    sin = Hecho("sin cifra", ClaseHecho.SECUENCIA, Poblacion("x"))
    orden = orden_canonico([sin, con])
    ok(orden[0] is con, "los hechos sin magnitud van al final")


def test_orden_es_recomputable_y_probatorio():
    hs = [mk(0.40), mk(0.61), mk(0.90)]
    ok(orden_es_derivado(hs) is None,
       "un orden que coincide con el canonico se demuestra, no se alega")

    desordenado = [mk(0.90), mk(0.40), mk(0.61)]
    f = orden_es_derivado(desordenado)
    ok(f is not None, "un orden ajustado a mano debe marcarse")
    ok(f.codigo == "ORDEN_NO_DERIVADO", f"codigo: {f.codigo}")
    ok("posicion 0" in f.detalle, f"debe decir donde divergen: {f.detalle}")


def test_clave_de_orden_es_estable():
    h = mk(0.61, ic=(0.51, 0.72))
    ok(clave_de_orden(h) == clave_de_orden(h), "la clave debe ser deterministica")


# ---------------------------------------------- revision completa
def test_revisar_bloquea_lo_grave():
    bueno = mk(0.61, ic=(0.51, 0.72))
    malo = hecho_umbral(20.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    rep = revisar([bueno, malo])
    ok(len(rep.bloqueados) == 1, f"debe bloquear uno: {len(rep.bloqueados)}")
    ok(rep.bloqueados[0] is malo, "el bloqueado debe ser el del umbral sintetico")
    ok(malo.veredicto == "ROJO", f"el hecho bloqueado va a ROJO: {malo.veredicto}")
    ok("UMBRAL_SINTETICO" in malo.diagnostico["independencia_bloqueo"],
       "debe quedar el codigo del bloqueo en el hecho")
    ok(not rep.limpio, "el reporte no esta limpio si hay un hallazgo grave")
    ok(len(rep.publicables) == 1, "el bueno si es publicable")


def test_revisar_con_reparacion():
    malo = hecho_umbral(20.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    rep = revisar([malo], reparar=True)
    ok(not rep.bloqueados, f"al reparar no debe quedar bloqueado: {len(rep.bloqueados)}")
    ok(malo.clase is ClaseHecho.CRITERIO, "debe haberse reformulado como ventana")
    ok(rep.limpio, "tras la reparacion el reporte queda limpio")


def test_revisar_detecta_varios_problemas_en_un_hecho():
    h = hecho_umbral(20.0, anclas=[ancla_ventana(inf=25.0, sup=75.0)])
    h.enunciado = "Iniciar si eGFR >=20 (evidencia A)."
    h.diagnostico.pop("justificacion")
    rep = revisar([h])
    codigos = {x.codigo for x in rep.hallazgos}
    ok("UMBRAL_SINTETICO" in codigos, f"debe detectar el umbral: {codigos}")
    ok("GRADACION_AJENA" in codigos, f"debe detectar la gradacion: {codigos}")
    ok("SELECCION_SIN_JUSTIFICAR" in codigos, f"debe detectar la seleccion: {codigos}")


def test_reporte_serializable():
    rep = revisar([mk(0.61, ic=(0.51, 0.72))])
    d = rep.dict()
    ok("limpio" in d and "hallazgos" in d, f"el reporte debe serializarse: {list(d)}")


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
