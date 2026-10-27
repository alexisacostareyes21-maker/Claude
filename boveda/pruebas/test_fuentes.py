"""Pruebas de la compuerta de licencias. Cada caso corresponde a una trampa real
verificada en la investigacion de fuentes, no a un caso hipotetico."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.hecho import TipoAncla
from harness.fuentes import (
    CATALOGO, MotivoRechazo, PERMITIDAS, admisible_pmc, fuente_de_ancla,
    huecos_de_cobertura, obligaciones_pendientes, pendientes_de_verificar,
)

FALLOS, PASES = [], 0


def ok(cond, msg):
    global PASES
    if cond:
        PASES += 1
    else:
        FALLOS.append(msg)


def reg(**kw):
    base = {"pmcid": "PMC123", "version": 1, "is_pmc_openaccess": True,
            "license_code": "CC BY", "is_retracted": False,
            "is_historical_ocr": False, "is_manuscript": False}
    base.update(kw)
    return base


# ----------------------------------------------------- lo que si entra
def test_cc_by_entra():
    d = admisible_pmc(reg(license_code="CC BY"))
    ok(bool(d), f"CC BY debe entrar: {d.motivo}")
    ok(any("terceros" in a for a in d.advertencias),
       f"debe advertir del contenido de terceros embebido: {d.advertencias}")


def test_manuscrito_entra_con_advertencia():
    d = admisible_pmc(reg(is_manuscript=True))
    ok(bool(d), "un manuscrito de autor con CC BY si entra")
    ok(any("manuscrito" in a for a in d.advertencias),
       f"pero debe advertir que las cifras pueden diferir de la version final: "
       f"{d.advertencias}")


# ----------------------------------------------------- las cuatro trampas
def test_null_no_es_permisivo():
    """Verificado en registros reales: existe license_code null con is_pmc_openaccess
    true. Tratar null como permisivo ingiere contenido sin permiso comprobado."""
    d = admisible_pmc(reg(license_code=None))
    ok(not d, "license_code null NO es permisivo")
    ok(d.codigo is MotivoRechazo.LICENCIA_AUSENTE, f"codigo: {d.codigo}")
    ok("null" in d.motivo or "Other" in d.motivo, f"debe explicarlo: {d.motivo}")


def test_share_alike_rechazado_aunque_sea_comercial():
    """PMC agrupa CC BY-SA como 'Commercial Use Allowed' y es cierto, pero
    contagiaria la Boveda entera."""
    d = admisible_pmc(reg(license_code="CC BY-SA"))
    ok(not d, "CC BY-SA permite uso comercial pero debe rechazarse")
    ok("contagiaria" in d.motivo, f"el motivo debe ser el contagio, no el uso comercial: "
                                  f"{d.motivo}")


def test_sin_derivados_rechazado_aunque_sea_comercial():
    d = admisible_pmc(reg(license_code="CC BY-ND"))
    ok(not d, "CC BY-ND permite uso comercial pero prohibe derivados")
    ok("derivada" in d.motivo, f"motivo preciso: {d.motivo}")


def test_no_comercial_rechazado():
    for lic in ("CC BY-NC", "CC BY-NC-SA", "CC BY-NC-ND"):
        d = admisible_pmc(reg(license_code=lic))
        ok(not d, f"{lic} debe rechazarse")
        ok("comercial" in d.motivo, f"{lic}: motivo debe citar el uso comercial")


def test_tdm_no_habilita_publicar():
    """TDM autoriza minar, no reusar el contenido en un producto."""
    d = admisible_pmc(reg(license_code="TDM"))
    ok(not d, "TDM no habilita publicar lo derivado")
    ok("mineria" in d.motivo, f"motivo: {d.motivo}")


def test_licencia_desconocida_falla_cerrado():
    for lic in ("CC-BY", "cc by", "CC BY 4.0", "Creative Commons", "", "Elsevier"):
        d = admisible_pmc(reg(license_code=lic))
        ok(not d, f"una grafia o valor no verificado debe rechazarse: {lic!r}")
    ok(admisible_pmc(reg(license_code="cc by")).codigo is MotivoRechazo.LICENCIA_DESCONOCIDA,
       "la comparacion es de cadena exacta, incluidas mayusculas")


def test_license_code_no_cadena():
    d = admisible_pmc(reg(license_code=4))
    ok(not d, "un license_code que no es cadena se rechaza")
    ok(d.codigo is MotivoRechazo.LICENCIA_DESCONOCIDA, f"codigo: {d.codigo}")


def test_fuera_del_subconjunto():
    d = admisible_pmc(reg(is_pmc_openaccess=False, license_code="CC BY"))
    ok(not d, "fuera del subconjunto abierto no entra ni con CC BY")
    ok(d.codigo is MotivoRechazo.FUERA_DE_OA, f"codigo: {d.codigo}")


# ----------------------------------------------------- seguridad clinica
def test_retractado_se_rechaza_primero():
    """La exclusion mas importante del modulo, y no es de licencia."""
    d = admisible_pmc(reg(is_retracted=True, license_code="CC BY"))
    ok(not d, "un articulo retractado nunca puede anclar un hecho")
    ok(d.codigo is MotivoRechazo.RETRACTADO, f"codigo: {d.codigo}")

    # la retractacion gana sobre todo lo demas, incluido un rechazo por licencia
    d2 = admisible_pmc(reg(is_retracted=True, license_code="CC BY-NC",
                           is_pmc_openaccess=False))
    ok(d2.codigo is MotivoRechazo.RETRACTADO,
       f"la retractacion se reporta primero porque es seguridad del paciente: {d2.codigo}")


def test_ocr_historico_se_rechaza():
    d = admisible_pmc(reg(is_historical_ocr=True))
    ok(not d, "el ruido de OCR inhabilita el articulo para extraer cifras exactas")
    ok(d.codigo is MotivoRechazo.OCR_HISTORICO, f"codigo: {d.codigo}")


def test_campos_ausentes_fallan_cerrado():
    ok(not admisible_pmc({}), "un registro vacio no entra")
    ok(not admisible_pmc({"license_code": "CC BY"}),
       "sin is_pmc_openaccess explicito no entra")
    ok(admisible_pmc({"license_code": "CC BY"}).codigo is MotivoRechazo.FUERA_DE_OA,
       "la ausencia se trata como negativa, no como permiso")


def test_dictamen_es_booleano():
    ok(bool(admisible_pmc(reg())) is True, "un dictamen admisible es verdadero")
    ok(bool(admisible_pmc(reg(license_code="CC BY-NC"))) is False,
       "un dictamen inadmisible es falso, para poder usarlo en un if")


# ----------------------------------------------------- catalogo
def test_catalogo_coherente():
    ok(len(CATALOGO) >= 4, f"debe tener las fuentes verificadas: {list(CATALOGO)}")
    for clave, f in CATALOGO.items():
        ok(f.clave == clave, f"la clave debe coincidir: {clave}")
        ok(f.base_legal, f"{clave} debe declarar su base legal")
        ok(f.acceso, f"{clave} debe decir como se accede")
        ok(f.confianza_dictamen in ("alta", "media", "baja"),
           f"{clave} confianza invalida: {f.confianza_dictamen}")


def test_solo_pmc_contagia():
    ok(CATALOGO["pmc_oa"].share_alike,
       "PMC es la unica fuente con riesgo de contagio, porque su licencia es por articulo")
    for clave in ("clinicaltrials", "openfda", "vadod"):
        ok(not CATALOGO[clave].share_alike, f"{clave} no debe tener share-alike")


def test_hueco_cardiologico_registrado():
    """El hallazgo que mas afecta la planeacion: no hay fuente libre para falla
    cardiaca ni para sindrome coronario agudo."""
    huecos = " ".join(huecos_de_cobertura()).lower()
    ok("insuficiencia cardiaca" in huecos, f"debe registrar el hueco de falla cardiaca")
    ok("coronario" in huecos, "debe registrar el hueco de sindrome coronario agudo")
    ok("renal" in huecos, "debe registrar que openFDA no tiene campo de ajuste renal")


def test_obligaciones_son_tareas_programadas():
    obl = obligaciones_pendientes()
    ok(len(obl) >= 8, f"debe listar las obligaciones continuas: {len(obl)}")
    todo = " ".join(obl).lower()
    ok("actualizad" in todo or "actualizar" in todo,
       "debe incluir el deber de mantener los datos actualizados")
    ok("retract" in todo,
       "debe incluir el re-chequeo de retractaciones, que ocurren DESPUES de ingerir")
    ok(all(o.startswith("[") for o in obl), "cada obligacion debe decir de que fuente es")


def test_pendientes_no_se_esconden():
    pend = pendientes_de_verificar()
    ok(len(pend) >= 3, f"lo no verificado debe quedar a la vista: {len(pend)}")
    ok(all(p.startswith("[") for p in pend), "cada pendiente debe decir de que fuente es")
    todo = " ".join(pend)
    # la grafia de CC0 YA se verifico contra el bucket real, asi que no debe
    # seguir listada como pendiente: una lista de pendientes que no se depura
    # deja de ser util y se vuelve decorativa
    ok("grafia exacta de 'CC0'" not in todo,
       f"lo ya verificado debe salir de la lista de pendientes: {todo[:200]}")
    ok("CC0" in str(PERMITIDAS), "y CC0 sigue en la lista blanca, ahora verificada")
    ok(any("retract" in p for p in pend),
       "debe quedar pendiente la latencia del re-chequeo de retractaciones")


def test_fuente_por_tipo_de_ancla():
    ok(fuente_de_ancla(TipoAncla.REGISTRO_ENSAYO).clave == "clinicaltrials", "ensayo")
    ok(fuente_de_ancla(TipoAncla.ETIQUETA_REGULADOR).clave == "openfda", "etiqueta")
    ok(fuente_de_ancla(TipoAncla.GUIA_GOBIERNO).clave == "vadod", "guia de gobierno")
    ok(fuente_de_ancla(TipoAncla.SIN_ANCLA) is None, "sin ancla no tiene fuente")


# ------------------------------------------- contra datos reales del bucket
def test_contra_registros_reales():
    """Prueba la compuerta contra metadatos REALES del bucket publico de PMC,
    consultados el 2026-10-27. La fijacion existe porque la compuerta depende de
    una comparacion de cadena exacta: si NLM cambia una grafia, el filtro
    empieza a descartar articulos validos en silencio y esta prueba lo detecta."""
    import json
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fijaciones", "pmc_licencias.json")
    datos = json.load(open(ruta, encoding="utf-8"))
    regs = datos["registros"]
    ok(len(regs) >= 15, f"la fijacion debe traer una muestra util: {len(regs)}")
    ok(datos["_fecha_consulta"], "debe constar la fecha de consulta")
    ok("no refleja" in datos["_aviso"].lower(),
       "los terminos del dataset exigen hacer constar que puede no ser lo mas actual")

    # la fijacion no debe contener contenido de articulos, solo campos de licencia
    permitidos = {"pmcid", "version", "license_code", "is_pmc_openaccess",
                  "is_retracted", "is_historical_ocr", "is_manuscript"}
    for r in regs:
        ok(set(r) <= permitidos,
           f"la fijacion solo lleva campos de licencia, no contenido: {set(r) - permitidos}")

    codigos = {repr(r["license_code"]) for r in regs}
    ok("'CC BY'" in codigos, f"la muestra debe traer CC BY: {codigos}")
    ok("'CC0'" in codigos,
       f"y CC0, cuya grafia exacta era un riesgo abierto hasta leerla: {codigos}")

    veredictos = {}
    for r in regs:
        d = admisible_pmc(r)
        clave = d.codigo.value if d.codigo else "ADMITIDO"
        veredictos[clave] = veredictos.get(clave, 0) + 1
        # ninguna decision puede quedar sin motivo legible
        ok(bool(d.motivo), f"todo dictamen debe traer motivo: {r.get('pmcid')}")

    ok(veredictos.get("ADMITIDO", 0) >= 5,
       f"debe admitir los CC BY y CC0 no historicos: {veredictos}")
    ok(veredictos.get("licencia_no_permitida", 0) >= 1,
       f"debe rechazar los no comerciales: {veredictos}")


def test_cc0_con_ocr_historico_se_rechaza_igual():
    """Caso real y contraintuitivo del bucket: cuatro registros traen la licencia
    mas permisiva posible (CC0) Y is_historical_ocr=True. La licencia los
    permite; el ruido de OCR los inhabilita para extraer cifras. Las dos cosas a
    la vez, y manda la segunda."""
    d = admisible_pmc(reg(license_code="CC0", is_historical_ocr=True))
    ok(not d, "CC0 no salva a un articulo con texto reconocido opticamente")
    ok(d.codigo is MotivoRechazo.OCR_HISTORICO,
       f"el motivo debe ser el OCR y no la licencia: {d.codigo}")

    ok(bool(admisible_pmc(reg(license_code="CC0", is_historical_ocr=False))),
       "el mismo CC0 sin OCR historico si entra")


def test_tdm_viene_con_oa_falso():
    """Otro patron real: los registros TDM del bucket traen
    is_pmc_openaccess=False, lo que confirma que los dos campos no son
    redundantes y que filtrar por uno solo no basta."""
    d = admisible_pmc(reg(license_code="TDM", is_pmc_openaccess=False))
    ok(not d, "TDM fuera del subconjunto abierto no entra")


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
