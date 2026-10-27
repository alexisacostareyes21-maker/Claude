"""Pruebas de la frontera educacion / apoyo a la decision clinica.

Cada caso corresponde a una regla que el analisis regulatorio adversarial dejo
como obligatoria. La frontera no la fija el contenido: la fija la voz y el
referente."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.voz import (
    Emisor, Referente, atribuir, entrada_admisible, formas_normativas, revisar,
    revisar_pluralidad, revisar_referente, revisar_vista, revisar_voz,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


NOM = Emisor("NOM-030-SSA2-2009", "numeral 7.4", "2009")
ENSAYO = Emisor("ClinicalTrials.gov", "NCT03036150", "2026-03-15")
INCOMPLETO = Emisor("KDIGO", "", "2024")


# ------------------------------------------------------- modo deontico
def test_detecta_formas_normativas():
    casos = [
        "el paciente debe recibir un iSGLT2",
        "hay que ajustar la dosis",
        "se recomienda iniciar tratamiento",
        "inicie un inhibidor de SGLT2",
        "administre sulfato de magnesio",
        "suspenda el farmaco",
        "la dosis es de 10 mg al dia",
        "el objetivo es menor de 130",
        "es el tratamiento de primera linea",
        "es el farmaco de eleccion",
        "es el mejor esquema disponible",
    ]
    for c in casos:
        ok(formas_normativas(c), f"debe detectar la forma normativa en: {c!r}")


def test_enunciados_descriptivos_pasan():
    limpios = [
        "el ensayo inscribio pacientes con eGFR entre 25 y 75 mL/min/1.73m2",
        "en 4304 participantes el desenlace renal compuesto mostro HR 0.61",
        "la inhibicion de SGLT2 reduce la reabsorcion proximal de sodio",
        "la etiqueta registra una dosis de 10 mg en su seccion 2.1",
        "tres anclas independientes respaldan esta cifra",
    ]
    for c in limpios:
        ok(not formas_normativas(c), f"un enunciado descriptivo no debe marcarse: {c!r}")


def test_normativo_sin_atribuir_se_bloquea():
    h = revisar_voz("la meta de presion es menor de 130/80")
    ok(h, "un normativo en voz propia debe bloquearse")
    ok(h[0].codigo == "NORMATIVO_SIN_ATRIBUIR", f"codigo: {h[0].codigo}")
    ok(h[0].gravedad == "alta", "es de gravedad alta")
    ok("transcribe" in h[0].detalle, f"debe decir que reformular: {h[0].detalle}")


def test_normativo_atribuido_pasa():
    """La misma cifra, dicha en voz propia o atribuida, cae a lados distintos."""
    texto = "la meta de presion es menor de 130/80"
    ok(revisar_voz(texto), "en voz propia se bloquea")
    ok(not revisar_voz(texto, NOM), "con atribucion completa es cita, no emision")


def test_atribucion_incompleta_no_salva():
    ok(revisar_voz("se recomienda iniciar un iSGLT2", INCOMPLETO),
       "una atribucion sin ancla equivale a emitir en voz propia")
    h = revisar_voz("se recomienda iniciar un iSGLT2", INCOMPLETO)
    ok("ancla" in h[0].detalle, f"debe decir que falta: {h[0].detalle}")
    ok(not Emisor("KDIGO", "", "2024").completo(), "un emisor sin ancla no esta completo")
    ok(Emisor("KDIGO", "cap 3", "2024").completo(), "con los tres campos si")


def test_atribuir_reescribe():
    r = atribuir("La meta de presion es menor de 130/80.", NOM)
    ok(r.startswith("Segun NOM-030-SSA2-2009"), f"debe empezar atribuyendo: {r}")
    ok("numeral 7.4" in r and "2009" in r, f"debe llevar ancla y fecha: {r}")
    ok(not revisar_voz(r, NOM), "el texto reescrito debe pasar la revision")


# ------------------------------------------------------- referente
def test_detecta_persona_concreta():
    casos = [
        "mi paciente tiene eGFR de 28",
        "tengo un paciente con ERC",
        "que le doy a este paciente",
        "cuanto le indico",
        "paciente de 54 anos con albuminuria",
        "en mi caso particular",
    ]
    for c in casos:
        h = revisar_referente(c)
        ok(h, f"debe detectar la referencia individual en: {c!r}")
        ok(h[0].codigo == "REFERENTE_INDIVIDUAL", f"codigo para {c!r}: {h[0].codigo}")


def test_poblacion_pasa():
    limpios = [
        "en adultos con ERC y albuminuria sobre bloqueo del SRAA",
        "en la poblacion inscrita en el ensayo",
        "en personas mayores de 65 anos con diabetes tipo 2",
    ]
    for c in limpios:
        ok(not revisar_referente(c, Referente.POBLACION_PICO),
           f"un enunciado de poblacion no debe marcarse: {c!r}")


def test_enum_de_referente_es_cerrado():
    ok(len(list(Referente)) == 3, f"solo tres valores: {list(Referente)}")
    ok("paciente" not in [r.value for r in Referente],
       "el valor 'paciente' no debe existir en el enum")


def test_compuerta_de_entrada():
    malo = [
        "mi paciente de 54 anos con eGFR 28, que dosis le doy",
        "tengo una paciente con preeclampsia",
        "hombre de 60 anos con creatinina de 2.1 mg/dL, que hago",
    ]
    for c in malo:
        adm, motivo = entrada_admisible(c)
        ok(not adm, f"debe rechazarse: {c!r}")
        ok(motivo, f"debe dar motivo: {c!r}")

    bueno = [
        "cual es la ventana de inscripcion del ensayo renal con dapagliflozina",
        "por que un iSGLT2 reduce la hiperfiltracion",
        "que dice la NOM-030 sobre las metas de presion",
        "como se estadifica la ERC por eGFR y albuminuria",
    ]
    for c in bueno:
        adm, _ = entrada_admisible(c)
        ok(adm, f"una pregunta de poblacion debe aceptarse: {c!r}")


def test_triple_edad_sexo_cifra():
    adm, motivo = entrada_admisible("mujer de 48 anos con HbA1c de 9.2 %")
    ok(not adm, "edad, sexo y cifra en la misma consulta describe a una persona")
    ok("persona concreta" in motivo, f"motivo: {motivo}")

    adm2, _ = entrada_admisible("en mujeres de 48 anos, que dice la evidencia")
    ok(adm2, "sin cifra de laboratorio no es la descripcion de un caso")


# ------------------------------------------------------- derivacion no colapsable
def test_vistas_prohibidas():
    for v in ("resumen_ejecutivo", "que hacer", "respuesta-rapida", "TLDR",
              "conducta", "recomendacion_final"):
        h = revisar_vista(v, muestra_derivacion=True, anclas_visibles=3)
        ok(any(x.codigo == "VISTA_COLAPSADA" for x in h),
           f"la vista {v!r} debe bloquearse: {[x.codigo for x in h]}")


def test_vista_legitima_pasa():
    h = revisar_vista("derivacion_completa", muestra_derivacion=True, anclas_visibles=3)
    ok(not h, f"una vista con derivacion y anclas debe pasar: {h}")


def test_derivacion_oculta_se_bloquea():
    h = revisar_vista("ficha", muestra_derivacion=False, anclas_visibles=3)
    ok(any(x.codigo == "DERIVACION_OCULTA" for x in h),
       "ocultar la derivacion destruye el criterio de revision independiente")


def test_anclas_ocultas_se_bloquean():
    h = revisar_vista("ficha", muestra_derivacion=True, anclas_visibles=0)
    ok(any(x.codigo == "ANCLAS_OCULTAS" for x in h),
       "sin ancla a la vista no hay verificacion independiente posible")


# ------------------------------------------------------- pluralidad
def test_salida_unica_se_bloquea():
    h = revisar_pluralidad([{"texto": "iSGLT2", "ancla": "NCT1"}])
    ok(any(x.codigo == "SALIDA_UNICA" for x in h),
       "una sola opcion es una recomendacion, no material de estudio")


def test_dos_opciones_con_ancla_pasan():
    h = revisar_pluralidad([{"texto": "a", "ancla": "NCT1"},
                            {"texto": "b", "ancla": "NCT2"}])
    ok(not h, f"dos opciones ancladas deben pasar: {h}")


def test_opcion_sin_ancla_se_marca():
    h = revisar_pluralidad([{"texto": "a", "ancla": "NCT1"}, {"texto": "b"}])
    ok(any(x.codigo == "OPCION_SIN_ANCLA" for x in h), "debe marcar la opcion sin ancla")
    ok(all(x.gravedad != "alta" for x in h if x.codigo == "OPCION_SIN_ANCLA"),
       "pero es de gravedad media: se corrige, no bloquea el producto")


# ------------------------------------------------------- integracion
def test_revision_completa_del_caso_malo():
    r = revisar(
        "Para mi paciente debe iniciar un iSGLT2, es el de primera linea.",
        nombre_vista="respuesta_rapida", muestra_derivacion=False, anclas_visibles=0,
        opciones=[{"texto": "iSGLT2"}],
    )
    ok(not r.del_lado_educativo, "este caso esta claramente del lado regulado")
    codigos = {h.codigo for h in r.hallazgos}
    for esperado in ("NORMATIVO_SIN_ATRIBUIR", "REFERENTE_INDIVIDUAL",
                     "VISTA_COLAPSADA", "DERIVACION_OCULTA", "ANCLAS_OCULTAS",
                     "SALIDA_UNICA"):
        ok(esperado in codigos, f"debe detectar {esperado}: {codigos}")


def test_revision_completa_del_caso_bueno():
    r = revisar(
        atribuir("en adultos con ERC y albuminuria se recomienda un iSGLT2", NOM),
        emisor=NOM, referente=Referente.POBLACION_PICO,
        nombre_vista="derivacion_completa", muestra_derivacion=True, anclas_visibles=3,
        opciones=[{"texto": "iSGLT2", "ancla": "NCT03036150"},
                  {"texto": "finerenona", "ancla": "NCT02540993"}],
    )
    ok(r.del_lado_educativo,
       f"el caso atribuido, plural y con derivacion debe pasar: {r.dict()}")


def test_reporte_serializable():
    d = revisar("debe iniciar tratamiento").dict()
    ok("del_lado_educativo" in d and "hallazgos" in d, f"debe serializarse: {list(d)}")


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
