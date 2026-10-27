"""Anclaje: convertir una cifra en un dato localizado en una fuente publica.

Una ancla solo queda `verificada=True` cuando el numero se ENCUENTRA en el
documento recuperado y COINCIDE con la magnitud afirmada. No basta con que el
documento exista, ni con que hable del tema. Esa es la diferencia entre citar y
anclar, y es lo unico que separa a la Boveda de un generador de texto con
bibliografia decorativa.

Cada ancla verificada guarda la ruta exacta dentro del documento (la ruta JSON
en el caso de un registro de ensayo, el campo y el desplazamiento en el caso de
una etiqueta), para que cualquier persona pueda repetir la comprobacion sin
confiar en el sistema.

RUTAS DE CAMPO, verificadas en la investigacion de fuentes de este proyecto:

ClinicalTrials.gov API v2 (licencia expresa a cualquiera, sin cargo):
  resultsSection.outcomeMeasuresModule.outcomeMeasures[]
    .title, .description, .timeFrame, .type
    .analyses[].paramType        "Hazard Ratio", "Risk Ratio", "Odds Ratio", ...
    .analyses[].paramValue       el valor
    .analyses[].ciPctValue       95
    .analyses[].ciLowerLimit / .ciUpperLimit
    .analyses[].pValue, .statisticalMethod
    .denoms[].counts[].value     denominadores reales por brazo
  protocolSection.statusModule.lastUpdatePostDateStruct.date

openFDA drug label (CC0 1.0):
  results[].dosage_and_administration[]      prosa libre
  results[].use_in_specific_populations[]    prosa libre: 8.6 renal, 8.7 hepatico
  results[].contraindications[]
  results[].mechanism_of_action[]            seccion 12.1, alimenta el grafo
  results[].openfda.spl_set_id               localizador estable

OBLIGACION CONTINUA QUE IMPONE INGENIERIA, no solo papeleo:
los terminos de ClinicalTrials.gov exigen mantener los datos actualizados en
todo momento mientras se retengan. Un snapshot congelado los incumple. Por eso
cada ancla lleva `fecha_consulta` y la fecha de ultima actualizacion del
registro, y existe `necesita_refresco()`; el cumplimiento es una tarea
programada, no una casilla en los terminos y condiciones.

HALLAZGO QUE OBLIGA A EXTRAER DE PROSA:
openFDA NO tiene ningun campo estructurado de ajuste renal o hepatico. Los
cortes de eGFR y de depuracion de creatinina, las dosis maximas y las reglas de
ajuste existen unicamente como prosa dentro de dosage_and_administration y
use_in_specific_populations. De ahi que el anclaje de dosis y umbrales dependa
del parseo de magnitudes de harness.numeros y no de una consulta de campo.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol

from .numeros import Acuerdo, Clase, Magnitud, comparar, parsear
from .hecho import Ancla, TipoAncla

CT_BASE = "https://clinicaltrials.gov/api/v2"
FDA_BASE = "https://api.fda.gov/drug/label.json"

# Campos de la etiqueta FDA donde viven las cifras, por tipo de hecho buscado.
CAMPOS_ETIQUETA = {
    "dosis": ["dosage_and_administration"],
    "ajuste_renal": ["use_in_specific_populations", "dosage_and_administration"],
    "ajuste_hepatico": ["use_in_specific_populations", "dosage_and_administration"],
    "contraindicacion": ["contraindications", "boxed_warning"],
    "mecanismo": ["mechanism_of_action", "clinical_pharmacology"],
    "farmacocinetica": ["pharmacokinetics", "clinical_pharmacology"],
    "interaccion": ["drug_interactions"],
}

# paramType de ClinicalTrials.gov -> clase de magnitud de la Boveda
PARAM_A_CLASE = {
    "hazard ratio": Clase.RAZON_RIESGO,
    "risk ratio": Clase.RAZON_RIESGO,
    "odds ratio": Clase.RAZON_RIESGO,
    "rate ratio": Clase.RAZON_RIESGO,
    "relative risk": Clase.RAZON_RIESGO,
    "risk difference": Clase.REDUCCION_ABS,
    "risk difference (%)": Clase.REDUCCION_ABS,
    "mean difference": Clase.ADIMENSIONAL,
    "mean difference (final values)": Clase.ADIMENSIONAL,
    "number": Clase.CONTEO,
}


class Fetcher(Protocol):
    """Como la Boveda trae documentos. Se inyecta para poder probar sin red."""

    def get(self, url: str) -> dict: ...


@dataclass
class FetcherHTTP:
    """Trae por red, respetando el proxy y el almacen de certificados del entorno.

    NO ESTA PROBADO EN ESTE ENTORNO: la politica de egress del contenedor donde
    se escribio este modulo bloquea clinicaltrials.gov y api.fda.gov con un 403
    en el CONNECT. El camino offline si esta probado. Antes de confiar en este
    adaptador hay que ejecutarlo contra la red real una vez.
    """

    timeout: int = 30
    cafile: Optional[str] = None
    user_agent: str = "ORIONS-Boveda/0.1 (anclaje de evidencia)"
    cache_dir: Optional[str] = None

    def get(self, url: str) -> dict:
        if self.cache_dir:
            ruta = os.path.join(self.cache_dir, _nombre_cache(url))
            if os.path.exists(ruta):
                with open(ruta, encoding="utf-8") as f:
                    return json.load(f)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            kw = {"timeout": self.timeout}
            if self.cafile:
                kw["cafile"] = self.cafile
            with urllib.request.urlopen(req, **kw) as r:
                datos = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise AnclajeImposible(f"HTTP {e.code} al traer {url}") from e
        except urllib.error.URLError as e:
            raise AnclajeImposible(
                f"no se pudo alcanzar {url}: {e.reason}. Si es un 403 en el CONNECT, "
                f"es la politica de egress del entorno y no un fallo del codigo: "
                f"reportar el host bloqueado en vez de insistir."
            ) from e
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(os.path.join(self.cache_dir, _nombre_cache(url)), "w",
                      encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False)
        return datos


@dataclass
class FetcherOffline:
    """Lee documentos ya guardados. Es el camino probado y el de las pruebas.

    Tambien es el modo correcto para reproducibilidad: una Boveda auditable
    necesita poder repetir el anclaje sobre el documento tal como estaba el dia
    que se anclo.
    """

    documentos: dict

    def get(self, url: str) -> dict:
        for clave, doc in self.documentos.items():
            if clave in url:
                return doc
        raise AnclajeImposible(f"sin documento offline para {url}")


class AnclajeImposible(Exception):
    """No se pudo recuperar el documento. Distinto de que la cifra no coincida."""


def _nombre_cache(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", url)[:180] + ".json"


# ---------------------------------------------------------------------------
# Anclaje en registro de ensayo
# ---------------------------------------------------------------------------


@dataclass
class ResultadoAnclaje:
    ancla: Ancla
    coincide: Optional[Acuerdo]
    ruta: str = ""              # ruta JSON o campo y desplazamiento
    encontrado: Optional[Magnitud] = None
    candidatos: Optional[list] = None
    motivo: str = ""

    def dict(self) -> dict:
        return {
            "ancla": self.ancla.dict(),
            "coincide": self.coincide.value if self.coincide else None,
            "ruta": self.ruta,
            "encontrado": self.encontrado.dict() if self.encontrado else None,
            "motivo": self.motivo,
        }


def anclar_en_ensayo(nct_id: str, magnitud: Magnitud, fetcher: Fetcher,
                     desenlace: str = "", tol: float = 0.02) -> ResultadoAnclaje:
    """Busca la magnitud en la base de resultados del ensayo.

    Recorre outcomeMeasures y sus analyses, convierte cada paramValue a una
    Magnitud de la Boveda y la compara semanticamente. Devuelve la primera
    coincidencia y, si no hay ninguna, la lista de lo que si encontro, que es
    justo lo que necesita el revisor humano para decidir.
    """
    if not re.fullmatch(r"NCT\d{8}", nct_id or ""):
        return ResultadoAnclaje(
            ancla=_ancla_ensayo(nct_id, magnitud, False),
            coincide=None,
            motivo=(f"'{nct_id}' no tiene la forma de un identificador de ensayo "
                    f"(NCT y ocho digitos): no se intenta la consulta"),
        )

    url = f"{CT_BASE}/studies/{nct_id}"
    try:
        doc = fetcher.get(url)
    except AnclajeImposible as e:
        return ResultadoAnclaje(ancla=_ancla_ensayo(nct_id, magnitud, False),
                                coincide=None, motivo=str(e))

    medidas = (doc.get("resultsSection", {})
                  .get("outcomeMeasuresModule", {})
                  .get("outcomeMeasures", []) or [])
    if not medidas:
        return ResultadoAnclaje(
            ancla=_ancla_ensayo(nct_id, magnitud, False), coincide=None,
            motivo=("el registro existe pero no publico resultados: sirve para la "
                    "poblacion y el diseno, no para anclar un tamano de efecto"),
        )

    clave_des = (desenlace or "").lower().strip()
    candidatos: list[dict] = []
    halladas: list[Magnitud] = []   # lo que la fuente SI dice, para contrastar

    for i, m in enumerate(medidas):
        titulo = (m.get("title") or "")
        if clave_des and clave_des not in titulo.lower() and clave_des not in (
                m.get("description") or "").lower():
            continue
        for j, an in enumerate(m.get("analyses", []) or []):
            cand = _magnitud_de_analisis(an)
            if cand is None:
                continue
            ruta = (f"resultsSection.outcomeMeasuresModule.outcomeMeasures[{i}]"
                    f".analyses[{j}]")
            candidatos.append({"ruta": ruta, "titulo": titulo,
                               "magnitud": str(cand), "param": an.get("paramType")})
            if cand.clase is magnitud.clase:
                halladas.append(cand)
            ac = comparar(cand, magnitud, tol)
            if ac in (Acuerdo.IDENTICO, Acuerdo.EQUIVALENTE, Acuerdo.COMPATIBLE):
                a = _ancla_ensayo(nct_id, cand, True)
                a.cita_corta = _recorte(titulo, 20)
                a.fecha_consulta = _ultima_actualizacion(doc)
                return ResultadoAnclaje(ancla=a, coincide=ac, ruta=ruta,
                                        encontrado=cand, candidatos=candidatos,
                                        motivo=f"coincide ({ac.value}) en {ruta}")

    # Si la fuente SI trae una magnitud de la misma clase y no coincide, el ancla
    # queda VERIFICADA con el valor de la fuente, no con el afirmado. Lo que se
    # verifico es lo que dice el registro; que la afirmacion lo contradiga es un
    # hallazgo distinto, y es la atestiguacion la que lo convierte en NEGRO. Sin
    # esto, una cifra que contradice su propia fuente se degradaria a un simple
    # "sin ancla" y se mostraria como no anclada en vez de bloquearse.
    if halladas:
        from .numeros import agrupar as _agrupar
        grupos = _agrupar(halladas)
        if len(grupos) > 1:
            return ResultadoAnclaje(
                ancla=_ancla_ensayo(nct_id, magnitud, False), coincide=None,
                candidatos=candidatos,
                motivo=(f"el registro trae {len(grupos)} medidas de clase "
                        f"{magnitud.clase.value} que no concuerdan entre si: hace falta "
                        f"precisar el desenlace antes de concluir"),
            )
        a = _ancla_ensayo(nct_id, halladas[0], True)
        a.fecha_consulta = _ultima_actualizacion(doc)
        return ResultadoAnclaje(
            ancla=a, coincide=Acuerdo.DISCREPANTE, candidatos=candidatos,
            encontrado=halladas[0],
            motivo=(f"el registro dice {halladas[0]} y la afirmacion dice {magnitud}: "
                    f"el ancla se verifica con el valor de la fuente y la afirmacion "
                    f"queda contradicha"),
        )
    return ResultadoAnclaje(
        ancla=_ancla_ensayo(nct_id, magnitud, False), coincide=None,
        candidatos=candidatos,
        motivo=(f"el registro publico {len(candidatos)} analisis pero ninguno de clase "
                f"{magnitud.clase.value}" if candidatos else
                "no se hallo ningun analisis con medida de efecto en el desenlace pedido"),
    )


def _magnitud_de_analisis(an: dict) -> Optional[Magnitud]:
    """Convierte un bloque analyses[] de ClinicalTrials.gov en una Magnitud."""
    param = (an.get("paramType") or "").strip().lower()
    valor = an.get("paramValue")
    if valor is None:
        return None
    try:
        v = float(str(valor).replace(",", ""))
    except (TypeError, ValueError):
        return None
    clase = PARAM_A_CLASE.get(param)
    if clase is None:
        return None
    if clase is Clase.REDUCCION_ABS and abs(v) > 1:
        v = v / 100.0            # la diferencia de riesgo viene en puntos porcentuales
    m = Magnitud(clase=clase, valor=v, bruto=f"{an.get('paramType')} {valor}")
    for campo, destino in (("ciLowerLimit", "ic_inf"), ("ciUpperLimit", "ic_sup")):
        bruto = an.get(campo)
        if bruto is None:
            continue
        try:
            lim = float(str(bruto).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if clase is Clase.REDUCCION_ABS and abs(lim) > 1:
            lim = lim / 100.0
        setattr(m, destino, lim)
    return m


def _ultima_actualizacion(doc: dict) -> str:
    return ((doc.get("protocolSection", {})
                .get("statusModule", {})
                .get("lastUpdatePostDateStruct", {}) or {}).get("date", "") or "")


def _ancla_ensayo(nct: str, mag: Optional[Magnitud], verificada: bool) -> Ancla:
    return Ancla(
        tipo=TipoAncla.REGISTRO_ENSAYO, localizador=nct,
        url=f"https://clinicaltrials.gov/study/{nct}", magnitud=mag,
        licencia="licencia expresa de ClinicalTrials.gov, otorgada a cualquiera sin cargo",
        verificada=verificada,
    )


# ---------------------------------------------------------------------------
# Anclaje en etiqueta de farmaco
# ---------------------------------------------------------------------------


def anclar_en_etiqueta(generico: str, magnitud: Magnitud, fetcher: Fetcher,
                       tipo_hecho: str = "dosis", tol: float = 0.02,
                       pista: str = "") -> ResultadoAnclaje:
    """Busca la magnitud en la prosa de la etiqueta del farmaco.

    openFDA no expone los cortes renales ni las dosis como campos: hay que
    parsearlos del texto. El procedimiento es: traer la etiqueta, aislar las
    secciones donde puede estar la cifra, partirlas en oraciones, parsear cada
    oracion con harness.numeros y comparar. Cuando coincide se guarda el campo,
    el desplazamiento y hasta 20 palabras textuales, que es lo que permite a una
    persona repetir la verificacion.
    """
    url = (f"{FDA_BASE}?search=openfda.generic_name:%22{urllib_quote(generico)}%22"
           f"&limit=1")
    try:
        doc = fetcher.get(url)
    except AnclajeImposible as e:
        return ResultadoAnclaje(ancla=_ancla_etiqueta(generico, "", magnitud, False),
                                coincide=None, motivo=str(e))

    resultados = doc.get("results") or []
    if not resultados:
        return ResultadoAnclaje(
            ancla=_ancla_etiqueta(generico, "", magnitud, False), coincide=None,
            motivo=f"openFDA no devolvio etiqueta para el generico '{generico}'")

    etiqueta = resultados[0]
    spl = ((etiqueta.get("openfda") or {}).get("spl_set_id") or [""])[0]
    campos = CAMPOS_ETIQUETA.get(tipo_hecho, ["dosage_and_administration"])
    candidatos: list[dict] = []
    halladas: list[Magnitud] = []
    clave = (pista or "").lower().strip()

    for campo in campos:
        for k, bloque in enumerate(etiqueta.get(campo) or []):
            for frase, inicio in _oraciones(bloque):
                if clave and clave not in frase.lower():
                    continue
                for cand in parsear(frase, clase_sugerida=magnitud.clase):
                    candidatos.append({"campo": f"{campo}[{k}]", "offset": inicio,
                                       "magnitud": str(cand),
                                       "frase": _recorte(frase, 25)})
                    if cand.clase is magnitud.clase:
                        halladas.append((cand, f"results[0].{campo}[{k}] offset {inicio}",
                                         frase))
                    ac = comparar(cand, magnitud, tol)
                    if ac in (Acuerdo.IDENTICO, Acuerdo.EQUIVALENTE, Acuerdo.COMPATIBLE):
                        a = _ancla_etiqueta(generico, spl, cand, True)
                        a.cita_corta = _recorte(frase, 20)
                        ruta = f"results[0].{campo}[{k}] offset {inicio}"
                        return ResultadoAnclaje(ancla=a, coincide=ac, ruta=ruta,
                                                encontrado=cand, candidatos=candidatos,
                                                motivo=f"coincide ({ac.value}) en {ruta}")

    # Solo se auto-verifica cuando lo hallado es INEQUIVOCO. Si la seccion trae
    # varias magnitudes de la misma clase que no concuerdan entre si (una dosis
    # inicial y una maxima, por ejemplo), elegir una para declarar contradiccion
    # seria inventar el hallazgo. Lo honesto es devolver los candidatos y pedir
    # una pista que desambigue.
    if halladas:
        from .numeros import agrupar as _agrupar
        grupos = _agrupar([c for c, _, _ in halladas])
        if len(grupos) > 1:
            return ResultadoAnclaje(
                ancla=_ancla_etiqueta(generico, spl, magnitud, False),
                coincide=None, candidatos=candidatos,
                motivo=(f"la seccion trae {len(grupos)} magnitudes de clase "
                        f"{magnitud.clase.value} que no concuerdan entre si "
                        f"({', '.join(str(g[0]) for g in grupos)}): hace falta una pista "
                        f"para desambiguar antes de declarar coincidencia o contradiccion"),
            )
        cand, ruta, frase = halladas[0]
        a = _ancla_etiqueta(generico, spl, cand, True)
        a.cita_corta = _recorte(frase, 20)
        return ResultadoAnclaje(
            ancla=a, coincide=Acuerdo.DISCREPANTE, candidatos=candidatos,
            encontrado=cand, ruta=ruta,
            motivo=(f"la etiqueta dice {cand} y la afirmacion dice {magnitud}: el ancla "
                    f"se verifica con el valor de la etiqueta y la afirmacion queda "
                    f"contradicha"),
        )
    return ResultadoAnclaje(
        ancla=_ancla_etiqueta(generico, spl, magnitud, False),
        coincide=None, candidatos=candidatos,
        motivo=(f"se parsearon {len(candidatos)} magnitudes en las secciones {campos} "
                f"pero ninguna de clase {magnitud.clase.value}" if candidatos else
                f"no se parseo ninguna magnitud de clase {magnitud.clase.value} en {campos}"),
    )


def _ancla_etiqueta(generico: str, spl: str, mag: Optional[Magnitud],
                    verificada: bool) -> Ancla:
    return Ancla(
        tipo=TipoAncla.ETIQUETA_REGULADOR,
        localizador=f"SPL:{spl}" if spl else f"etiqueta:{generico}",
        url=(f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={spl}"
             if spl else FDA_BASE),
        magnitud=mag, licencia="CC0 1.0 (openFDA)", verificada=verificada,
    )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def urllib_quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s.strip())


# Corta tras un punto seguido de mayuscula o parentesis, y tambien ANTES de un
# numero de seccion del formato PLR ("2.1", "8.6", "12.1"), que es como estan
# estructuradas las etiquetas de la FDA.
_FIN_ORACION = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])|(?<=[.;:])\s+(?=\d+\.\d+\s+[A-Z])")

# Numero de seccion al inicio de una oracion. Hay que quitarlo antes de parsear:
# "2.1 Recommended Dosage" se leeria como una dosis de 2.1 mg, que es exactamente
# el tipo de cifra fantasma que envenena una boveda.
_NUM_SECCION = re.compile(r"^\d{1,2}(?:\.\d{1,2}){0,2}\s+(?=[A-Z])")


def _oraciones(texto: str) -> list[tuple[str, int]]:
    """Parte un bloque de prosa en oraciones con su desplazamiento.

    El desplazamiento importa: es lo que permite senalar el lugar exacto del
    documento donde se leyo la cifra, y por tanto re-verificarla. Se calcula
    sobre el texto ORIGINAL, no sobre el limpiado, para que siga apuntando al
    documento real.
    """
    out: list[tuple[str, int]] = []
    pos = 0
    for trozo in _FIN_ORACION.split(texto or ""):
        if trozo and trozo.strip():
            limpio = _NUM_SECCION.sub("", trozo.strip())
            desplazamiento = pos + (len(trozo) - len(trozo.lstrip()))
            out.append((limpio, desplazamiento))
        pos += len(trozo or "") + 1
    return out


def _recorte(texto: str, palabras: int) -> str:
    """Recorta a un maximo de palabras.

    El limite no es estetico: la cita corta se guarda al amparo del derecho de
    cita del articulo 148 de la Ley Federal del Derecho de Autor, que exige que
    lo citado no constituya una reproduccion sustancial. Veinte palabras de un
    documento de dominio publico sobran de margen; el limite esta ahi para que
    el mismo codigo siga siendo seguro cuando la fuente no sea de dominio
    publico.
    """
    ws = (texto or "").split()
    return " ".join(ws[:palabras]) + ("..." if len(ws) > palabras else "")


def necesita_refresco(ancla: Ancla, hoy: str, dias: int = 30) -> bool:
    """True si el ancla llego a su limite de frescura.

    Existe por una obligacion concreta: los terminos de ClinicalTrials.gov
    exigen mantener los datos actualizados en todo momento mientras se retengan.
    Cumplirlo es una tarea programada de sincronizacion delta, no una promesa.
    `hoy` se recibe como parametro en vez de leerse del reloj para que el
    anclaje sea reproducible y las pruebas deterministas.
    """
    if not ancla.fecha_consulta:
        return True
    try:
        from datetime import date
        f = date.fromisoformat(ancla.fecha_consulta[:10])
        h = date.fromisoformat(hoy[:10])
    except ValueError:
        return True
    return (h - f).days >= dias


def aplicar_anclaje(hecho, resultados: list[ResultadoAnclaje]) -> None:
    """Reemplaza las anclas del hecho por el resultado real del anclaje.

    Deliberadamente destructivo: un hecho no conserva una ancla que se declaro
    sin comprobar. Si el anclaje no pudo verificarse, el hecho se queda sin ancla
    y la atestiguacion lo mandara como maximo a AMBAR. Es la unica forma de que
    `verificada` signifique algo.
    """
    hecho.anclas = [r.ancla for r in resultados]
    hecho.diagnostico.setdefault("anclaje", [])
    hecho.diagnostico["anclaje"] = [
        {"localizador": r.ancla.localizador, "verificada": r.ancla.verificada,
         "coincide": r.coincide.value if r.coincide else None,
         "ruta": r.ruta, "motivo": r.motivo}
        for r in resultados
    ]


__all__ = [
    "Fetcher", "FetcherHTTP", "FetcherOffline", "AnclajeImposible",
    "ResultadoAnclaje", "anclar_en_ensayo", "anclar_en_etiqueta",
    "necesita_refresco", "aplicar_anclaje", "CAMPOS_ETIQUETA", "PARAM_A_CLASE",
]
