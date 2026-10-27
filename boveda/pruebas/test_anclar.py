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
    r = anclar_en_ensayo("NCT03036150", p1("HR 0.39"), F, desenlace="renal compuesto")
    ok(not r.ancla.verificada, "no debe verificar una cifra que no esta")
    ok(r.coincide is Acuerdo.DISCREPANTE, f"debe discrepar: {r.coincide}")
    ok(r.candidatos and len(r.candidatos) >= 1,
       "debe devolver lo que si encontro, para el revisor humano")
    ok("0.61" in str(r.candidatos), f"los candidatos deben incluir el valor real: {r.candidatos}")


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
    ok(not r.ancla.verificada, "una dosis diez veces mayor no debe verificar")
    ok(r.candidatos, "debe reportar las magnitudes que si parseo")


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

    r = anclar_en_ensayo("NCT03036150", p1("HR 0.39"), F, desenlace="renal compuesto")
    aplicar_anclaje(h, [r])
    ok(len(h.anclas) == 1 and not h.anclas[0].verificada,
       "el anclaje real reemplaza el ancla declarada sin comprobar")
    ok(h.techo() == "AMBAR",
       f"sin ancla verificada el techo baja a AMBAR: {h.techo()}")
    ok(h.diagnostico["anclaje"][0]["motivo"], "debe quedar el rastro del intento")


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
