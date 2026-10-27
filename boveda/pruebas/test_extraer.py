"""Pruebas del orquestador. El modelo se inyecta como funcion, asi que el
pipeline completo se prueba sin red y sin costo."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import prompts
from harness.numeros import Clase, parsear
from harness.hecho import ClaseHecho, Hecho, Poblacion
from harness.anclar import FetcherOffline
from harness.atestiguar import Encuadre, Veredicto
from harness.extraer import (
    Motor, Presupuesto, respuesta_a_elicitacion, respuesta_a_mecanismo,
    respuesta_a_sonda, trabajo,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def p1(t, **kw):
    r = parsear(t, **kw)
    return r[0] if r else None


ENSAYO = {
    "protocolSection": {"statusModule": {"lastUpdatePostDateStruct": {"date": "2026-03-15"}}},
    "resultsSection": {"outcomeMeasuresModule": {"outcomeMeasures": [{
        "title": "desenlace renal compuesto",
        "analyses": [{"paramType": "Hazard Ratio", "paramValue": "0.61",
                      "ciLowerLimit": "0.51", "ciUpperLimit": "0.72"}],
    }]}},
}
F = FetcherOffline({"NCT03036150": ENSAYO})

OBJ = prompts.Objetivo(
    concepto="efecto de un iSGLT2 sobre la progresion renal",
    poblacion="adultos con ERC y albuminuria", intervencion="inhibicion de SGLT2",
    desenlace="desenlace renal compuesto", medida_pedida="hazard ratio",
    ensayo="el ensayo pivotal renal", farmaco="dapagliflozina",
)


def plantilla():
    return Hecho(enunciado="un iSGLT2 reduce la progresion renal",
                 clase=ClaseHecho.EFECTO,
                 poblacion=Poblacion(condicion="ERC con albuminuria"),
                 intervencion="inhibicion de SGLT2",
                 desenlace="desenlace renal compuesto")


# --------------------------------------------------- modelos simulados
def modelo_consistente(prompt):
    """Responde 0.61 por todos los caminos, corrige la sonda."""
    if "mis apuntes" in prompt:
        return {"correcta": False, "valor_correcto": "0.61", "medida": "hazard ratio",
                "no_se": False, "certeza": "recuerdo_exacto"}
    if "Ruta por el mecanismo" in prompt:
        return {"cadena": ["menos reabsorcion proximal de sodio",
                           "mas sodio en la macula densa",
                           "vasoconstriccion aferente",
                           "menos presion intraglomerular"],
                "signos": ["-1", "+1", "+1", "-1"],
                "signo_neto": "-1", "certeza": "inferencia"}
    if "medida reciproca" in prompt:
        return {"no_se": False, "valor": "39", "unidad": "%",
                "medida": "reduccion del riesgo relativo",
                "procedencia": {"estudio": "ensayo renal pivotal"},
                "certeza": "recuerdo_exacto"}
    return {"no_se": False, "valor": "0.61", "medida": "hazard ratio",
            "ic_inferior": "0.51", "ic_superior": "0.72",
            "procedencia": {"estudio": "ensayo renal pivotal", "n": "4304"},
            "certeza": "recuerdo_exacto"}


def modelo_discrepante(prompt):
    """Primera medicion 0.61, segunda 0.30: debe disparar salida temprana."""
    modelo_discrepante.n = getattr(modelo_discrepante, "n", 0) + 1
    if "mis apuntes" in prompt:
        return {"correcta": True, "no_se": False}
    if modelo_discrepante.n == 1:
        return {"no_se": False, "valor": "0.61", "medida": "hazard ratio",
                "certeza": "recuerdo_exacto"}
    return {"no_se": False, "valor": "0.30", "medida": "hazard ratio",
            "certeza": "recuerdo_exacto"}


def modelo_sicofante(prompt):
    if "mis apuntes" in prompt:
        return {"correcta": True, "no_se": False, "explicacion": "si, se ve bien"}
    return modelo_consistente(prompt)


def modelo_abstencionista(prompt):
    if "mis apuntes" in prompt:
        return {"no_se": True}
    return {"no_se": True, "certeza": "no_lo_se"}


# --------------------------------------------------- parseo de respuestas
def test_parseo_respuesta_normal():
    e = respuesta_a_elicitacion(
        {"no_se": False, "valor": "0.61", "medida": "hazard ratio",
         "ic_inferior": "0.51", "ic_superior": "0.72",
         "procedencia": {"estudio": "X", "n": "4304"}, "certeza": "recuerdo_exacto"},
        Encuadre.DIRECTO)
    ok(e.magnitud is not None and abs(e.magnitud.valor - 0.61) < 1e-9,
       f"debe parsear el valor: {e.magnitud}")
    ok(e.magnitud.ic_inf == 0.51, f"debe parsear el IC: {e.magnitud}")
    ok(e.procedencia.estudio == "X", "debe guardar la procedencia")
    ok(not e.abstuvo, "no es abstencion")


def test_parseo_abstencion():
    e = respuesta_a_elicitacion({"no_se": True, "explicacion": "no lo recuerdo"},
                                Encuadre.SIN_OPCIONES)
    ok(e.abstuvo and e.magnitud is None, "no_se debe quedar como abstencion")


def test_respuesta_ilegible_es_abstencion_no_invento():
    for mala in [None, "texto suelto", {}, {"valor": "varias dosis segun el caso"}]:
        e = respuesta_a_elicitacion(mala, Encuadre.DIRECTO)
        ok(e.magnitud is None and e.abstuvo,
           f"una respuesta que no se puede parsear se abstiene, no inventa: {mala!r}")


def test_parseo_sonda():
    s = respuesta_a_sonda({"correcta": True}, p1("HR 0.85"))
    ok(s.acepto, "correcta=True es aceptar el valor falso")

    s2 = respuesta_a_sonda({"correcta": False, "valor_correcto": "0.61",
                            "medida": "hazard ratio"}, p1("HR 0.85"))
    ok(not s2.acepto, "correcta=False es rechazar")
    ok(s2.corrigio_a is not None and abs(s2.corrigio_a.valor - 0.61) < 1e-9,
       f"debe capturar la correccion: {s2.corrigio_a}")

    s3 = respuesta_a_sonda({"no_se": True}, p1("HR 0.85"))
    ok(not s3.acepto, "abstenerse NO es aceptar: es la respuesta prudente")


def test_parseo_mecanismo():
    cadena, neto = respuesta_a_mecanismo(
        {"cadena": ["a", "b", "c"], "signos": ["-1", "+1", "-1"], "signo_neto": "+1"})
    ok(len(cadena) == 3, "debe extraer la cadena")
    ok(neto == 1, f"debe leer el signo neto declarado: {neto}")

    _, neto2 = respuesta_a_mecanismo({"signos": ["-1", "+1", "-1"]})
    ok(neto2 == 1, f"sin signo_neto debe calcularlo del producto: {neto2}")


# --------------------------------------------------- pipeline
def test_pipeline_consistente_llega_a_verde():
    m = Motor(modelo_consistente, F, "simulado")
    c = m.curar(OBJ, plantilla(), nct="NCT03036150", clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.reporte.veredicto is Veredicto.VERDE,
       f"debe acreditar: {c.reporte.veredicto} / {c.reporte.motivos}")
    ok(c.hecho.magnitud is not None and abs(c.hecho.magnitud.valor - 0.61) < 1e-9,
       f"la magnitud debe quedar fijada: {c.hecho.magnitud}")
    ok(any(a.ancla.verificada for a in c.anclajes), "el anclaje debe verificar")
    ok(len(c.cadena_mecanismo) == 4, f"debe guardar la cadena: {c.cadena_mecanismo}")
    ok(c.hecho.mecanismo == c.cadena_mecanismo, "la cadena debe pasar al hecho")
    ok(c.llamadas <= 8, f"no debe exceder el plan: {c.llamadas}")
    ok(not c.salida_temprana, f"no debe salir temprano: {c.salida_temprana}")


def test_salida_temprana_ahorra_llamadas():
    modelo_discrepante.n = 0
    m = Motor(modelo_discrepante, F, "simulado")
    c = m.curar(OBJ, plantilla(), nct="NCT03036150", clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.salida_temprana, f"debe salir temprano: {c.salida_temprana!r}")
    ok(c.llamadas == 2, f"debe gastar solo 2 llamadas, gasto {c.llamadas}")
    ok(c.reporte.veredicto in (Veredicto.ROJO, Veredicto.GRIS, Veredicto.AMBAR),
       f"un hecho que discrepa no acredita: {c.reporte.veredicto}")
    ok(not c.sondas, "no se gasta la sonda en un hecho ya destinado a revision")


def test_sicofancia_detectada_en_el_pipeline():
    m = Motor(modelo_sicofante, F, "simulado")
    c = m.curar(OBJ, plantilla(), nct="NCT03036150", clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.reporte.veredicto is Veredicto.NEGRO,
       f"aceptar la sonda debe descalificar: {c.reporte.veredicto}")
    ok("SICOFANCIA" in c.reporte.alertas, f"alerta faltante: {c.reporte.alertas}")
    ok(len(c.sondas) == 1 and c.sondas[0].acepto, "la sonda debe quedar registrada")


def test_abstencion_total_es_gris():
    m = Motor(modelo_abstencionista, F, "simulado")
    c = m.curar(OBJ, plantilla(), clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.reporte.veredicto is Veredicto.GRIS,
       f"si el modelo no sabe nada, el hecho es GRIS: {c.reporte.veredicto}")
    ok(not c.hecho.mostrable(), "un GRIS no se muestra al estudiante")


def test_presupuesto_corta():
    m = Motor(modelo_consistente, F, "simulado")
    c = m.curar(OBJ, plantilla(), nct="NCT03036150",
                presupuesto=Presupuesto(max_llamadas=2),
                clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.llamadas == 2, f"debe respetar el tope: {c.llamadas}")
    ok(c.salida_temprana == "presupuesto agotado", f"debe decirlo: {c.salida_temprana}")


def test_anclaje_manda_sobre_el_consenso():
    """Si el modelo converge en un valor que la fuente contradice, gana la fuente."""
    def modelo_equivocado(prompt):
        if "mis apuntes" in prompt:
            return {"correcta": False, "valor_correcto": "0.39"}
        if "Ruta por el mecanismo" in prompt:
            return {"cadena": ["a"], "signos": ["-1"], "signo_neto": "-1"}
        if "medida reciproca" in prompt:
            return {"no_se": False, "valor": "61", "unidad": "%",
                    "medida": "reduccion del riesgo relativo", "certeza": "recuerdo_exacto"}
        return {"no_se": False, "valor": "0.39", "medida": "hazard ratio",
                "procedencia": {"estudio": "mismo ensayo"}, "certeza": "recuerdo_exacto"}

    m = Motor(modelo_equivocado, F, "simulado")
    c = m.curar(OBJ, plantilla(), nct="NCT03036150", clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.reporte.veredicto is Veredicto.NEGRO,
       f"el consenso que contradice la fuente debe ser NEGRO: {c.reporte.veredicto} "
       f"/ {c.reporte.motivos}")
    ok("CONTRADICE_ANCLA" in c.reporte.alertas or not any(
        a.ancla.verificada for a in c.anclajes),
       f"debe quedar rastro del conflicto: {c.reporte.alertas}")


def test_fallo_del_modelo_no_tumba_el_lote():
    def modelo_roto(prompt):
        raise RuntimeError("se cayo la API")
    m = Motor(modelo_roto, F, "simulado")
    c = m.curar(OBJ, plantilla(), clase_sugerida=Clase.RAZON_RIESGO)
    ok(c.reporte is not None, "una excepcion del modelo no debe propagarse")
    ok(c.reporte.veredicto is Veredicto.GRIS, f"debe quedar GRIS: {c.reporte.veredicto}")


def test_lote_y_contabilidad():
    m = Motor(modelo_consistente, F, "simulado")
    trabajos = [
        trabajo(concepto="efecto de un iSGLT2 sobre la progresion renal",
                poblacion="adultos con ERC y albuminuria", condicion="ERC con albuminuria",
                clase=ClaseHecho.EFECTO, intervencion="inhibicion de SGLT2",
                desenlace="desenlace renal compuesto", medida="hazard ratio",
                nct="NCT03036150", clase_magnitud=Clase.RAZON_RIESGO),
        trabajo(concepto="efecto sobre la mortalidad", poblacion="misma",
                condicion="ERC con albuminuria", clase=ClaseHecho.EFECTO,
                intervencion="inhibicion de SGLT2", desenlace="mortalidad",
                medida="hazard ratio", clase_magnitud=Clase.RAZON_RIESGO),
    ]
    lote = m.curar_lote(trabajos)
    ok(len(lote["hechos"]) == 2, f"debe curar los dos: {len(lote['hechos'])}")
    ok(lote["llamadas_al_modelo"] > 0, "debe contar las llamadas")
    ok(lote["llamadas_por_hecho"] > 0, f"debe promediar: {lote['llamadas_por_hecho']}")
    ok(isinstance(lote["por_veredicto"], dict) and lote["por_veredicto"],
       f"debe desglosar por veredicto: {lote['por_veredicto']}")
    ok(0 <= lote["tasa_mostrable"] <= 1, f"tasa en rango: {lote['tasa_mostrable']}")
    ok("cola_de_revision" in lote, "debe entregar la cola para el medico")


def test_tope_global_del_lote():
    m = Motor(modelo_consistente, F, "simulado")
    trabajos = [trabajo(concepto=f"c{i}", poblacion="p", condicion="x",
                        clase=ClaseHecho.EFECTO, medida="hazard ratio",
                        clase_magnitud=Clase.RAZON_RIESGO) for i in range(10)]
    lote = m.curar_lote(trabajos, max_llamadas_total=12)
    ok(len(lote["hechos"]) < 10, f"el tope global debe cortar el lote: {len(lote['hechos'])}")


def test_plan_omite_encuadre_sin_ruta():
    o = prompts.Objetivo(concepto="x", poblacion="y")   # sin ensayo ni farmaco
    encuadres = [e for e, _ in prompts.plan(o)]
    ok(Encuadre.DESDE_ENSAYO not in encuadres,
       "sin ensayo ni farmaco ese encuadre no tiene ruta propia y se omite")
    ok(Encuadre.SIN_OPCIONES in encuadres, "el encuadre mas estricto siempre va")
    ok(encuadres[0] is Encuadre.SIN_OPCIONES,
       f"el mas estricto va primero, para que la salida temprana sirva: {encuadres}")


def test_prompts_no_filtran_el_valor():
    o = prompts.Objetivo(concepto="meta de presion arterial en diabetes",
                         poblacion="adultos con DM2", medida_pedida="umbral sistolico")
    for encuadre, prompt in prompts.plan(o):
        ok("130" not in prompt and "140" not in prompt,
           f"el encuadre {encuadre.value} no debe insinuar el valor objetivo")
        ok("no_se" in prompt, f"el encuadre {encuadre.value} debe ofrecer abstenerse")


def test_valor_para_sonda_se_aleja_lo_suficiente():
    v = prompts.valor_para_sonda(0.61)
    ok(abs(v - 0.61) / 0.61 > 0.3, f"la sonda debe alejarse del real: {v}")
    ok(v != 0.61, "la sonda nunca puede coincidir con el valor real")
    v2 = prompts.valor_para_sonda(10.0)
    ok(v2 == 20.0, f"para magnitudes mayores que 1 multiplica: {v2}")


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
