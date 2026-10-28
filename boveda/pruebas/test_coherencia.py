"""Pruebas del cierre aritmetico.

La calibracion NO es arbitraria: los umbrales se fijaron midiendo cinco razones
reales ancladas en este proyecto, y las pruebas las usan como casos positivos."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import Clase, Magnitud, parsear
from harness.coherencia import (
    Cierre, Observacion, asimetria_log, error_estandar_log, eventos_que_implica,
    eventos_que_implican_n_y_tasa, plan_de_preguntas, verificar,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def R(v, lo=None, hi=None):
    return Magnitud(Clase.RAZON_RIESGO, v, ic_inf=lo, ic_sup=hi)


def codigos(rep):
    return {f.codigo for f in rep.fallos}


# ============================================================ la validacion clave
def test_el_intervalo_predice_los_eventos_de_dapa_ckd():
    """El resultado que sostiene todo el modulo. De HR 0.61 (0.51-0.72) SOLO, sin
    ninguna fuente externa, la formula predice 517 eventos. DAPA-CKD publico 509.
    Error del 1.5%. El intervalo de confianza CODIFICA el numero de eventos."""
    d = eventos_que_implica(R(0.61, 0.51, 0.72))
    ok(d is not None, "debe poder calcularlo")
    ok(abs(d - 509) / 509 < 0.05,
       f"debe predecir los ~509 eventos reales de DAPA-CKD con menos de 5% de error: "
       f"predijo {d:.0f}")


def test_las_cinco_cifras_reales_cierran():
    """Casos positivos: cifras reales ancladas contra PMC en este proyecto.
    Si alguna fallara, el umbral estaria mal calibrado y el modulo seria inutil
    por falsos positivos."""
    reales = [
        ("DAPA-CKD renal", 0.61, 0.51, 0.72),
        ("PMC9491404 renal compuesto", 0.66, 0.58, 0.75),
        ("PMC9491404 mortalidad", 0.86, 0.77, 0.96),
        ("PMC8591237 macroalbuminuria", 0.57, 0.48, 0.67),
        ("PMC7613836 SMART-C", 0.63, 0.58, 0.69),
    ]
    for nombre, v, lo, hi in reales:
        rep = verificar(Observacion(razon=R(v, lo, hi)))
        ok(rep.cierre is Cierre.CIERRA, f"{nombre} debe cerrar: {codigos(rep)}")
        a = asimetria_log(R(v, lo, hi))
        ok(a is not None and a < 0.10,
           f"{nombre}: la asimetria real debe ser pequena, fue {a:.3f}")


def test_dapa_ckd_completo_cierra_con_cuatro_relaciones():
    rep = verificar(Observacion(
        razon=R(0.61, 0.51, 0.72), n_total=4304, eventos_total=509,
        tasa_control=0.145, tasa_tratado=0.091, reduccion_relativa=0.39,
        significativo_declarado=True,
    ))
    ok(rep.cierre is Cierre.CIERRA,
       f"el conjunto real completo debe cerrar: {[f.codigo for f in rep.fallos]}")
    ok(rep.relaciones_comprobadas >= 5,
       f"debe comprobar varias relaciones: {rep.relaciones_comprobadas}")
    ok(rep.confianza > 0.65,
       f"mas relaciones comprobadas, mas confianza: {rep.confianza}")


# ============================================================ fabricacion detectada
def test_intervalo_demasiado_estrecho():
    """La firma de un intervalo inventado: implica mas eventos de los que caben."""
    rep = verificar(Observacion(razon=R(0.61, 0.59, 0.63), n_total=4304,
                                tasa_control=0.145))
    ok(rep.cierre is Cierre.NO_CIERRA, f"debe no cerrar: {codigos(rep)}")
    ok("INTERVALO_INCOMPATIBLE_CON_EL_TAMANO_DE_MUESTRA" in codigos(rep),
       f"codigos: {codigos(rep)}")
    ok("MAS_EVENTOS_QUE_PARTICIPANTES" in codigos(rep),
       "14284 eventos en 4304 personas es imposible y debe decirse asi")


def test_intervalo_de_otro_analisis():
    """Emparejar un punto estimado con el intervalo de otro analisis deja una
    asimetria logaritmica que en cifras reales nunca aparece."""
    rep = verificar(Observacion(razon=R(0.61, 0.55, 0.95)))
    ok(rep.cierre is Cierre.NO_CIERRA, f"debe no cerrar: {codigos(rep)}")
    ok("INTERVALO_ASIMETRICO" in codigos(rep), f"codigos: {codigos(rep)}")
    a = asimetria_log(R(0.61, 0.55, 0.95))
    ok(a > 1.0, f"la asimetria debe ser grande: {a:.2f}")


def test_eventos_declarados_incompatibles():
    rep = verificar(Observacion(razon=R(0.61, 0.51, 0.72), eventos_total=40))
    ok(rep.cierre is Cierre.NO_CIERRA, "40 eventos no producen ese intervalo")
    ok("EVENTOS_INCOMPATIBLES_CON_EL_INTERVALO" in codigos(rep), f"{codigos(rep)}")


def test_punto_fuera_del_intervalo():
    rep = verificar(Observacion(razon=R(0.61, 0.70, 0.90)))
    ok("PUNTO_FUERA_DEL_INTERVALO" in codigos(rep),
       f"es imposible y no admite matices: {codigos(rep)}")
    ok(rep.cierre is Cierre.NO_CIERRA, "debe bloquear")


def test_confundir_la_razon_con_su_complemento():
    """El error de interpretacion mas frecuente del gremio."""
    rep = verificar(Observacion(razon=R(0.61, 0.51, 0.72), reduccion_relativa=0.61))
    ok("REDUCCION_RELATIVA_NO_COINCIDE" in codigos(rep),
       f"una razon de 0.61 implica 39% de reduccion, no 61%: {codigos(rep)}")

    rep2 = verificar(Observacion(razon=R(0.61, 0.51, 0.72), reduccion_relativa=0.39))
    ok(rep2.cierre is Cierre.CIERRA, "con el complemento correcto debe cerrar")


def test_tasas_que_no_producen_la_razon():
    rep = verificar(Observacion(razon=R(0.61, 0.51, 0.72), tasa_control=0.145,
                                tasa_tratado=0.130))
    ok("RAZON_NO_COINCIDE_CON_LAS_TASAS" in codigos(rep),
       f"13.0% sobre 14.5% es 0.90, no 0.61: {codigos(rep)}")


def test_nnt_que_no_es_el_reciproco():
    rep = verificar(Observacion(tasa_control=0.145, tasa_tratado=0.091, nnt=50))
    ok("NNT_NO_COINCIDE" in codigos(rep),
       f"la reduccion absoluta de 5.4 puntos da un NNT de ~18, no 50: {codigos(rep)}")

    rep2 = verificar(Observacion(tasa_control=0.145, tasa_tratado=0.091, nnt=18.5))
    ok(rep2.cierre is Cierre.CIERRA, f"con el reciproco correcto cierra: {codigos(rep2)}")


def test_reduccion_absoluta_que_no_coincide():
    rep = verificar(Observacion(tasa_control=0.145, tasa_tratado=0.091,
                                reduccion_absoluta=0.10))
    ok("REDUCCION_ABSOLUTA_NO_COINCIDE" in codigos(rep), f"{codigos(rep)}")


def test_significancia_contradice_el_intervalo():
    rep = verificar(Observacion(razon=R(0.90, 0.75, 1.08),
                                significativo_declarado=True))
    ok("SIGNIFICANCIA_CONTRADICE_EL_INTERVALO" in codigos(rep),
       f"el intervalo cruza la unidad: {codigos(rep)}")

    rep2 = verificar(Observacion(razon=R(0.61, 0.51, 0.72),
                                significativo_declarado=True))
    ok(rep2.cierre is Cierre.CIERRA, "un intervalo que no cruza la unidad si es coherente")


# ============================================================ unidades y dosis
def test_cierre_de_unidades_de_laboratorio():
    a = Magnitud(Clase.CONCENTRACION, 100, "mg/dl", analito="ldl")
    b = Magnitud(Clase.CONCENTRACION, 2.586, "mmol/l", analito="ldl")
    rep = verificar(Observacion(concentracion_a=a, concentracion_b=b, analito="ldl"))
    ok(rep.cierre is Cierre.CIERRA, f"100 mg/dL = 2.59 mmol/L de LDL: {codigos(rep)}")

    mala = Magnitud(Clase.CONCENTRACION, 5.0, "mmol/l", analito="ldl")
    rep2 = verificar(Observacion(concentracion_a=a, concentracion_b=mala, analito="ldl"))
    ok("UNIDADES_NO_RECONCILIAN" in codigos(rep2),
       f"la conversion es fija: si no cierra, una de las dos no es de ese analito: "
       f"{codigos(rep2)}")


def test_cierre_de_dosis_diaria():
    rep = verificar(Observacion(dosis_por_toma=5, tomas_por_dia=2, dosis_diaria=10))
    ok(rep.cierre is Cierre.CIERRA, f"5 mg dos veces al dia son 10: {codigos(rep)}")

    rep2 = verificar(Observacion(dosis_por_toma=5, tomas_por_dia=2, dosis_diaria=5))
    ok("DOSIS_DIARIA_NO_COINCIDE" in codigos(rep2), f"{codigos(rep2)}")


def test_confusion_entre_dosis_por_peso_y_absoluta():
    """El error de dosificacion mas frecuente y el mas grave."""
    rep = verificar(Observacion(dosis_por_kg=1.5, peso_kg=70, dosis_diaria=105))
    ok(rep.cierre is Cierre.CIERRA, f"1.5 mg/kg en 70 kg son 105 mg: {codigos(rep)}")

    rep2 = verificar(Observacion(dosis_por_kg=1.5, peso_kg=70, dosis_diaria=1.5))
    ok("DOSIS_POR_PESO_NO_COINCIDE" in codigos(rep2),
       f"se declaro la dosis por kilo como si fuera la absoluta: {codigos(rep2)}")


# ============================================================ comportamiento general
def test_sin_datos_es_insuficiente():
    rep = verificar(Observacion())
    ok(rep.cierre is Cierre.INSUFICIENTE, f"sin cantidades no se comprueba nada")
    ok(rep.confianza == 0.0, "y la confianza es cero, no se inventa")
    ok(rep.relaciones_comprobadas == 0, "y debe decir que comprobo cero relaciones")


def test_razon_sin_intervalo_no_alcanza():
    rep = verificar(Observacion(razon=R(0.61)))
    ok(rep.cierre is Cierre.INSUFICIENTE,
       "una razon sin intervalo no permite ninguna comprobacion aritmetica")


def test_la_confianza_crece_con_las_relaciones_no_con_la_insistencia():
    una = verificar(Observacion(razon=R(0.61, 0.51, 0.72)))
    muchas = verificar(Observacion(
        razon=R(0.61, 0.51, 0.72), n_total=4304, eventos_total=509,
        tasa_control=0.145, tasa_tratado=0.091, reduccion_relativa=0.39,
        significativo_declarado=True))
    ok(muchas.confianza > una.confianza,
       f"mas relaciones independientes dan mas confianza: {una.confianza} -> "
       f"{muchas.confianza}")
    ok(muchas.confianza <= 0.80,
       f"con tope por debajo de 1: el cierre prueba que recuerda un estudio real, no "
       f"que sea el estudio correcto. Fue {muchas.confianza}")


def test_los_derivados_quedan_a_la_vista():
    rep = verificar(Observacion(razon=R(0.61, 0.51, 0.72), n_total=4304,
                                tasa_control=0.145))
    ok("eventos_implicados_por_el_intervalo" in rep.derivados,
       f"debe exponer lo que dedujo: {list(rep.derivados)}")
    ok("asimetria" in rep.derivados, "y la asimetria medida")
    d = rep.dict()
    ok("cierre" in d and "derivados" in d, f"debe serializarse: {list(d)}")


def test_error_estandar_rechaza_intervalos_imposibles():
    ok(error_estandar_log(R(0.61, 0.72, 0.51)) is None, "limites invertidos")
    ok(error_estandar_log(R(0.61, 0, 0.72)) is None, "limite inferior en cero")
    ok(error_estandar_log(R(0.61, -0.1, 0.72)) is None, "limite negativo")
    ok(error_estandar_log(R(0.61)) is None, "sin intervalo")


def test_plan_de_preguntas_es_separable():
    plan = plan_de_preguntas("efecto de un iSGLT2 sobre la progresion renal",
                             "adultos con ERC y albuminuria", "desenlace renal compuesto")
    ok(len(plan) >= 6, f"debe pedir varias cantidades ligadas: {len(plan)}")
    campos = {p["campo"] for p in plan}
    for esperado in ("razon", "n_total", "eventos_total", "tasa_control", "nnt"):
        ok(esperado in campos, f"debe pedir {esperado}: {campos}")
    for p in plan:
        ok("intervalo" not in p["pregunta"].lower() or p["campo"] == "razon",
           f"ninguna pregunta debe insinuar la aritmetica que se va a comprobar: "
           f"{p['campo']}")


def test_el_texto_real_se_puede_alimentar_directo():
    """Integracion con el parser: la razon sale del texto, no se escribe a mano."""
    m = parsear("HR 0.61 (95% CI 0.51-0.72)")[0]
    rep = verificar(Observacion(razon=m, n_total=4304, tasa_control=0.145))
    ok(rep.cierre is Cierre.CIERRA, f"debe cerrar desde el texto parseado: {codigos(rep)}")


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
