"""Pruebas del anclaje. Usan FetcherOffline con documentos que replican la forma
real de las respuestas de ClinicalTrials.gov API v2 y de openFDA."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import Acuerdo, Clase, Magnitud, parsear
from harness.hecho import ClaseHecho, Hecho, Poblacion, TipoAncla
from harness.anclar import (
    AnclajeImposible, FetcherOffline, anclar_en_ensayo, anclar_en_etiqueta,
    aplicar_anclaje, necesita_refresco,
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


# Documento con la forma real de la API v2: ruta
# resultsSection.outcomeMeasuresModule.outcomeMeasures[].analyses[]
ENSAYO = {
    "protocolSection": {
        "statusModule": {"lastUpdatePostDateStruct": {"date": "2026-03-15"}}
    },
    "resultsSection": {
        "outcomeMeasuresModule": {
            "outcomeMeasures": [
                {
                    "title": "Tiempo al primer evento del desenlace renal compuesto",
                    "description": "caida sostenida del eGFR, enfermedad renal terminal o muerte renal",
                    "type": "PRIMARY",
                    "analyses": [{
                        "paramType": "Hazard Ratio",
                        "paramValue": "0.61",
                        "ciPctValue": "95",
                        "ciLowerLimit": "0.51",
                        "ciUpperLimit": "0.72",
                        "pValue": "<0.001",
                        "statisticalMethod": "Regression, Cox",
                    }],
                },
                {
                    "title": "Mortalidad por todas las causas",
                    "type": "SECONDARY",
                    "analyses": [{
                        "paramType": "Hazard Ratio",
                        "paramValue": "0.69",
                        "ciLowerLimit": "0.53",
                        "ciUpperLimit": "0.88",
                    }],
                },
            ]
        }
    },
}

ENSAYO_SIN_RESULTADOS = {
    "protocolSection": {"statusModule": {"lastUpdatePostDateStruct": {"date": "2026-01-01"}}},
}

# Documento con la forma real de openFDA: la cifra vive en PROSA, no en un campo
ETIQUETA = {
    "results": [{
        "openfda": {"spl_set_id": ["abc-123-def"], "generic_name": ["DAPAGLIFLOZIN"]},
        "dosage_and_administration": [
            "2.1 Recommended Dosage. The recommended dosage is 10 mg orally once daily "
            "in the morning, with or without food. "
            "2.2 Patients with Renal Impairment. Initiation is not recommended in patients "
            "with an eGFR less than 25 mL/min/1.73 m2. "
            "Doses above 10 mg daily have not been studied for this indication."
        ],
        "use_in_specific_populations": [
            "8.6 Renal Impairment. No dose adjustment is required in patients with an eGFR "
            "of 25 mL/min/1.73 m2 or greater. "
            "8.7 Hepatic Impairment. In patients with severe hepatic impairment a starting "
            "dose of 5 mg is recommended."
        ],
        "mechanism_of_action": [
            "Inhibition of SGLT2 reduces reabsorption of filtered glucose in the proximal "
            "renal tubule and lowers the renal threshold for glucose."
        ],
    }]
}

F = FetcherOffline({"NCT03036150": ENSAYO, "NCT99999999": ENSAYO_SIN_RESULTADOS,
                    "dapagliflozin": ETIQUETA})


# ------------------------------------------------------------- ensayo
def test_ancla_ensayo_coincide():
    r = anclar_en_ensayo("NCT03036150", p1("HR 0.61"), F, desenlace="renal compuesto")
    ok(r.ancla.verificada, f"debe verificar: {r.motivo}")
    ok(r.coincide is Acuerdo.IDENTICO, f"debe coincidir identico: {r.coincide}")
    ok("outcomeMeasures[0].analyses[0]" in r.ruta, f"debe dar la ruta JSON exacta: {r.ruta}")
    ok(r.encontrado.ic_inf == 0.51 and r.encontrado.ic_sup == 0.72,
       f"debe traer el IC del registro: {r.encontrado}")
    ok(r.ancla.fecha_consulta == "2026-03-15",
       f"debe guardar la fecha de ultima actualizacion: {r.ancla.fecha_consulta}")
    ok(r.ancla.tipo is TipoAncla.REGISTRO_ENSAYO, "tipo de ancla correcto")
    ok(len(r.ancla.cita_corta.split()) <= 21, f"la cita corta se recorta: {r.ancla.cita_corta}")


def test_ancla_ensayo_equivalente_por_complemento():
    # el hecho afirma RRR 39%; el registro trae HR 0.61: deben reconciliarse
    r = anclar_en_ensayo("NCT03036150", p1("reduccion del riesgo relativo del 39%"), F,
                         desenlace="renal compuesto")
    ok(r.ancla.verificada, f"HR 0.61 debe anclar un RRR de 39%: {r.motivo}")
    ok(r.coincide is Acuerdo.EQUIVALENTE, f"debe ser equivalencia: {r.coincide}")


def test_ancla_ensayo_discrepa():
    """Cuando la fuente dice OTRO numero, el ancla se verifica con el de la fuente.

    Es deliberado y es la pieza que hace que una cifra equivocada se bloquee en
    vez de degradarse. Si el ancla quedara sin verificar, la atestiguacion solo
    veria "sin ancla" y mostraria la cifra equivocada con una etiqueta de no
    anclada. Verificando el ancla con el valor de la fuente, la cifra afirmada
    entra en contradiccion explicita y la atestiguacion la manda a NEGRO.
    """
    r = anclar_en_ensayo("NCT03036150", p1("HR 0.39"), F, desenlace="renal compuesto")
    ok(r.coincide is Acuerdo.DISCREPANTE, f"debe discrepar: {r.coincide}")
    ok(r.ancla.verificada,
       "el ancla se verifica con lo que SI dice la fuente, no con lo afirmado")
    ok(r.encontrado is not None and abs(r.encontrado.valor - 0.61) < 1e-9,
       f"el ancla debe llevar el valor real de la fuente: {r.encontrado}")
    ok(r.candidatos and len(r.candidatos) >= 1,
       "debe devolver lo que si encontro, para el revisor humano")


def test_discrepancia_de_fuente_termina_en_negro():
    """La prueba de punta a punta de lo anterior."""
    from harness.atestiguar import Elicitacion, Encuadre, Veredicto, atestiguar
    h = Hecho("un iSGLT2 reduce la progresion renal", ClaseHecho.EFECTO,
              Poblacion("ERC con albuminuria"),
              intervencion="iSGLT2", desenlace="desenlace renal compuesto")
    r = anclar_en_ensayo("NCT03036150", p1("HR 0.39"), F, desenlace="renal compuesto")
    aplicar_anclaje(h, [r])
    rep = atestiguar(h, [
        Elicitacion(p1("HR 0.39"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,39"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("HR 0.40"), Encuadre.SIN_OPCIONES),
    ])
    ok(rep.veredicto is Veredicto.NEGRO,
       f"una cifra que contradice su propia fuente debe bloquearse: {rep.veredicto}")
    ok("CONTRADICE_ANCLA" in rep.alertas, f"alerta faltante: {rep.alertas}")
    ok(not h.mostrable() if h.veredicto == "NEGRO" else True, "no se muestra")


def test_desenlace_filtra():
    # sin filtro de desenlace tomaria el primero que coincida; con filtro va al correcto
    r = anclar_en_ensayo("NCT03036150", p1("HR 0.69"), F, desenlace="mortalidad")
    ok(r.ancla.verificada, f"debe anclar el desenlace secundario pedido: {r.motivo}")
    ok("outcomeMeasures[1]" in r.ruta, f"debe apuntar al desenlace correcto: {r.ruta}")


def test_nct_mal_formado_no_consulta():
    r = anclar_en_ensayo("DAPA-CKD", p1("HR 0.61"), F)
    ok(not r.ancla.verificada, "un identificador mal formado no puede verificar")
    ok("no tiene la forma" in r.motivo, f"debe explicar por que: {r.motivo}")

    r2 = anclar_en_ensayo("NCT123", p1("HR 0.61"), F)
    ok(not r2.ancla.verificada, "NCT con pocos digitos se rechaza")


def test_registro_sin_resultados():
    r = anclar_en_ensayo("NCT99999999", p1("HR 0.61"), F)
    ok(not r.ancla.verificada, "sin resultados publicados no hay ancla de efecto")
    ok("no publico resultados" in r.motivo, f"motivo claro: {r.motivo}")


def test_documento_inalcanzable():
    r = anclar_en_ensayo("NCT00000001", p1("HR 0.61"), F)
    ok(not r.ancla.verificada, "si no se puede traer el documento, no hay ancla")
    ok("sin documento offline" in r.motivo, f"debe propagar el motivo: {r.motivo}")


# ------------------------------------------------------------- etiqueta
def test_ancla_etiqueta_dosis_en_prosa():
    r = anclar_en_etiqueta("dapagliflozin", p1("10 mg una vez al dia"), F,
                           tipo_hecho="dosis")
    ok(r.ancla.verificada, f"debe extraer la dosis de la prosa: {r.motivo}")
    ok("dosage_and_administration" in r.ruta, f"debe decir en que campo: {r.ruta}")
    ok("offset" in r.ruta, f"debe dar el desplazamiento para re-verificar: {r.ruta}")
    ok(r.ancla.localizador.startswith("SPL:"), f"localizador SPL: {r.ancla.localizador}")
    ok(r.ancla.licencia == "CC0 1.0 (openFDA)", f"licencia: {r.ancla.licencia}")


def test_ancla_etiqueta_corte_renal_en_prosa():
    # openFDA no tiene campo de ajuste renal: el corte vive solo en el texto
    r = anclar_en_etiqueta("dapagliflozin", Magnitud(Clase.TFG, 25, "ml/min/1.73m2"), F,
                           tipo_hecho="ajuste_renal")
    ok(r.ancla.verificada, f"debe extraer el corte de eGFR de la prosa: {r.motivo}")
    ok(r.encontrado is not None and r.encontrado.valor == 25,
       f"debe dar 25 mL/min/1.73m2: {r.encontrado}")


def test_ancla_etiqueta_pista_desambigua():
    # hay un 10 mg y un 5 mg en la etiqueta: la pista dirige a la seccion hepatica
    r = anclar_en_etiqueta("dapagliflozin", p1("5 mg"), F,
                           tipo_hecho="ajuste_hepatico", pista="hepatic")
    ok(r.ancla.verificada, f"debe encontrar la dosis hepatica de 5 mg: {r.motivo}")
    ok("hepatic" in r.ancla.cita_corta.lower(),
       f"la cita debe venir de la seccion correcta: {r.ancla.cita_corta}")


def test_ancla_etiqueta_discrepa():
    r = anclar_en_etiqueta("dapagliflozin", p1("100 mg al dia"), F, tipo_hecho="dosis")
    ok(r.coincide is Acuerdo.DISCREPANTE, f"una dosis diez veces mayor discrepa: {r.coincide}")
    ok(r.ancla.verificada, "el ancla lleva lo que dice la etiqueta")
    ok(r.encontrado is not None and r.encontrado.valor == 10,
       f"la etiqueta dice 10 mg, no 100: {r.encontrado}")
    ok(r.candidatos, "debe reportar las magnitudes que si parseo")


def test_numero_de_seccion_no_es_una_cifra_clinica():
    """Regresion. Las etiquetas de la FDA estan numeradas por seccion: 2.1, 8.6,
    12.1. Sin limpiar eso, "2.1 Recommended Dosage" se parsea como una dosis de
    2.1 mg y el anclaje concluye que la etiqueta contradice la dosis real. Es
    exactamente la clase de cifra fantasma que la Boveda tiene que no cometer.
    """
    from harness.anclar import _oraciones
    frases = _oraciones("2.1 Recommended Dosage. The recommended dosage is 10 mg "
                        "orally once daily. 8.6 Renal Impairment. No adjustment.")
    ok(not any(f.startswith("2.1") or f.startswith("8.6") for f, _, _ in frases),
       f"el numero de seccion debe quedar fuera de la oracion: {[f[:30] for f, _, _ in frases]}")
    ok(all(o >= 0 for _, o, _ in frases), "los desplazamientos deben ser validos")

    # pero NO debe descartarse: la subseccion se arrastra como contexto
    secciones = [sec for _, _, sec in frases]
    ok("2.1" in secciones, f"la subseccion 2.1 debe quedar registrada: {secciones}")
    ok("8.6" in secciones, f"la subseccion 8.6 debe quedar registrada: {secciones}")
    ok(secciones[1] == "2.1",
       f"la subseccion se arrastra a la oracion siguiente, que no la repite: {secciones}")

    mags = []
    for f, _, _ in frases:
        mags += parsear(f, clase_sugerida=Clase.DOSIS)
    valores = sorted({m.valor for m in mags})
    ok(2.1 not in valores and 8.6 not in valores,
       f"ninguna dosis debe salir de la numeracion de seccion: {valores}")
    ok(10 in valores, f"la dosis real si debe parsearse: {valores}")


def test_subseccion_es_restriccion_dura():
    """La estructura del formato PLR esta impuesta por regulacion, no inferida.
    Una cifra fuera de su subseccion no es el dato buscado."""
    from harness.anclar import seccion_admisible
    ok(seccion_admisible("8.6", "ajuste_renal"), "8.6 es la seccion renal")
    ok(seccion_admisible("8.6.1", "ajuste_renal"), "una subseccion hija cuenta")
    ok(seccion_admisible("8", "ajuste_renal"), "la seccion padre cuenta")
    ok(not seccion_admisible("7", "ajuste_renal"),
       "la seccion de interacciones NO puede contener un corte renal")
    ok(not seccion_admisible("12.1", "dosis"),
       "el mecanismo de accion no es donde vive una dosis")
    ok(seccion_admisible("12.1", "mecanismo"), "12.1 si es el mecanismo")
    ok(seccion_admisible("", "dosis"),
       "sin subseccion identificada no se rechaza: la ausencia de estructura no es "
       "prueba de que la cifra este fuera de lugar")


def test_cifra_en_subseccion_equivocada_se_descarta():
    doc = {"results": [{
        "openfda": {"spl_set_id": ["x"]},
        # el corte renal real vive en 8.6; el 60 de la seccion 7 es otra cosa
        "use_in_specific_populations": [
            "7 Drug Interactions. Coadministration increased exposure by 60 percent. "
            "8.6 Renal Impairment. No adjustment is needed if the eGFR is 30 mL/min or greater."
        ],
    }]}
    f = FetcherOffline({"farmaco-x": doc})
    r = anclar_en_etiqueta("farmaco-x", Magnitud(Clase.TFG, 30, "ml/min/1.73m2"), f,
                           tipo_hecho="ajuste_renal")
    ok(r.ancla.verificada, f"debe anclar el corte que SI esta en 8.6: {r.motivo}")
    ok("PLR 8.6" in r.ruta, f"la ruta debe registrar la subseccion: {r.ruta}")


def test_varias_magnitudes_sin_pista_no_se_resuelve():
    """Si la seccion trae dos dosis que no concuerdan, elegir una seria inventar."""
    doc = {"results": [{
        "openfda": {"spl_set_id": ["x"]},
        "dosage_and_administration": [
            "The starting dose is 25 mg once daily. The maximum dose is 200 mg once daily."
        ],
    }]}
    r = anclar_en_etiqueta("farmaco-ambiguo", p1("50 mg al dia"),
                           FetcherOffline({"farmaco-ambiguo": doc}), tipo_hecho="dosis")
    ok(not r.ancla.verificada, "con magnitudes en conflicto no se auto-verifica")
    ok(r.coincide is None, f"no se declara coincidencia ni contradiccion: {r.coincide}")
    ok("desambiguar" in r.motivo, f"debe pedir una pista: {r.motivo}")


def test_etiqueta_inexistente():
    r = anclar_en_etiqueta("farmaco-inexistente", p1("10 mg"), F)
    ok(not r.ancla.verificada, "sin etiqueta no hay ancla")


# ------------------------------------------------------------- frescura e integracion
def test_necesita_refresco():
    from harness.hecho import Ancla
    a = Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador="NCT03036150",
              fecha_consulta="2026-01-01", verificada=True)
    ok(necesita_refresco(a, "2026-03-15", dias=30),
       "a mas de 30 dias debe pedir refresco")
    ok(not necesita_refresco(a, "2026-01-10", dias=30),
       "a 9 dias no debe pedir refresco")

    b = Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador="NCT1", verificada=True)
    ok(necesita_refresco(b, "2026-01-01"),
       "sin fecha de consulta siempre necesita refresco")


def test_aplicar_anclaje_es_destructivo():
    from harness.hecho import Ancla
    h = Hecho("x", ClaseHecho.EFECTO, Poblacion("y"),
              anclas=[Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador="inventada",
                            verificada=True)])
    ok(h.techo() == "VERDE", "antes del anclaje el techo lo da el ancla declarada")

    # un NCT mal formado: el anclaje ni lo intenta, asi que no hay ancla real
    r = anclar_en_ensayo("DAPA-CKD", p1("HR 0.61"), F)
    aplicar_anclaje(h, [r])
    ok(len(h.anclas) == 1 and not h.anclas[0].verificada,
       "el anclaje real reemplaza el ancla declarada sin comprobar")
    ok(h.anclas[0].localizador == "DAPA-CKD",
       f"el localizador inventado se reemplaza por el real intentado: {h.anclas[0].localizador}")
    ok(h.techo() == "AMBAR",
       f"sin ancla verificada el techo baja a AMBAR: {h.techo()}")
    ok(h.diagnostico["anclaje"][0]["motivo"], "debe quedar el rastro del intento")


# ------------------------------------------- anclaje en articulo de PMC
# Documento con la forma real del bucket: metadatos en JSON y texto plano aparte.
ART_META_OK = {"pmcid": "PMC9491404", "version": 1, "license_code": "CC BY",
               "is_pmc_openaccess": True, "is_retracted": False,
               "is_historical_ocr": False, "is_manuscript": False}
ART_META_NC = {"pmcid": "PMC6518930", "version": 1, "license_code": "CC BY-NC-ND",
               "is_pmc_openaccess": True, "is_retracted": False,
               "is_historical_ocr": False, "is_manuscript": False}
ART_META_RETR = {"pmcid": "PMC7777777", "version": 1, "license_code": "CC BY",
                 "is_pmc_openaccess": True, "is_retracted": True,
                 "is_historical_ocr": False, "is_manuscript": False}
ART_TXT = ("RESULTS. SGLT2i were associated with a 34% reduction in the risk of a "
           "kidney composite outcome (HR 0.66, 95% CI 0.58-0.75). All-cause mortality "
           "was also lower (HR 0.86, 95% CI 0.77-0.96). In a subgroup analysis the "
           "effect was larger with macroalbuminuria (HR 0.57, 95% CI 0.48-0.67).")

FART = FetcherOffline(
    documentos={"PMC9491404.1.json": ART_META_OK, "PMC6518930.1.json": ART_META_NC,
                "PMC7777777.1.json": ART_META_RETR},
    textos={"PMC9491404.1.txt": ART_TXT, "PMC6518930.1.txt": ART_TXT,
            "PMC7777777.1.txt": ART_TXT},
)


def test_ancla_articulo_verifica_y_da_offset():
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("PMC9491404.1", p1("HR 0.66 (95% CI 0.58-0.75)"), FART,
                           pista="kidney")
    ok(r.ancla.verificada, f"debe anclar: {r.motivo}")
    ok("offset" in r.ruta, f"debe dar el desplazamiento exacto: {r.ruta}")
    ok(r.ancla.tipo is TipoAncla.ARTICULO_CC_BY, f"tipo: {r.ancla.tipo}")
    ok("CC BY" in r.ancla.licencia, f"debe guardar la licencia real: {r.ancla.licencia}")
    ok(len(r.ancla.cita_corta.split()) <= 21, f"cita recortada: {r.ancla.cita_corta}")
    ok("kidney" in r.ancla.cita_corta.lower(),
       f"la pista debe dirigir a la frase correcta: {r.ancla.cita_corta}")


def test_la_pista_distingue_el_subgrupo_del_primario():
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("PMC9491404.1", p1("HR 0.57 (95% CI 0.48-0.67)"), FART,
                           pista="macroalbuminuria")
    ok(r.ancla.verificada, f"debe anclar el subgrupo pedido: {r.motivo}")
    ok("macroalbuminuria" in r.ancla.cita_corta.lower(),
       f"y venir de la frase del subgrupo: {r.ancla.cita_corta}")


def test_licencia_se_revisa_antes_de_leer_el_contenido():
    """Un ancla en un articulo que ORIONS no puede usar es PEOR que no tener
    ancla: parece trazabilidad y es una infraccion con nombre propio."""
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("PMC6518930.1", p1("HR 0.66 (95% CI 0.58-0.75)"), FART)
    ok(not r.ancla.verificada, "CC BY-NC-ND no puede anclar")
    ok("compuerta de licencias rechaza" in r.motivo, f"motivo: {r.motivo}")
    ok("No se leyo el contenido" in r.motivo,
       f"y debe constar que no se abrio el documento: {r.motivo}")
    ok(not r.candidatos, "no debe haber candidatos: nunca se parseo el texto")


def test_retractado_no_ancla_aunque_sea_cc_by():
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("PMC7777777.1", p1("HR 0.66 (95% CI 0.58-0.75)"), FART)
    ok(not r.ancla.verificada, "un articulo retractado nunca ancla un hecho clinico")
    ok("retractado" in r.motivo, f"motivo: {r.motivo}")


def test_cifra_ausente_reporta_lo_que_si_hay():
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("PMC9491404.1", p1("HR 0.39 (95% CI 0.30-0.50)"), FART)
    ok(not r.ancla.verificada, "una cifra que no esta no se ancla")
    ok(r.candidatos, "debe reportar las magnitudes que si hallo, para el revisor")
    ok("0.66" in str(r.candidatos) or "0.86" in str(r.candidatos),
       f"los candidatos deben ser los reales del texto: {r.candidatos[:2]}")


def test_pmcid_mal_formado():
    from harness.anclar import anclar_en_articulo
    r = anclar_en_articulo("9491404", p1("HR 0.66"), FART)
    ok(not r.ancla.verificada, "un PMCID sin prefijo no se consulta")
    ok("no tiene la forma" in r.motivo, f"motivo: {r.motivo}")


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
