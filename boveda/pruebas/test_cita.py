"""Pruebas de la cita verbatim.

Cada caso corresponde a una de las siete reglas duras que salieron de la
investigacion de rutas de acceso. La idea central que se prueba: una cita NO se
puede fabricar, solo cortar de la fuente."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.cita import (
    Atribucion, MAX_CITAS_CONSECUTIVAS, MAX_PALABRAS_POR_CITA, MotivoRechazoCita,
    PresupuestoDeCita, REGLAS_DURAS, TECHO_PALABRAS_POR_OBRA, TipoObjeto,
    detectar_traduccion, extraer, huella_documento, localizar, verificar_integridad,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


# Documento fuente simulando una guia: recomendaciones separadas por material.
def _relleno(n):
    return " " + " ".join([f"Rationale paragraph {i} with supporting evidence."
                           for i in range(n)]) + " "


# Cuatro recomendaciones bien separadas: hace falta que exista una region lejana
# a las tres primeras para poder probar la contiguidad por separado de la
# dispersion.
DOC = (
    "KDIGO 2024 Clinical Practice Guideline for CKD."
    + _relleno(40) +
    "Recommendation 1.1.1: We recommend using cystatin C to confirm eGFR in adults "
    "when an accurate estimate is required for clinical decision making (1B)."
    + _relleno(60) +
    "Recommendation 3.1.1: We recommend treating adults with CKD and type 2 diabetes "
    "with an SGLT2 inhibitor (1A)."
    + _relleno(60) +
    "Recommendation 4.2.1: We suggest a target systolic blood pressure guided by "
    "standardized office measurement in adults with high blood pressure and CKD (2B)."
    + _relleno(60) +
    "Recommendation 5.1.1: We recommend statin-based therapy in adults aged 50 years "
    "and older with CKD not treated with dialysis (1A)."
)

ATR = Atribucion(obra="KDIGO 2024 Clinical Practice Guideline for CKD",
                 emisor="KDIGO", anio="2024", localizador="doi:10.1016/j.kint.2023.10.018",
                 url="https://doi.org/10.1016/j.kint.2023.10.018",
                 licencia="CC BY-NC-ND 4.0")


def coords(frase):
    c = localizar(DOC, frase)
    ok(c is not None, f"la frase debe estar en el documento: {frase[:40]!r}")
    return c


# ================================================ la idea central
def test_una_cita_no_se_puede_fabricar():
    """`extraer` no recibe el texto de la cita: recibe el documento y las
    coordenadas. Es la unica puerta, y existe para que sea estructuralmente
    imposible que un texto generado pase por cita."""
    import inspect
    params = set(inspect.signature(extraer).parameters)
    ok("texto_fuente" in params and "inicio" in params and "fin" in params,
       f"extraer debe recibir el documento y coordenadas: {params}")
    ok("texto" not in params and "cita" not in params,
       f"y NO debe recibir el texto de la cita: {params}")


def test_la_parafrasis_no_se_localiza():
    """El None de localizar es informacion valiosa: significa que lo que se creia
    una cita es una parafrasis, y una parafrasis presentada como cita viola la
    clausula de no alteracion y ademas puede estar alucinada."""
    ok(localizar(DOC, "We recommend treating adults with CKD and type 2 diabetes") is not None,
       "la frase literal si se localiza")
    ok(localizar(DOC, "Se recomienda tratar a los adultos con ERC y diabetes tipo 2") is None,
       "la traduccion no es el texto de la fuente")
    ok(localizar(DOC, "KDIGO recommends SGLT2 inhibitors for diabetic CKD patients") is None,
       "una parafrasis fiel tampoco esta en la fuente, y eso es el punto")


def test_extraer_y_verificar():
    ini, fin = coords("We recommend treating adults with CKD and type 2 diabetes "
                      "with an SGLT2 inhibitor (1A).")
    r = extraer(DOC, ini, fin, ATR, idioma="en")
    ok(bool(r), f"debe extraer: {r.motivo}")
    ok("SGLT2" in r.cita.texto, f"el texto debe ser el de la fuente: {r.cita.texto[:50]}")
    ok("(1A)" in r.cita.texto,
       "la etiqueta de nivel de evidencia se conserva: es justo lo que no se puede derivar")
    ok(r.cita.huella(), "debe tener huella")
    v = verificar_integridad(r.cita, DOC)
    ok(bool(v), f"debe verificar integra: {v.motivo}")


def test_integridad_detecta_alteracion():
    ini, fin = coords("We recommend using cystatin C to confirm eGFR in adults")
    r = extraer(DOC, ini, fin, ATR, idioma="en")
    alterada = type(r.cita)(
        texto=r.cita.texto.replace("recommend", "suggest"),
        atribucion=r.cita.atribucion, inicio=r.cita.inicio, fin=r.cita.fin,
        idioma=r.cita.idioma, tipo=r.cita.tipo, huella_fuente=r.cita.huella_fuente)
    v = verificar_integridad(alterada, DOC)
    ok(not v, "una cita alterada no debe verificar")
    ok(v.codigo is MotivoRechazoCita.ALTERADA, f"codigo: {v.codigo}")
    ok("parafrasis presentada como cita" in v.motivo, f"motivo: {v.motivo[:120]}")


def test_integridad_detecta_cambio_de_fuente():
    ini, fin = coords("We recommend using cystatin C")
    r = extraer(DOC, ini, fin, ATR, idioma="en")
    v = verificar_integridad(r.cita, DOC + " Addendum: new recommendation added.")
    ok(not v, "si el documento cambio hay que re-extraer")
    ok("documento fuente cambio" in v.motivo, f"motivo: {v.motivo[:90]}")


# ================================================ las siete reglas duras
def test_solo_texto_no_tablas_ni_algoritmos():
    ini, fin = coords("We recommend using cystatin C")
    for t in (TipoObjeto.TABLA, TipoObjeto.FIGURA, TipoObjeto.ALGORITMO,
              TipoObjeto.DIAGRAMA):
        r = extraer(DOC, ini, fin, ATR, idioma="en", tipo=t)
        ok(not r, f"el derecho de cita no cubre {t.value}")
        ok(r.codigo is MotivoRechazoCita.OBJETO_NO_CUBIERTO, f"codigo para {t.value}")
    r = extraer(DOC, ini, fin, ATR, idioma="en", tipo=TipoObjeto.TEXTO)
    ok(bool(r), "el texto si esta cubierto")


def test_traducir_no_es_citar():
    """La restriccion de producto mas incomoda, y no tiene vuelta."""
    ini, fin = coords("We recommend treating adults with CKD and type 2 diabetes")
    r = extraer(DOC, ini, fin, ATR, idioma="en")
    aviso = detectar_traduccion(r.cita, "es")
    ok(aviso is not None, "mostrar en espanol una cita en ingles debe avisarse")
    ok("obra derivada" in aviso, f"debe decir por que: {aviso[:110]}")
    ok("articulo 27" in aviso, "y citar la base legal")
    ok(detectar_traduccion(r.cita, "en") is None, "en su idioma original no hay problema")


def test_atribucion_incompleta_no_es_cita():
    ini, fin = coords("We recommend using cystatin C")
    for falta in ("obra", "emisor", "anio", "localizador"):
        datos = {"obra": "X", "emisor": "Y", "anio": "2024", "localizador": "doi:1"}
        datos[falta] = ""
        r = extraer(DOC, ini, fin, Atribucion(**datos), idioma="en")
        ok(not r, f"sin {falta} no hay cita amparada")
        ok(r.codigo is MotivoRechazoCita.ATRIBUCION_INCOMPLETA, f"codigo sin {falta}")
    ok(Atribucion(obra="X", emisor="Y", anio="2024", localizador="doi:1").completa(),
       "con los cuatro campos si esta completa")


def test_cita_demasiado_larga():
    r = extraer(DOC, 0, 1200, ATR, idioma="en")
    ok(not r, "un fragmento largo no es una cita")
    ok(r.codigo is MotivoRechazoCita.DEMASIADO_LARGA, f"codigo: {r.codigo}")
    ok(str(MAX_PALABRAS_POR_CITA) in r.motivo, "debe decir el maximo")


def test_advertencias_de_licencia():
    ini, fin = coords("We recommend treating adults with CKD and type 2 diabetes")
    r = extraer(DOC, ini, fin, ATR, idioma="en")
    av = " ".join(r.advertencias)
    ok("NO COMERCIAL" in av,
       f"debe advertir que la licencia es no comercial: {r.advertencias}")
    ok("parafrasear" in av,
       f"y que al prohibir derivados el modelo no puede reescribirla: {r.advertencias}")


def test_reglas_duras_documentadas():
    ok(len(REGLAS_DURAS) >= 7, f"las siete reglas deben estar escritas: {len(REGLAS_DURAS)}")
    todo = " ".join(REGLAS_DURAS).lower()
    for clave in ("conjuntas", "obra citada", "densidad", "solo texto", "traducir",
                  "adyacente", "clickwrap"):
        ok(clave in todo, f"falta la regla sobre {clave}")


# ================================================ densidad y contiguidad
def test_techo_por_obra():
    p = PresupuestoDeCita(obra="KDIGO 2024")
    ini, fin = coords("We recommend using cystatin C")
    cita = extraer(DOC, ini, fin, ATR, idioma="en").cita
    p.palabras_usadas = TECHO_PALABRAS_POR_OBRA - 2
    r = p.cabe(cita)
    ok(not r, "pasado el techo no cabe")
    ok(r.codigo is MotivoRechazoCita.TECHO_DE_OBRA_EXCEDIDO, f"codigo: {r.codigo}")
    ok("argentina" in r.motivo.lower(), f"debe decir de donde sale el techo: {r.motivo[:100]}")


def test_contiguidad_rompe_la_racha_con_material_propio():
    """Lo que la ley castiga es que los pasajes sean TANTOS Y SEGUIDOS."""
    p = PresupuestoDeCita(obra="KDIGO 2024")
    frases = ["We recommend using cystatin C to confirm eGFR in adults",
              "We recommend treating adults with CKD and type 2 diabetes",
              "We suggest a target systolic blood pressure guided by"]
    citas = []
    for f in frases:
        i, j = coords(f)
        citas.append(extraer(DOC, i, j, ATR, idioma="en").cita)

    for c in citas:
        ok(bool(p.agregar(c)), f"las primeras citas dispersas si caben")
    ok(p.consecutivas == MAX_CITAS_CONSECUTIVAS,
       f"debe contar la racha: {p.consecutivas}")

    # La cuarta cita esta LEJOS de las tres anteriores, para que la rechace la
    # regla de contiguidad y no la de dispersion, que es la que se prueba aqui.
    i4, j4 = coords("We recommend statin-based therapy in adults aged 50 years")
    cuarta = extraer(DOC, i4, j4, ATR, idioma="en").cita
    r = p.cabe(cuarta)
    ok(not r, "la cuarta seguida no cabe")
    ok(r.codigo is MotivoRechazoCita.DEMASIADO_SEGUIDAS, f"codigo: {r.codigo}")
    ok("tantos y seguidos" in r.motivo.lower(), f"debe citar el criterio: {r.motivo[:110]}")

    p.material_propio()
    ok(bool(p.cabe(cuarta)), "material propio en medio rompe la racha y vuelve a caber")


def test_dispersion_obligatoria():
    p = PresupuestoDeCita(obra="KDIGO 2024")
    i, j = coords("We recommend using cystatin C to confirm eGFR in adults")
    primera = extraer(DOC, i, j, ATR, idioma="en").cita
    p.agregar(primera)
    p.material_propio()
    # una segunda cita pegada a la primera
    r = p.cabe(extraer(DOC, i + 10, i + 60, ATR, idioma="en").cita)
    ok(not r, "dos citas contiguas del mismo pasaje no deben permitirse")
    ok(r.codigo is MotivoRechazoCita.DEMASIADO_CERCA, f"codigo: {r.codigo}")


def test_informe_mide_el_tramo_mas_denso():
    p = PresupuestoDeCita(obra="KDIGO 2024")
    for f in ["We recommend using cystatin C to confirm eGFR in adults",
              "We recommend treating adults with CKD and type 2 diabetes"]:
        i, j = coords(f)
        p.agregar(extraer(DOC, i, j, ATR, idioma="en").cita)
        p.material_propio()
    inf = p.informe()
    ok(inf["n_citas"] == 2, f"debe contar las citas: {inf}")
    ok(inf["palabras_usadas"] > 0, "y las palabras")
    ok("palabras_en_el_tramo_mas_denso" in inf,
       f"y medir la densidad, que es el criterio real: {list(inf)}")
    ok(inf["proporcion_del_techo"] < 0.1, f"dos citas usan poco del techo: {inf}")


def test_coordenadas_invalidas():
    for i, j in [(-1, 50), (50, 10), (0, 0), (10, len(DOC) + 100)]:
        r = extraer(DOC, i, j, ATR, idioma="en")
        ok(not r, f"coordenadas invalidas [{i},{j}] deben rechazarse")


def test_huella_de_documento_es_estable():
    ok(huella_documento(DOC) == huella_documento(DOC), "deterministica")
    ok(huella_documento(DOC) != huella_documento(DOC + " "), "sensible al cambio")


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
