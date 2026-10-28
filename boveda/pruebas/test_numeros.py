"""Pruebas del motor de normalizacion numerica.

Ejecutar:  python3 -m pruebas.test_numeros        (desde /home/user/Claude/boveda)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import (  # noqa: E402
    Acuerdo, Clase, Comparador, Magnitud,
    agrupar, comparar, convertir_concentracion, orden_de_magnitud_distinto, parsear,
)

FALLOS = []
PASES = 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def p1(texto, **kw):
    """Parsea y devuelve la primera magnitud, o None."""
    r = parsear(texto, **kw)
    return r[0] if r else None


# ---------------------------------------------------------------- parseo basico
def test_parseo_efecto():
    m = p1("HR 0.61 (95% CI 0.51-0.72)")
    ok(m is not None and m.clase is Clase.RAZON_RIESGO, "HR no reconocido")
    ok(m and abs(m.valor - 0.61) < 1e-9, f"HR valor mal: {m}")
    ok(m and m.ic_inf == 0.51 and m.ic_sup == 0.72, f"IC mal: {m}")

    # coma decimal, notacion espanola
    m = p1("HR 0,61 (IC 95% 0,51-0,72)")
    ok(m is not None and abs(m.valor - 0.61) < 1e-9, f"coma decimal mal: {m}")
    ok(m and m.ic_inf == 0.51, f"IC con coma mal: {m}")

    m = p1("hazard ratio de 0.73")
    ok(m is not None and abs(m.valor - 0.73) < 1e-9, f"alias largo mal: {m}")

    m = p1("reduccion del riesgo relativo del 39%")
    ok(m is not None and m.clase is Clase.REDUCCION_REL, f"RRR no reconocido: {m}")
    ok(m and abs(m.valor - 0.39) < 1e-9, f"RRR valor mal: {m}")

    m = p1("NNT de 19")
    ok(m is not None and m.clase is Clase.NNT and m.valor == 19, f"NNT mal: {m}")


def test_parseo_umbrales():
    m = p1("eGFR >= 25 mL/min/1.73m2")
    ok(m is not None and m.clase is Clase.TFG, f"TFG no reconocida: {m}")
    ok(m and m.valor == 25 and m.comparador is Comparador.MAYOR_IGUAL, f"TFG comparador mal: {m}")

    m = p1("eGFR ≥ 25 mL/min/1,73 m²")
    ok(m is not None and m.valor == 25, f"TFG unicode mal: {m}")

    mags = parsear("meta de presion arterial <130/80 mmHg")
    ok(len(mags) == 2, f"presion compuesta mal: {mags}")
    if len(mags) == 2:
        ok(mags[0].valor == 130 and mags[0].etiqueta == "sistolica", f"sistolica mal: {mags[0]}")
        ok(mags[1].valor == 80 and mags[1].etiqueta == "diastolica", f"diastolica mal: {mags[1]}")
        ok(mags[0].comparador is Comparador.MENOR, f"comparador presion mal: {mags[0]}")

    m = p1("HbA1c menor de 7%")
    ok(m is not None and m.clase is Clase.PROPORCION and m.valor == 7, f"porcentaje mal: {m}")

    m = p1("glucosa de 126 mg/dL", analito="glucosa")
    ok(m is not None and m.clase is Clase.CONCENTRACION and m.valor == 126, f"concentracion mal: {m}")


def test_parseo_dosis():
    m = p1("10 mg una vez al dia")
    ok(m is not None and m.clase is Clase.DOSIS, f"dosis no reconocida: {m}")
    ok(m and m.valor == 10 and m.por_dia == 10, f"dosis diaria mal: {m}")

    m = p1("5 mg dos veces al dia")
    ok(m is not None and m.por_dia == 10, f"BID mal: {m}")

    # conversion de unidad a canonica
    m = p1("1 g cada 8 h")
    ok(m is not None and m.valor == 1000 and m.unidad == "mg", f"g->mg mal: {m}")
    ok(m and m.por_dia == 3000, f"TID con gramos mal: {m}")

    m = p1("500 mcg al dia")
    ok(m is not None and abs(m.valor - 0.5) < 1e-9, f"mcg->mg mal: {m}")


def test_rango():
    m = p1("entre 70 y 100 mg/dL", analito="glucosa")
    ok(m is not None and m.comparador is Comparador.RANGO, f"rango no reconocido: {m}")
    ok(m and m.valor == 70 and m.valor_sup == 100, f"rango valores mal: {m}")


def test_millares_vs_decimal():
    from harness.numeros import _a_float
    ok(_a_float("0,61") == 0.61, "0,61 debe ser decimal")
    ok(_a_float("1,234") == 1234.0, "1,234 debe ser millares")
    ok(_a_float("1.234,5") == 1234.5, "1.234,5 formato europeo")
    ok(_a_float("0,500") == 0.5, "0,500 con cero inicial es decimal")
    ok(_a_float("12,5") == 12.5, "12,5 decimal")


# ---------------------------------------------------------------- equivalencias
def test_equivalencia_hr_rrr():
    hr = p1("HR 0.61")
    rrr = p1("reduccion del riesgo relativo del 39%")
    ok(comparar(hr, rrr) is Acuerdo.EQUIVALENTE,
       f"HR 0.61 debe equivaler a RRR 39%: {comparar(hr, rrr)}")

    rrr_mal = p1("reduccion del riesgo relativo del 61%")
    ok(comparar(hr, rrr_mal) is Acuerdo.DISCREPANTE,
       "HR 0.61 no equivale a RRR 61% (error clasico de interpretacion)")


def test_equivalencia_nnt_arr():
    nnt = p1("NNT de 20")
    arr = Magnitud(Clase.REDUCCION_ABS, 0.05, bruto="ARR 5%")
    ok(comparar(nnt, arr) is Acuerdo.EQUIVALENTE, f"NNT 20 = ARR 5%: {comparar(nnt, arr)}")

    # NNT frente a RRR no es decidible sin riesgo basal: debe ser INCOMPARABLE
    rrr = p1("RRR 39%")
    ok(comparar(nnt, rrr) is Acuerdo.INCOMPARABLE,
       "NNT frente a RRR requiere riesgo basal: debe ser incomparable, no un acuerdo falso")


def test_concentracion_molar():
    mg = Magnitud(Clase.CONCENTRACION, 100, "mg/dl", analito="ldl", bruto="LDL 100 mg/dL")
    mm = Magnitud(Clase.CONCENTRACION, 2.586, "mmol/l", analito="ldl", bruto="LDL 2.59 mmol/L")
    ok(comparar(mg, mm) is Acuerdo.IDENTICO,
       f"LDL 100 mg/dL = 2.59 mmol/L: {comparar(mg, mm)}")

    conv = convertir_concentracion(mm, "mg/dl")
    ok(conv is not None and abs(conv.valor - 100) < 1.0, f"conversion molar mal: {conv}")


def test_solape_ic():
    a = p1("HR 0.61 (95% CI 0.51-0.72)")
    b = p1("HR 0.68 (95% CI 0.60-0.78)")
    ok(comparar(a, b) is Acuerdo.COMPATIBLE,
       f"IC que se solapan deben ser compatibles: {comparar(a, b)}")

    c = p1("HR 1.20 (95% CI 1.05-1.40)")
    ok(comparar(a, c) is Acuerdo.DISCREPANTE,
       f"IC que no se solapan deben discrepar: {comparar(a, c)}")


def test_presion_no_cruza_etiqueta():
    mags = parsear("<130/80 mmHg")
    ok(comparar(mags[0], mags[1]) is Acuerdo.INCOMPARABLE,
       "sistolica y diastolica nunca deben compararse entre si")


def test_orden_de_magnitud():
    a = p1("10 mg al dia")
    b = p1("100 mg al dia")
    ok(orden_de_magnitud_distinto(a, b), "debe detectar el error de factor 10 en dosis")
    ok(comparar(a, b) is Acuerdo.DISCREPANTE, "10 mg y 100 mg deben discrepar")

    c = p1("10 mg al dia")
    ok(not orden_de_magnitud_distinto(a, c), "misma dosis no es error de orden")


def test_unidades_distintas_incomparables():
    a = Magnitud(Clase.PROPORCION, 7, "%", bruto="7%")
    b = Magnitud(Clase.CONCENTRACION, 7, "mmol/l", analito="glucosa", bruto="7 mmol/L")
    ok(comparar(a, b) is Acuerdo.INCOMPARABLE, "clases distintas sin puente son incomparables")


# ---------------------------------------------------------------- agrupamiento
def test_agrupar_consenso():
    elic = [
        p1("HR 0.61 (95% CI 0.51-0.72)"),
        p1("hazard ratio de 0,61"),
        p1("reduccion del riesgo relativo del 39%"),
        p1("HR 0.39"),  # confabulacion: confunde HR con RRR
    ]
    grupos = agrupar([m for m in elic if m])
    ok(len(grupos) == 2, f"deben quedar 2 grupos, quedaron {len(grupos)}: "
                         f"{[[str(x) for x in g] for g in grupos]}")
    ok(len(grupos[0]) == 3, f"el grupo dominante debe tener 3 elicitaciones: {len(grupos[0])}")


def test_agrupar_dispersion():
    elic = [p1("HR 0.61"), p1("HR 0.85"), p1("HR 0.40"), p1("HR 1.10")]
    grupos = agrupar([m for m in elic if m])
    ok(len(grupos) == 4, f"valores dispersos no deben agruparse: {len(grupos)}")


def test_no_inventa():
    ok(parsear("el tratamiento mejora el desenlace") == [],
       "texto sin cifras debe devolver lista vacia, no una magnitud inventada")
    ok(parsear("") == [], "texto vacio debe devolver lista vacia")


# ------------------------------------------- texto real de la literatura
def test_punto_medio_decimal_del_lancet():
    """El Lancet y otras revistas britanicas usan punto medio como separador
    decimal. Antes de arreglarlo, "RR 0\u00b763" se parseaba como 0: corrupcion
    silenciosa, peor que no parsear, porque el valor real se perdia y quedaba un
    numero plausible y equivocado en su lugar. Se descubrio corriendo el parser
    sobre texto real de PMC, no en una prueba sintetica."""
    m = p1("RR 0\u00b763, 95%CI 0\u00b758-0\u00b769")
    ok(m is not None and abs(m.valor - 0.63) < 1e-9, f"punto medio decimal: {m}")
    ok(m and m.ic_inf == 0.58 and m.ic_sup == 0.69, f"IC con punto medio: {m}")

    m2 = p1("RR 1\u00b705 (95% CI 0\u00b795-1\u00b716)")
    ok(m2 is not None and abs(m2.valor - 1.05) < 1e-9, f"valor mayor que 1: {m2}")

    # pero el punto medio como signo de multiplicacion NO se toca
    ok(parsear("3 \u00b7 4 = 12") == [] or
       all(abs(x.valor - 34) > 1e-9 for x in parsear("3 \u00b7 4 = 12")),
       "el punto medio entre espacios no es un separador decimal")


def test_intervalo_en_ingles_sin_parentesis():
    """"HR 0.66, 95% CI 0.58-0.75" perdia el intervalo en silencio, porque el
    patron exigia parentesis cuando el porcentaje va antes de la sigla. El
    intervalo es justo lo que sostiene las comparaciones por solape."""
    for t in ["HR 0.66, 95% CI 0.58-0.75",
              "hazard ratio 0.57 (95% CI 0.48-0.67)",
              "the relative risk was 0.70 (95% confidence interval 0.58 to 0.83)",
              "HR 0,61 (IC 95% 0,51-0,72)"]:
        m = p1(t)
        ok(m is not None and m.ic_inf is not None and m.ic_sup is not None,
           f"debe capturar el intervalo en: {t!r} -> {m}")


def test_alias_en_ingles_y_abreviatura_entre_corchetes():
    """"relative risk" no estaba en los alias, solo "risk ratio" y "riesgo
    relativo": la suite estaba sesgada al espanol. Y el corchete de la
    abreviatura, como en "relative risk [RR] 0.63", bloqueaba el enlace entre el
    alias y el numero."""
    casos = [
        ("relative risk [RR] 0\u00b763, 95% confidence interval 0\u00b758-0\u00b769", 0.63),
        ("hazard ratio (HR) 0.61 (95% CI 0.51-0.72)", 0.61),
        ("rate ratio 0.89 (95% CI 0.80-0.99)", 0.89),
        ("risk ratio [RR] of 0\u00b763", 0.63),
    ]
    for t, esperado in casos:
        m = p1(t)
        ok(m is not None and abs(m.valor - esperado) < 1e-9,
           f"{t[:46]!r} debe dar {esperado}: {m}")
        ok(m is not None and m.clase is Clase.RAZON_RIESGO,
           f"y clasificarse como razon de riesgo: {m}")


def main():
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in pruebas:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FALLOS.append(f"{t.__name__} lanzo {type(e).__name__}: {e}")
    print(f"\n{PASES} aserciones pasaron, {len(FALLOS)} fallaron\n")
    for f in FALLOS:
        print("  FALLO:", f)
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
