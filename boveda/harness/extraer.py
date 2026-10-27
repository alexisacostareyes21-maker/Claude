"""El orquestador: de un objetivo clinico a un hecho atestiguado.

Este es el harness completo. Toma un objetivo descrito sin su valor, ejecuta el
plan de elicitacion por encuadres independientes, parsea las respuestas, corre
la sonda de complacencia, intenta anclar en una fuente publica, atestigua y
devuelve un Hecho con veredicto.

ECONOMIA, que es lo que decide si esto se puede construir sin dinero.

El plan completo cuesta de 7 a 8 llamadas al modelo por hecho. Con 600 hechos
para cubrir los dominios de mas rendimiento del ENARM, son unas 4,800 llamadas:
caro pero no prohibitivo, y una sola vez por hecho, no por usuario.

Dos mecanismos lo bajan bastante:

1. SALIDA TEMPRANA. Los dos encuadres mas estrictos van primero. Si ya
   discrepan entre si, el hecho esta destinado a ROJO y gastar seis llamadas
   mas no cambia el resultado: solo confirma con mas detalle algo que ya se
   sabe. En la practica una fraccion grande de los hechos se resuelve o se
   descarta en dos o tres llamadas.

2. ANCLAR ANTES DE ELICITAR, cuando se puede. Si el hecho tiene un NCT o un
   farmaco conocido, el anclaje es una consulta HTTP gratuita contra una fuente
   libre. Un hecho ya anclado necesita menos elicitaciones para acreditar, y la
   extraccion sobre el documento recuperado es mas barata y mas fiable que el
   recuerdo.

El tiempo medico tambien es presupuesto. El medico no revisa la Boveda: revisa
la cola de revision ordenada por costo de equivocarse, que para 600 hechos son
tipicamente unas decenas de casos, no 600. Eso es lo que hace viable la
validacion clinica sin nomina.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from . import prompts
from .anclar import (
    Fetcher, ResultadoAnclaje, anclar_en_ensayo, anclar_en_etiqueta, aplicar_anclaje,
)
from .atestiguar import (
    Acuerdo, Certeza, Elicitacion, Encuadre, Procedencia, Reporte, SondaFalsa,
    Veredicto, atestiguar, cola_de_revision,
)
from .hecho import ClaseHecho, Hecho, Poblacion
from .numeros import Clase, Magnitud, comparar, parsear

# Una funcion que recibe un prompt y devuelve el JSON ya parseado del modelo.
# Se inyecta para que el harness sea probable sin red y sin costo.
Modelo = Callable[[str], dict]


@dataclass
class Presupuesto:
    """Tope de llamadas al modelo. Existe porque el presupuesto real es cero."""

    max_llamadas: int = 8
    gastadas: int = 0

    def queda(self) -> int:
        return max(0, self.max_llamadas - self.gastadas)

    def gastar(self) -> bool:
        if self.queda() <= 0:
            return False
        self.gastadas += 1
        return True


@dataclass
class Curacion:
    """El resultado completo de curar un hecho, con su rastro."""

    hecho: Hecho
    reporte: Optional[Reporte] = None
    elicitaciones: list[Elicitacion] = field(default_factory=list)
    sondas: list[SondaFalsa] = field(default_factory=list)
    anclajes: list[ResultadoAnclaje] = field(default_factory=list)
    llamadas: int = 0
    salida_temprana: str = ""
    cadena_mecanismo: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return {
            "hecho": self.hecho.dict(),
            "reporte": self.reporte.dict() if self.reporte else None,
            "llamadas_al_modelo": self.llamadas,
            "salida_temprana": self.salida_temprana,
            "cadena_mecanismo": self.cadena_mecanismo,
            "anclajes": [a.dict() for a in self.anclajes],
        }


# ---------------------------------------------------------------------------
# Parseo de la respuesta del modelo
# ---------------------------------------------------------------------------


def respuesta_a_elicitacion(resp: dict, encuadre: Encuadre, modelo: str = "",
                            clase_sugerida: Optional[Clase] = None,
                            analito: Optional[str] = None) -> Elicitacion:
    """Convierte el JSON del modelo en una Elicitacion.

    Una respuesta mal formada, o una cifra que no se puede parsear, se trata
    como abstencion y no como error: el harness prefiere perder una medicion
    antes que inventar una magnitud a partir de un campo ambiguo.
    """
    if not isinstance(resp, dict):
        return Elicitacion(None, encuadre, modelo, abstuvo=True,
                           texto_bruto="respuesta no es un objeto")

    if resp.get("no_se") is True:
        return Elicitacion(None, encuadre, modelo, abstuvo=True,
                           certeza=Certeza.NO_LO_SE,
                           texto_bruto=str(resp.get("explicacion") or "no_se"))

    # El orden importa: el parser reconoce "hazard ratio 0.61", no "0.61 hazard ratio",
    # porque el alias de la medida tiene que preceder al numero para anclarlo.
    bruto = " ".join(str(resp.get(k, "")) for k in ("medida", "valor", "unidad")).strip()
    if resp.get("ic_inferior") and resp.get("ic_superior"):
        bruto += f" (IC 95% {resp['ic_inferior']}-{resp['ic_superior']})"

    mags = parsear(bruto, clase_sugerida=clase_sugerida, analito=analito)
    if not mags:
        return Elicitacion(None, encuadre, modelo, abstuvo=True,
                           texto_bruto=f"no se pudo parsear una magnitud de: {bruto!r}")

    p = resp.get("procedencia") or {}
    proc = Procedencia(
        estudio=str(p.get("estudio") or ""), ano=str(p.get("ano") or ""),
        n=str(p.get("n") or ""), poblacion=str(p.get("poblacion") or ""),
        desenlace=str(p.get("desenlace") or ""), registro=str(p.get("registro") or ""),
    )
    try:
        certeza = Certeza(str(resp.get("certeza") or "recuerdo_aproximado"))
    except ValueError:
        certeza = Certeza.RECUERDO_APROXIMADO

    return Elicitacion(mags[0], encuadre, modelo, texto_bruto=bruto,
                       certeza=certeza, procedencia=proc)


def respuesta_a_sonda(resp: dict, valor_falso: Magnitud,
                      clase_sugerida: Optional[Clase] = None) -> SondaFalsa:
    """Interpreta la respuesta a la sonda de complacencia.

    Aceptar es `correcta == True`. Decir no_se NO es aceptar: es abstenerse, que
    es la respuesta prudente y no debe penalizarse.
    """
    if not isinstance(resp, dict):
        return SondaFalsa(valor_falso, acepto=False, texto_bruto="respuesta ilegible")
    if resp.get("no_se") is True:
        return SondaFalsa(valor_falso, acepto=False,
                          texto_bruto="el modelo se abstuvo de juzgar la cifra")
    acepto = resp.get("correcta") is True
    corr = None
    if not acepto and resp.get("valor_correcto"):
        bruto = (f"{resp.get('medida') or ''} {resp.get('valor_correcto')} "
                 f"{resp.get('unidad') or ''}").strip()
        mags = parsear(bruto, clase_sugerida=clase_sugerida)
        corr = mags[0] if mags else None
    return SondaFalsa(valor_falso, acepto=acepto, corrigio_a=corr,
                      texto_bruto=str(resp.get("explicacion") or ""))


def respuesta_a_mecanismo(resp: dict) -> tuple[list[str], int]:
    """Extrae la cadena causal y su signo neto del encuadre de mecanismo."""
    if not isinstance(resp, dict):
        return [], 0
    cadena = [str(x) for x in (resp.get("cadena") or [])]
    neto = 0
    bruto = str(resp.get("signo_neto") or "")
    if "-1" in bruto or "menos" in bruto.lower():
        neto = -1
    elif "+1" in bruto or "1" in bruto or "mas" in bruto.lower():
        neto = 1
    if not neto:
        signos = [str(s) for s in (resp.get("signos") or [])]
        prod = 1
        for s in signos:
            prod *= -1 if ("-1" in s or "menos" in s.lower()) else 1
        neto = prod if signos else 0
    return cadena, neto


# ---------------------------------------------------------------------------
# El motor
# ---------------------------------------------------------------------------


class Motor:
    """Cura hechos: elicita, ancla, atestigua."""

    def __init__(self, modelo: Modelo, fetcher: Optional[Fetcher] = None,
                 nombre_modelo: str = "modelo") -> None:
        self.modelo = modelo
        self.fetcher = fetcher
        self.nombre_modelo = nombre_modelo

    # ------------------------------------------------------------------ curar
    def curar(self, objetivo: prompts.Objetivo, plantilla: Hecho,
              nct: str = "", generico: str = "", tipo_hecho_etiqueta: str = "dosis",
              presupuesto: Optional[Presupuesto] = None,
              clase_sugerida: Optional[Clase] = None,
              pista_etiqueta: str = "") -> Curacion:
        """Pipeline completo para un hecho.

        `plantilla` trae la poblacion, la intervencion y el desenlace ya escritos
        a mano o por un paso previo: la magnitud la pone este metodo. Separar las
        dos cosas es deliberado, porque la poblacion es donde un error pasa
        inadvertido y donde conviene que haya criterio humano.
        """
        pres = presupuesto or Presupuesto()
        cur = Curacion(hecho=plantilla)
        plan = prompts.plan(objetivo)

        # ---- 1. Elicitacion por encuadres, con salida temprana
        for encuadre, prompt in plan:
            if not pres.gastar():
                cur.salida_temprana = "presupuesto agotado"
                break
            cur.llamadas += 1
            resp = self._llamar(prompt)

            if encuadre is Encuadre.DESDE_MECANISMO:
                cadena, neto = respuesta_a_mecanismo(resp)
                cur.cadena_mecanismo = cadena
                cur.elicitaciones.append(
                    Elicitacion(None, encuadre, self.nombre_modelo,
                                abstuvo=True, signo_mecanismo=neto,
                                texto_bruto=" | ".join(cadena[:4]))
                )
                continue

            cur.elicitaciones.append(
                respuesta_a_elicitacion(resp, encuadre, self.nombre_modelo,
                                        clase_sugerida=clase_sugerida)
            )

            if self._discrepancia_temprana(cur.elicitaciones):
                cur.salida_temprana = (
                    "los dos primeros encuadres discrepan: el hecho va a revision y "
                    "seguir elicitando no cambiaria el veredicto"
                )
                break

        # ---- 2. Anclaje en fuente publica
        consenso = self._consenso_provisional(cur.elicitaciones)
        if self.fetcher is not None and consenso is not None:
            if nct:
                cur.anclajes.append(
                    anclar_en_ensayo(nct, consenso, self.fetcher,
                                     desenlace=objetivo.desenlace)
                )
            if generico:
                cur.anclajes.append(
                    anclar_en_etiqueta(generico, consenso, self.fetcher,
                                       tipo_hecho=tipo_hecho_etiqueta,
                                       pista=pista_etiqueta)
                )
            if cur.anclajes:
                aplicar_anclaje(cur.hecho, cur.anclajes)

        # ---- 3. Sonda de complacencia, solo si vale la pena gastarla
        if consenso is not None and not cur.salida_temprana and pres.queda() > 0:
            falso = prompts.valor_para_sonda(consenso.valor)
            if pres.gastar():
                cur.llamadas += 1
                resp = self._llamar(prompts.sonda_falsa(
                    objetivo, str(falso), consenso.clase.value))
                mag_falsa = Magnitud(clase=consenso.clase, valor=falso,
                                     unidad=consenso.unidad, bruto=str(falso))
                cur.sondas.append(
                    respuesta_a_sonda(resp, mag_falsa, clase_sugerida=consenso.clase)
                )

        # ---- 4. Atestiguacion
        rep = atestiguar(cur.hecho, cur.elicitaciones, cur.sondas)
        cur.reporte = rep
        cur.hecho.veredicto = rep.veredicto.value
        cur.hecho.confianza = rep.confianza
        cur.hecho.diagnostico.update(rep.dict())
        if rep.magnitud_consenso is not None and cur.hecho.magnitud is None:
            cur.hecho.magnitud = rep.magnitud_consenso
        if cur.cadena_mecanismo and not cur.hecho.mecanismo:
            cur.hecho.mecanismo = cur.cadena_mecanismo
        return cur

    # ------------------------------------------------------------------ lote
    def curar_lote(self, trabajos: Sequence[dict],
                   max_llamadas_total: int = 0) -> dict:
        """Cura varios hechos y devuelve el lote con su contabilidad.

        Cada trabajo es un diccionario con las claves que acepta `curar`. El
        resultado trae la cola de revision ya ordenada, que es el entregable
        para el medico validador.
        """
        curaciones: list[Curacion] = []
        gastado = 0
        for t in trabajos:
            if max_llamadas_total and gastado >= max_llamadas_total:
                break
            pres = Presupuesto(max_llamadas=t.get("max_llamadas", 8))
            c = self.curar(
                objetivo=t["objetivo"], plantilla=t["plantilla"],
                nct=t.get("nct", ""), generico=t.get("generico", ""),
                tipo_hecho_etiqueta=t.get("tipo_hecho_etiqueta", "dosis"),
                presupuesto=pres, clase_sugerida=t.get("clase_sugerida"),
                pista_etiqueta=t.get("pista_etiqueta", ""),
            )
            gastado += c.llamadas
            curaciones.append(c)

        hechos = [c.hecho for c in curaciones]
        por_veredicto: dict[str, int] = {}
        for h in hechos:
            por_veredicto[h.veredicto] = por_veredicto.get(h.veredicto, 0) + 1

        return {
            "curaciones": curaciones,
            "hechos": hechos,
            "mostrables": [h for h in hechos if h.se_muestra()],
            "cola_de_revision": cola_de_revision(hechos),
            "llamadas_al_modelo": gastado,
            "llamadas_por_hecho": round(gastado / len(curaciones), 2) if curaciones else 0,
            "por_veredicto": por_veredicto,
            "tasa_mostrable": (round(len([h for h in hechos if h.se_muestra()]) / len(hechos), 3)
                               if hechos else 0),
        }

    # ------------------------------------------------------------------ interno
    def _llamar(self, prompt: str) -> dict:
        """Llama al modelo y nunca deja que una excepcion tumbe el lote."""
        try:
            r = self.modelo(prompt)
            return r if isinstance(r, dict) else {}
        except Exception as e:  # noqa: BLE001
            return {"no_se": True, "explicacion": f"fallo la llamada: {type(e).__name__}"}

    @staticmethod
    def _discrepancia_temprana(elic: list[Elicitacion]) -> bool:
        """True si las dos primeras mediciones utiles ya se contradicen.

        No basta con que no coincidan: tienen que DISCREPAR. Dos magnitudes
        incomparables, o una abstencion, no son evidencia de conflicto y no
        justifican abandonar el hecho.
        """
        utiles = [e for e in elic if e.magnitud is not None and not e.abstuvo]
        if len(utiles) != 2:
            return False
        return comparar(utiles[0].magnitud, utiles[1].magnitud) is Acuerdo.DISCREPANTE

    @staticmethod
    def _consenso_provisional(elic: list[Elicitacion]) -> Optional[Magnitud]:
        """La magnitud mas votada hasta ahora, para orientar el anclaje.

        Es provisional por diseno: se usa para saber QUE buscar en la fuente, no
        para acreditar nada. Si el anclaje encuentra otra cosa, gana la fuente.
        """
        from .numeros import agrupar
        mags = [e.magnitud for e in elic if e.magnitud is not None and not e.abstuvo]
        if not mags:
            return None
        grupos = agrupar(mags)
        return grupos[0][0] if grupos else None


# ---------------------------------------------------------------------------
# Ayudas para armar trabajos
# ---------------------------------------------------------------------------


def trabajo(concepto: str, poblacion: str, condicion: str, clase: ClaseHecho,
            intervencion: str = "", desenlace: str = "", comparador: str = "",
            medida: str = "", ensayo: str = "", farmaco: str = "", nct: str = "",
            generico: str = "", clase_magnitud: Optional[Clase] = None,
            nivel_atencion: str = "", pais: str = "MX",
            tipo_hecho_etiqueta: str = "dosis", pista_etiqueta: str = "",
            revisar_si: Optional[list] = None) -> dict:
    """Construye un trabajo para `curar_lote` sin repetir la plomeria."""
    return {
        "objetivo": prompts.Objetivo(
            concepto=concepto, poblacion=poblacion, intervencion=intervencion,
            comparador=comparador, desenlace=desenlace, medida_pedida=medida,
            ensayo=ensayo, farmaco=farmaco,
        ),
        "plantilla": Hecho(
            enunciado=concepto, clase=clase,
            poblacion=Poblacion(condicion=condicion, nivel_atencion=nivel_atencion,
                                pais_contexto=pais),
            intervencion=intervencion or farmaco, comparador_clinico=comparador,
            desenlace=desenlace,
            revisar_si=revisar_si or ["aparece un ensayo nuevo en esta poblacion",
                                      "cambia la etiqueta del regulador"],
        ),
        "nct": nct, "generico": generico, "clase_sugerida": clase_magnitud,
        "tipo_hecho_etiqueta": tipo_hecho_etiqueta, "pista_etiqueta": pista_etiqueta,
    }


__all__ = [
    "Motor", "Modelo", "Presupuesto", "Curacion", "trabajo",
    "respuesta_a_elicitacion", "respuesta_a_sonda", "respuesta_a_mecanismo",
]
