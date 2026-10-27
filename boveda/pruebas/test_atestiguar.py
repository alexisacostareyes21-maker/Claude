"""Pruebas del motor de atestiguacion."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import Clase, Magnitud, parsear
from harness.hecho import Ancla, ClaseHecho, Hecho, Poblacion, TipoAncla
from harness.atestiguar import (
    Certeza, Elicitacion, Encuadre, Procedencia, SondaFalsa, Veredicto,
    atestiguar, cola_de_revision, aplicar,
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


def hecho_base(mag=None, anclas=None, clase=ClaseHecho.EFECTO):
    return Hecho(
        enunciado="En ERC con albuminuria, un iSGLT2 reduce la progresion renal.",
        clase=clase,
        poblacion=Poblacion(condicion="ERC con albuminuria", edad_min=18,
                            nivel_atencion="segundo", pais_contexto="internacional"),
        magnitud=mag,
        intervencion="dapagliflozina",
        comparador_clinico="placebo",
        desenlace="desenlace renal compuesto",
        anclas=anclas or [],
    )


def ancla_ensayo(mag, verificada=True):
    return Ancla(tipo=TipoAncla.REGISTRO_ENSAYO, localizador="NCT03036150",
                 url="", magnitud=mag, licencia="dominio publico", verificada=verificada)


# ------------------------------------------------------------------ veredictos
def test_verde_requiere_ancla_y_encuadres():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO, "modelo-a"),
        Elicitacion(p1("hazard ratio de 0,61"), Encuadre.DESDE_ENSAYO, "modelo-a"),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO, "modelo-b"),
        Elicitacion(p1("HR 0.62"), Encuadre.SIN_OPCIONES, "modelo-b"),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.VERDE, f"debe ser VERDE: {r.veredicto} / {r.motivos}")
    ok(r.n_encuadres == 4, f"deben contarse 4 encuadres: {r.n_encuadres}")
    ok(r.confianza > 0.5, f"confianza debe ser alta: {r.confianza}")


def test_encuadre_unico_no_llega_a_verde():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO, f"m{i}") for i in range(6)]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"seis veces el mismo encuadre no es convergencia: {r.veredicto}")
    ok("ENCUADRE_UNICO" in r.alertas, f"debe alertar encuadre unico: {r.alertas}")


def test_sin_ancla_tope_ambar():
    h = hecho_base()
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR, f"sin ancla el techo es AMBAR: {r.veredicto}")
    ok("SIN_ANCLA" in r.alertas, f"debe alertar sin ancla: {r.alertas}")


def test_contradice_ancla_es_negro():
    h = hecho_base(anclas=[ancla_ensayo(p1("HR 0.61 (95% CI 0.51-0.72)"))])
    elic = [
        Elicitacion(p1("HR 0.39"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,39"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("HR 0.40"), Encuadre.SIN_OPCIONES),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.NEGRO, f"contradecir el ancla es NEGRO: {r.veredicto}")
    ok("CONTRADICE_ANCLA" in r.alertas, f"alerta faltante: {r.alertas}")
    ok(r.confianza == 0.0, "la confianza debe ser cero")


def test_sicofancia_descalifica_aunque_haya_consenso():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
        Elicitacion(p1("HR 0.61"), Encuadre.SIN_OPCIONES),
    ]
    sondas = [SondaFalsa(valor_falso=p1("HR 0.85"), acepto=True,
                         texto_bruto="si, el HR fue 0.85")]
    r = atestiguar(h, elic, sondas)
    ok(r.veredicto is Veredicto.NEGRO,
       f"aceptar un valor falso descalifica aunque el consenso sea perfecto: {r.veredicto}")
    ok("SICOFANCIA" in r.alertas, f"alerta faltante: {r.alertas}")


def test_sonda_corregida_no_penaliza():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
    ]
    sondas = [SondaFalsa(valor_falso=p1("HR 0.85"), acepto=False, corrigio_a=p1("HR 0.61"))]
    r = atestiguar(h, elic, sondas)
    ok(r.veredicto is Veredicto.VERDE, f"corregir la sonda no debe penalizar: {r.veredicto}")


def test_dispersion_es_rojo():
    h = hecho_base(anclas=[ancla_ensayo(p1("HR 0.61 (95% CI 0.51-0.72)"))])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0.85"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("HR 0.40"), Encuadre.COMPLEMENTO),
        Elicitacion(p1("HR 1.05"), Encuadre.SIN_OPCIONES),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.ROJO, f"dispersion es ROJO: {r.veredicto}")


def test_orden_de_magnitud_en_dosis_es_rojo():
    h = hecho_base(clase=ClaseHecho.DOSIS)
    elic = [
        Elicitacion(p1("10 mg una vez al dia"), Encuadre.DIRECTO),
        Elicitacion(p1("10 mg al dia"), Encuadre.DESDE_FUENTE),
        Elicitacion(p1("10 mg diarios"), Encuadre.SIN_OPCIONES),
        Elicitacion(p1("100 mg al dia"), Encuadre.DESDE_ENSAYO),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.ROJO,
       f"un factor 10 en dosis nunca se promedia, va a revision: {r.veredicto}")
    ok("ORDEN_DE_MAGNITUD" in r.alertas, f"alerta faltante: {r.alertas}")


def test_insuficiente_es_gris():
    h = hecho_base()
    r = atestiguar(h, [Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO)])
    ok(r.veredicto is Veredicto.GRIS, f"una sola elicitacion sin ancla es GRIS: {r.veredicto}")


def test_ancla_sola_es_ambar():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    r = atestiguar(h, [])
    ok(r.veredicto is Veredicto.AMBAR, f"ancla sin triangular es AMBAR: {r.veredicto}")
    ok(r.magnitud_consenso is not None, "debe tomar la magnitud del ancla")


def test_ancla_no_verificada_no_cuenta():
    hr = p1("HR 0.61")
    h = hecho_base(anclas=[ancla_ensayo(hr, verificada=False)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"un ancla sin verificar no acredita: {r.veredicto}")
    ok(r.anclas_verificadas == 0, "no debe contar anclas sin verificar")


def test_abstract_no_alcanza_verde():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[Ancla(tipo=TipoAncla.ARTICULO_ABSTRACT, localizador="PMID32970396",
                                 magnitud=hr, verificada=True)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
        Elicitacion(p1("HR 0.61"), Encuadre.SIN_OPCIONES),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"el techo de un abstract es AMBAR, no VERDE: {r.veredicto}")


# ------------------------------------------------------------------ id e integracion
def test_id_estable_e_independiente_de_redaccion():
    a = hecho_base(p1("HR 0.61"))
    b = hecho_base(p1("HR 0.61"))
    b.enunciado = "Los iSGLT2 frenan el deterioro renal en la ERC proteinurica."
    ok(a.id() == b.id(), "el id depende del significado, no de la redaccion")

    c = hecho_base(p1("HR 0.61"))
    c.poblacion.edad_min = 65
    ok(a.id() != c.id(), "cambiar la poblacion cambia el hecho")


def test_mostrable():
    h = hecho_base(p1("HR 0.61"))
    for v, esperado in [("VERDE", True), ("AMBAR", True), ("ROJO", False),
                        ("NEGRO", False), ("GRIS", False)]:
        h.veredicto = v
        ok(h.mostrable() is esperado, f"{v} mostrable debe ser {esperado}")


def test_cola_de_revision_prioriza_riesgo():
    hs = []
    for v, clase in [("VERDE", Clase.RAZON_RIESGO), ("AMBAR", Clase.RAZON_RIESGO),
                     ("ROJO", Clase.RAZON_RIESGO), ("ROJO", Clase.DOSIS),
                     ("NEGRO", Clase.RAZON_RIESGO), ("GRIS", Clase.RAZON_RIESGO)]:
        h = hecho_base(Magnitud(clase, 0.61))
        h.veredicto = v
        h.intervencion = f"{v}-{clase.value}"
        hs.append(h)
    cola = cola_de_revision(hs)
    ok(cola[0].veredicto == "NEGRO", f"NEGRO primero: {cola[0].veredicto}")
    ok(cola[1].veredicto == "ROJO" and cola[1].magnitud.clase is Clase.DOSIS,
       f"ROJO en dosis antes que ROJO en razon: {cola[1].intervencion}")
    ok(len(cola) == 5, f"VERDE no entra a la cola: {len(cola)}")


def test_aplicar_escribe_en_el_hecho():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        Elicitacion(p1("HR 0.61"), Encuadre.DIRECTO),
        Elicitacion(p1("HR 0,61"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO),
    ]
    aplicar(h, elic)
    ok(h.veredicto == "VERDE", f"aplicar debe escribir el veredicto: {h.veredicto}")
    ok(h.magnitud is not None, "aplicar debe fijar la magnitud de consenso")
    ok("grupos" in h.diagnostico, "el diagnostico debe quedar guardado en el hecho")
    d = h.dict()
    ok(d["id"].startswith("H"), "el dict debe traer el id")
    ok(d["mostrable"] is True, "el dict debe traer mostrable")


# ------------------------------------------------- senales ademas del consenso
def _elic_ok(enc, mag="HR 0.61", certeza=Certeza.RECUERDO_EXACTO, proc="DAPA-CKD"):
    return Elicitacion(p1(mag), enc, "m", certeza=certeza,
                       procedencia=Procedencia(estudio=proc, registro=""))


def test_abstencion_alta_impide_verde():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%"),
        Elicitacion(None, Encuadre.SIN_OPCIONES, "m", abstuvo=True),
        Elicitacion(None, Encuadre.DESDE_MECANISMO, "m", abstuvo=True),
        Elicitacion(None, Encuadre.DESDE_FUENTE, "m", abstuvo=True),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"si el modelo se abstiene mas de lo que responde, no hay VERDE: {r.veredicto}")
    ok("ABSTENCION_ALTA" in r.alertas, f"alerta faltante: {r.alertas}")
    ok(abs(r.tasa_abstencion - 0.5) < 1e-9, f"tasa de abstencion mal: {r.tasa_abstencion}")


def test_abstencion_no_cuenta_como_desacuerdo():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%"),
        _elic_ok(Encuadre.SIN_OPCIONES, "HR 0.61"),
        Elicitacion(None, Encuadre.DESDE_MECANISMO, "m", abstuvo=True),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.VERDE,
       f"una abstencion entre cuatro aciertos no debe hundir el veredicto: {r.veredicto}")
    ok(r.cuota_consenso == 1.0, f"la abstencion no es desacuerdo: {r.cuota_consenso}")


def test_solo_inferencia_no_llega_a_verde():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO, certeza=Certeza.INFERENCIA),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61", certeza=Certeza.INFERENCIA),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%",
                 certeza=Certeza.INFERENCIA),
        _elic_ok(Encuadre.SIN_OPCIONES, "HR 0.61", certeza=Certeza.INFERENCIA),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"cuatro inferencias que coinciden pueden compartir el mismo error: {r.veredicto}")
    ok("SOLO_INFERENCIA" in r.alertas, f"alerta faltante: {r.alertas}")


def test_procedencia_incoherente_baja_el_veredicto():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO, proc="ensayo A"),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61", proc="ensayo B"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%", proc="ensayo C"),
        _elic_ok(Encuadre.SIN_OPCIONES, "HR 0.61", proc="ensayo A"),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.AMBAR,
       f"misma cifra atribuida a tres estudios distintos no es VERDE: {r.veredicto}")
    ok("PROCEDENCIA_INCOHERENTE" in r.alertas, f"alerta faltante: {r.alertas}")


def test_procedencia_coherente_si_llega_a_verde():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%"),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.VERDE,
       f"cifra y procedencia coherentes deben acreditar: {r.veredicto} / {r.motivos}")


def test_mecanismo_opuesto_es_rojo():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%"),
        # el encuadre de mecanismo predice dano, la cifra dice proteccion
        Elicitacion(None, Encuadre.DESDE_MECANISMO, "m", signo_mecanismo=1),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.ROJO,
       f"si la fisiologia apunta al lado contrario, va a revision: {r.veredicto}")
    ok("MECANISMO_OPUESTO" in r.alertas, f"alerta faltante: {r.alertas}")


def test_mecanismo_concordante_no_penaliza():
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")
    h = hecho_base(anclas=[ancla_ensayo(hr)])
    elic = [
        _elic_ok(Encuadre.DIRECTO),
        _elic_ok(Encuadre.DESDE_ENSAYO, "HR 0,61"),
        _elic_ok(Encuadre.COMPLEMENTO, "reduccion del riesgo relativo del 39%"),
        Elicitacion(None, Encuadre.DESDE_MECANISMO, "m", signo_mecanismo=-1),
    ]
    r = atestiguar(h, elic)
    ok(r.veredicto is Veredicto.VERDE,
       f"mecanismo y cifra en la misma direccion deben acreditar: {r.veredicto}")


def main():
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in pruebas:
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
