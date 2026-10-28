"""Normalizacion y equivalencia semantica de magnitudes clinicas.

El problema que resuelve este modulo: la verificacion de hechos basada en texto
(NLI, similitud de embeddings, coincidencia de cadenas) falla con numeros.

    "HR 0.61 (95% CI 0.51-0.72)"
    "hazard ratio de 0,61"
    "reduccion del riesgo relativo del 39%"

son el mismo hecho con tres redacciones distintas, y un verificador textual los
trata como tres hechos diferentes. Al reves, "10 mg" y "100 mg" tienen una
similitud textual altisima y son un error de un orden de magnitud.

Por eso la Boveda compara magnitudes, no cadenas: parsea, convierte a unidad
canonica, aplica equivalencias conocidas entre medidas de efecto y compara con
tolerancia relativa y solape de intervalos de confianza.

Sin dependencias externas. Python 3.9+.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Clases de magnitud
# ---------------------------------------------------------------------------


class Clase(str, Enum):
    """Familia semantica de la magnitud. Determina con que se puede comparar."""

    RAZON_RIESGO = "razon_riesgo"        # HR, RR, OR, SHR
    REDUCCION_REL = "reduccion_relativa"  # RRR, "reduccion del 39%"
    REDUCCION_ABS = "reduccion_absoluta"  # ARR, diferencia de riesgo
    NNT = "nnt"                           # numero necesario a tratar
    PROPORCION = "proporcion"             # incidencia, prevalencia, FEVI, %
    DOSIS = "dosis"                       # masa por toma o por dia
    CONCENTRACION = "concentracion"       # mg/dL, mmol/L, mEq/L
    PRESION = "presion"                   # mmHg
    TFG = "tfg"                           # mL/min/1.73 m2
    TIEMPO = "tiempo"                     # minutos, horas, dias
    CONTEO = "conteo"                     # n de pacientes, puntos de una escala
    ADIMENSIONAL = "adimensional"         # indices sin unidad


class Comparador(str, Enum):
    IGUAL = "="
    MENOR = "<"
    MENOR_IGUAL = "<="
    MAYOR = ">"
    MAYOR_IGUAL = ">="
    RANGO = "rango"


# ---------------------------------------------------------------------------
# Tabla de unidades: factor hacia la unidad canonica de cada familia
# ---------------------------------------------------------------------------

# familia -> (unidad_canonica, {alias: factor})
_UNIDADES: dict[str, tuple[str, dict[str, float]]] = {
    "masa": (
        "mg",
        {
            "kg": 1e6, "g": 1e3, "mg": 1.0,
            "mcg": 1e-3, "ug": 1e-3, "µg": 1e-3, "microgramos": 1e-3, "microgramo": 1e-3,
            "ng": 1e-6, "ui": 1.0, "u": 1.0, "unidades": 1.0,  # UI no convertible: se mantiene aparte
        },
    ),
    "volumen": ("ml", {"l": 1e3, "litro": 1e3, "litros": 1e3, "dl": 100.0, "ml": 1.0, "cc": 1.0}),
    "presion": ("mmhg", {"mmhg": 1.0, "mm hg": 1.0, "torr": 1.0, "kpa": 7.50062, "cmh2o": 0.735559}),
    "tiempo": (
        "min",
        {
            "s": 1 / 60, "seg": 1 / 60, "segundo": 1 / 60, "segundos": 1 / 60,
            "min": 1.0, "minuto": 1.0, "minutos": 1.0,
            "h": 60.0, "hr": 60.0, "hora": 60.0, "horas": 60.0,
            "d": 1440.0, "dia": 1440.0, "dias": 1440.0,
            "sem": 10080.0, "semana": 10080.0, "semanas": 10080.0,
            "mes": 43200.0, "meses": 43200.0,
            "ano": 525600.0, "anos": 525600.0, "year": 525600.0, "years": 525600.0,
        },
    ),
    "tfg": (
        "ml/min/1.73m2",
        {
            "ml/min/1.73m2": 1.0, "ml/min/1,73m2": 1.0, "ml/min/1.73 m2": 1.0,
            "ml/min/1.73m²": 1.0, "ml/min": 1.0, "ml/min/173m2": 1.0,
        },
    ),
}

# Concentraciones: la conversion mg/dL <-> mmol/L depende del analito.
# Factor = peso molecular / 10 (para pasar mmol/L a mg/dL).
_PESO_MOLECULAR = {
    "glucosa": 18.016,
    "colesterol": 38.67,
    "ldl": 38.67,
    "hdl": 38.67,
    "trigliceridos": 88.57,
    "creatinina": 0.0113,  # mg/dL = umol/L * 0.0113
    "urea": 6.006,
    "bilirrubina": 58.467,
    "calcio": 4.008,
    "acido urico": 16.81,
    "lactato": 9.009,
}

_ALIAS_RAZON = {
    "hr": Clase.RAZON_RIESGO, "hazard ratio": Clase.RAZON_RIESGO, "razon de riesgo": Clase.RAZON_RIESGO,
    "rr": Clase.RAZON_RIESGO, "riesgo relativo": Clase.RAZON_RIESGO, "risk ratio": Clase.RAZON_RIESGO,
    "relative risk": Clase.RAZON_RIESGO, "rate ratio": Clase.RAZON_RIESGO,
    "subdistribution hazard ratio": Clase.RAZON_RIESGO,
    "or": Clase.RAZON_RIESGO, "odds ratio": Clase.RAZON_RIESGO, "razon de momios": Clase.RAZON_RIESGO,
    "shr": Clase.RAZON_RIESGO, "sub-hazard ratio": Clase.RAZON_RIESGO,
    "irr": Clase.RAZON_RIESGO, "incidence rate ratio": Clase.RAZON_RIESGO,
}

_ALIAS_REDUCCION = {
    "rrr": Clase.REDUCCION_REL, "reduccion del riesgo relativo": Clase.REDUCCION_REL,
    "reduccion relativa": Clase.REDUCCION_REL, "relative risk reduction": Clase.REDUCCION_REL,
    "arr": Clase.REDUCCION_ABS, "reduccion absoluta del riesgo": Clase.REDUCCION_ABS,
    "absolute risk difference": Clase.REDUCCION_ABS,
    "reduccion absoluta": Clase.REDUCCION_ABS, "diferencia de riesgo": Clase.REDUCCION_ABS,
    "absolute risk reduction": Clase.REDUCCION_ABS, "risk difference": Clase.REDUCCION_ABS,
}

# Alias de medidas de efecto ordenados por longitud descendente, para que la
# cadena mas especifica gane sobre su subcadena.
_ALIAS_EFECTO: list[tuple[str, "Clase"]] = sorted(
    list(_ALIAS_RAZON.items()) + list(_ALIAS_REDUCCION.items()),
    key=lambda kv: len(kv[0]),
    reverse=True,
)

# Rangos plausibles por clase. Una magnitud fuera de rango es un error de
# parseo, no un hallazgo: la Boveda prefiere no devolver nada antes que
# devolver un numero mal clasificado.
_PLAUSIBLE: dict[str, tuple[float, float]] = {
    "razon_riesgo": (0.01, 20.0),
    "reduccion_relativa": (0.0, 1.0),
    "reduccion_absoluta": (0.0, 1.0),
    "nnt": (1.0, 1e6),
    "proporcion": (0.0, 100.0),
    "presion": (20.0, 320.0),
    "tfg": (0.0, 250.0),
}

# Frecuencias de administracion -> tomas por dia
_FRECUENCIA = {
    "qd": 1, "od": 1, "una vez al dia": 1, "cada 24 h": 1, "c/24h": 1, "c24h": 1,
    "diario": 1, "diaria": 1, "al dia": 1, "once daily": 1, "1 vez al dia": 1,
    "bid": 2, "dos veces al dia": 2, "cada 12 h": 2, "c/12h": 2, "c12h": 2,
    "twice daily": 2, "2 veces al dia": 2,
    "tid": 3, "tres veces al dia": 3, "cada 8 h": 3, "c/8h": 3, "c8h": 3, "3 veces al dia": 3,
    "qid": 4, "cuatro veces al dia": 4, "cada 6 h": 4, "c/6h": 4, "c6h": 4, "4 veces al dia": 4,
    "cada 4 h": 6, "c/4h": 6, "cada 48 h": 0.5, "cada 72 h": 1 / 3,
    "semanal": 1 / 7, "una vez a la semana": 1 / 7, "weekly": 1 / 7, "cada semana": 1 / 7,
}


# ---------------------------------------------------------------------------
# Magnitud
# ---------------------------------------------------------------------------


@dataclass
class Magnitud:
    """Una magnitud clinica normalizada y comparable."""

    clase: Clase
    valor: float
    unidad: Optional[str] = None          # unidad canonica de la familia
    ic_inf: Optional[float] = None
    ic_sup: Optional[float] = None
    comparador: Comparador = Comparador.IGUAL
    valor_sup: Optional[float] = None     # limite superior cuando comparador=RANGO
    analito: Optional[str] = None         # para concentraciones
    por_dia: Optional[float] = None       # dosis diaria total normalizada
    etiqueta: Optional[str] = None        # sistolica / diastolica / etc
    bruto: str = ""

    def dict(self) -> dict:
        d = asdict(self)
        d["clase"] = self.clase.value
        d["comparador"] = self.comparador.value
        return d

    def __str__(self) -> str:
        cmp_ = "" if self.comparador is Comparador.IGUAL else self.comparador.value
        if self.comparador is Comparador.RANGO:
            base = f"{_fmt(self.valor)}-{_fmt(self.valor_sup)}"
        else:
            base = f"{cmp_}{_fmt(self.valor)}"
        u = f" {self.unidad}" if self.unidad else ""
        ic = ""
        if self.ic_inf is not None and self.ic_sup is not None:
            ic = f" (IC95 {_fmt(self.ic_inf)}-{_fmt(self.ic_sup)})"
        et = f" [{self.etiqueta}]" if self.etiqueta else ""
        return f"{self.clase.value}:{base}{u}{ic}{et}"


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "?"
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f"{v:g}"


# ---------------------------------------------------------------------------
# Parseo
# ---------------------------------------------------------------------------


# El punto medio como separador decimal (0·63) es el estilo de The Lancet y de
# varias revistas britanicas. No se puede sustituir a ciegas, porque el mismo
# caracter se usa como signo de multiplicacion y como vineta: solo cuenta cuando
# esta ENTRE DIGITOS. Antes de este arreglo, "RR 0·63" se parseaba como 0, es
# decir corrupcion silenciosa, que es peor que no parsear: el valor real se
# perdia y quedaba en su lugar un numero plausible y equivocado. Se descubrio
# corriendo el parser sobre texto real de PMC, no en una prueba sintetica.
_PUNTO_MEDIO = re.compile("(?<=\\d)[\u00b7\u2022\u2027\u22c5\u2219](?=\\d)")


def _norm_texto(s: str) -> str:
    """Minusculas, sin acentos, guiones y simbolos unificados."""
    s = _PUNTO_MEDIO.sub(".", s or "")
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    s = s.replace("≤", "<=").replace("≥", ">=").replace("²", "2")
    s = s.replace("µ", "u").replace("μ", "u")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _a_float(tok: str) -> Optional[float]:
    """Convierte un token numerico a float resolviendo coma decimal vs millares.

    Reglas:
      - Si hay punto y coma, la coma es separador de millares.
      - Si solo hay coma y le siguen exactamente 3 digitos y la parte entera
        tiene 1 a 3 digitos distintos de "0", es separador de millares.
      - En cualquier otro caso con coma, la coma es decimal.
    """
    tok = tok.strip().replace(" ", "")
    if not tok:
        return None
    tiene_punto = "." in tok
    tiene_coma = "," in tok
    if tiene_punto and tiene_coma:
        # el separador que aparece ultimo es el decimal
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")   # 1.234,5 -> 1234.5
        else:
            tok = tok.replace(",", "")                      # 1,234.5 -> 1234.5
    elif tiene_coma:
        entero, _, dec = tok.rpartition(",")
        if len(dec) == 3 and entero.isdigit() and 1 <= len(entero) <= 3 and entero != "0":
            tok = tok.replace(",", "")
        else:
            tok = tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return None


_NUM = r"[0-9]+(?:[.,][0-9]+)?"
# Dos ordenes, los dos reales y los dos frecuentes:
#   "IC 95% 0.51-0.72"  /  "95% CI 0.58-0.75"  /  "95%CI 0.58-0.69"
# El parentesis es OPCIONAL en ambos. Exigirlo en el segundo orden hacia que
# "HR 0.66, 95% CI 0.58-0.75" perdiera el intervalo en silencio, y el intervalo
# es justo lo que sostiene las comparaciones por solape y el peso de confianza.
_SEP_IC = r"(?:\s*(?:-|a|to|,|hasta)\s*)"
_RE_IC = re.compile(
    r"\(?\s*(?:ic|ci|intervalo\s+de\s+confianza|confidence\s+interval)\s*(?:del?\s*)?9[05](?:[.,]\d+)?\s*%?\s*"
    r"[:=,]?\s*(" + _NUM + r")" + _SEP_IC + r"(" + _NUM + r")\s*\)?"
    r"|\(?\s*9[05](?:[.,]\d+)?\s*%\s*(?:ic|ci|intervalo\s+de\s+confianza|confidence\s+interval|conf\.?\s*int\.?)\s*"
    r"[:=,]?\s*(" + _NUM + r")" + _SEP_IC + r"(" + _NUM + r")\s*\)?",
    re.I,
)


def _extraer_ic(texto: str) -> tuple[Optional[float], Optional[float]]:
    m = _RE_IC.search(texto)
    if not m:
        return None, None
    g = [x for x in m.groups() if x is not None]
    if len(g) >= 2:
        return _a_float(g[0]), _a_float(g[1])
    return None, None


def _familia_unidad(u: str) -> tuple[Optional[str], Optional[float]]:
    """Devuelve (familia, factor) para una unidad textual."""
    u = u.strip().lower().replace(" ", "")
    for fam, (_canon, alias) in _UNIDADES.items():
        for a, f in alias.items():
            if u == a.replace(" ", ""):
                return fam, f
    return None, None


def _frecuencia_por_dia(texto: str) -> Optional[float]:
    t = _norm_texto(texto)
    mejor = None
    for k, v in _FRECUENCIA.items():
        if k in t:
            # prefiere la coincidencia mas larga (mas especifica)
            if mejor is None or len(k) > mejor[0]:
                mejor = (len(k), v)
    return mejor[1] if mejor else None


_RE_PRESION = re.compile(r"(?P<cmp><=|>=|<|>)?\s*(?P<sis>\d{2,3})\s*/\s*(?P<dia>\d{2,3})\s*(?:mm\s*hg)?")
_RE_TFG = re.compile(
    r"(?P<cmp><=|>=|<|>)?\s*(?P<v>" + _NUM + r")\s*ml\s*/\s*min(?:\s*/\s*1[.,]?73\s*m2?)?", re.I
)
# (?<![A-Za-z0-9]) evita capturar el "1" de "HbA1c" o el numero dentro de "NCT03036150";
# (?![A-Za-z0-9]) cierra sin usar \b, que falla cuando la unidad termina en "%".
_RE_SIMPLE = re.compile(
    r"(?P<cmp><=|>=|<|>)?\s*(?<![A-Za-z0-9])(?P<v>" + _NUM + r")\s*"
    r"(?P<u>%|mg/dl|mmol/l|meq/l|umol/l|mg|mcg|ug|kg|ng|g|ml|dl|l|mmhg|kpa|puntos|punto|pts|pt|ui|u)?"
    r"(?![A-Za-z0-9])",
    re.I,
)
_RE_RANGO = re.compile(
    r"(?:entre\s+)?(?<![A-Za-z0-9])(" + _NUM + r")"
    r"(?:\s*-\s*|\s+(?:a|to|y)\s+)(" + _NUM + r")\s*"
    r"(%|mg/dl|mmol/l|mmhg|mg)?(?![A-Za-z0-9])",
    re.I,
)


def parsear(texto: str, clase_sugerida: Optional[Clase] = None,
            analito: Optional[str] = None) -> list[Magnitud]:
    """Extrae magnitudes de un texto y descarta las fisicamente implausibles."""
    return [m for m in _parsear_bruto(texto, clase_sugerida, analito) if plausible(m)]


def _parsear_bruto(texto: str, clase_sugerida: Optional[Clase] = None,
                   analito: Optional[str] = None) -> list[Magnitud]:
    """Extrae todas las magnitudes reconocibles de un fragmento de texto.

    No pretende cubrir todo el lenguaje clinico: cubre las formas en que de
    hecho se escriben umbrales, dosis y tamanos de efecto en guias, etiquetas
    de farmaco y abstracts. Lo que no reconoce devuelve lista vacia, y eso es
    una senal para el harness, no un error silencioso.
    """
    t = _norm_texto(texto)
    out: list[Magnitud] = []
    ic_inf, ic_sup = _extraer_ic(t)

    # 1. Medidas de efecto por alias explicito (HR, RR, OR, RRR, ARR, NNT).
    # Orden por longitud descendente: "reduccion del riesgo relativo" debe
    # probarse antes que "riesgo relativo", que es su subcadena y la secuestraria.
    for alias, clase in _ALIAS_EFECTO:
        # el conector mas largo va primero: "del" antes de "de", si no "de" consume
        # el prefijo y deja la "l" bloqueando el numero.
        # Admite una abreviatura entre corchetes o parentesis entre el alias y el
        # numero, porque asi se escribe de verdad en la literatura:
        # "relative risk [RR] 0.63", "hazard ratio (HR) 0.61".
        pat = re.compile(
            r"\b" + re.escape(alias) + r"\b\s*(?:\[[^\]]{0,18}\]|\([^)]{0,18}\))?\s*"
            r"(?:fue de|del|de|en|=|:|was|of)?\s*[:=]?\s*(" + _NUM + r")",
            re.I,
        )
        m = pat.search(t)
        if m:
            v = _a_float(m.group(1))
            if v is None:
                continue
            if clase in (Clase.REDUCCION_REL, Clase.REDUCCION_ABS) and v > 1:
                v = v / 100.0  # "RRR 39" o "RRR 39%" -> 0.39
            cand = Magnitud(clase=clase, valor=v, ic_inf=ic_inf, ic_sup=ic_sup, bruto=texto)
            if plausible(cand):
                out.append(cand)
                break

    # "reduccion del 39%" sin alias
    if not out:
        m = re.search(r"reduc\w*\s+(?:del?\s+)?(?:riesgo\s+)?(?:relativ\w+\s+)?(?:en\s+)?(" + _NUM + r")\s*%", t)
        if m:
            v = _a_float(m.group(1))
            if v is not None:
                out.append(Magnitud(clase=Clase.REDUCCION_REL, valor=v / 100.0,
                                    ic_inf=ic_inf, ic_sup=ic_sup, bruto=texto))

    # NNT
    m = re.search(r"\bnnt\b\s*(?:de|=|:)?\s*(" + _NUM + r")", t)
    if m:
        v = _a_float(m.group(1))
        if v is not None:
            out.append(Magnitud(clase=Clase.NNT, valor=v, bruto=texto))

    if out:
        return out

    # 2. Presion arterial compuesta: 130/80
    m = _RE_PRESION.search(t)
    if m and ("mmhg" in t or "presion" in t or "pa " in t or "tension" in t or "/" in m.group(0)):
        cmp_ = _cmp(m.group("cmp"))
        out.append(Magnitud(Clase.PRESION, float(m.group("sis")), "mmhg",
                            comparador=cmp_, etiqueta="sistolica", bruto=texto))
        out.append(Magnitud(Clase.PRESION, float(m.group("dia")), "mmhg",
                            comparador=cmp_, etiqueta="diastolica", bruto=texto))
        return out

    # 3. Tasa de filtracion glomerular
    m = _RE_TFG.search(t)
    if m:
        v = _a_float(m.group("v"))
        if v is not None:
            out.append(Magnitud(Clase.TFG, v, "ml/min/1.73m2",
                                comparador=_cmp(m.group("cmp")), bruto=texto))
            return out

    # 4. Rango explicito (el separador ya es obligatorio en la expresion)
    m = _RE_RANGO.search(t)
    if m:
        lo, hi = _a_float(m.group(1)), _a_float(m.group(2))
        if lo is not None and hi is not None and hi > lo:
            clase, unidad = _clasificar(m.group(3), clase_sugerida, analito)
            if clase is not None:
                out.append(Magnitud(clase, lo, unidad, comparador=Comparador.RANGO,
                                    valor_sup=hi, analito=analito, bruto=texto))
                return out

    # 5. Magnitud simple con unidad
    for m in _RE_SIMPLE.finditer(t):
        v = _a_float(m.group("v"))
        if v is None:
            continue
        u_txt = (m.group("u") or "").strip()
        clase, unidad = _clasificar(u_txt, clase_sugerida, analito)
        if clase is None:
            continue
        mag = Magnitud(clase, v, unidad, comparador=_cmp(m.group("cmp")),
                       analito=analito, ic_inf=ic_inf, ic_sup=ic_sup, bruto=texto)
        # convierte a unidad canonica de su familia
        fam, factor = _familia_unidad(u_txt) if u_txt else (None, None)
        if fam and factor and factor != 1.0:
            mag.valor = v * factor
            mag.unidad = _UNIDADES[fam][0]
        if clase is Clase.DOSIS:
            f = _frecuencia_por_dia(texto)
            if f:
                mag.por_dia = mag.valor * f
        out.append(mag)
        break  # una magnitud por fragmento: el harness fragmenta antes

    return out


def plausible(m: Magnitud) -> bool:
    """True si la magnitud cae en el rango fisicamente posible de su clase.

    Un HR de 39 o una presion de 4 son errores de parseo o de extraccion. La
    Boveda los descarta en origen: un hecho ausente es recuperable, un hecho
    mal clasificado contamina todo lo que se derive de el.
    """
    rango = _PLAUSIBLE.get(m.clase.value)
    if rango is None:
        return True
    lo, hi = rango
    if not (lo <= m.valor <= hi):
        return False
    for v in (m.ic_inf, m.ic_sup, m.valor_sup):
        if v is not None and not (lo <= v <= hi):
            return False
    return True


def _cmp(s: Optional[str]) -> Comparador:
    return {
        "<": Comparador.MENOR, "<=": Comparador.MENOR_IGUAL,
        ">": Comparador.MAYOR, ">=": Comparador.MAYOR_IGUAL,
    }.get((s or "").strip(), Comparador.IGUAL)


def _clasificar(u: str, sugerida: Optional[Clase],
                analito: Optional[str]) -> tuple[Optional[Clase], Optional[str]]:
    u = (u or "").strip().lower()
    if u == "%":
        return Clase.PROPORCION, "%"
    if u in ("mg/dl", "mmol/l", "meq/l", "umol/l"):
        return Clase.CONCENTRACION, u
    if u in ("mg", "g", "kg", "mcg", "ug", "ng", "ui", "u"):
        return Clase.DOSIS, "mg"
    if u in ("ml", "l", "dl", "cc"):
        return Clase.DOSIS, "ml"
    if u in ("mmhg", "kpa"):
        return Clase.PRESION, "mmhg"
    if u in ("punto", "puntos", "pt", "pts"):
        return Clase.CONTEO, "puntos"
    if u == "" and sugerida is not None:
        canon = {
            Clase.PRESION: "mmhg", Clase.TFG: "ml/min/1.73m2",
            Clase.PROPORCION: "%", Clase.DOSIS: "mg",
        }.get(sugerida)
        return sugerida, canon
    if u == "":
        return None, None
    return Clase.ADIMENSIONAL, None


# ---------------------------------------------------------------------------
# Equivalencias entre clases
# ---------------------------------------------------------------------------


def equivalentes(a: Magnitud, b: Magnitud, tol: float = 0.02) -> Optional[bool]:
    """Compara dos magnitudes de clases distintas via equivalencias conocidas.

    Devuelve True si son equivalentes, False si son incompatibles, y None si la
    equivalencia no se puede establecer sin informacion adicional (por ejemplo
    NNT frente a RRR, que requiere el riesgo basal).
    """
    ca, cb = a.clase, b.clase
    if {ca, cb} == {Clase.RAZON_RIESGO, Clase.REDUCCION_REL}:
        razon = a if ca is Clase.RAZON_RIESGO else b
        red = b if ca is Clase.RAZON_RIESGO else a
        return _cerca(1.0 - razon.valor, red.valor, tol)
    if {ca, cb} == {Clase.NNT, Clase.REDUCCION_ABS}:
        nnt = a if ca is Clase.NNT else b
        arr = b if ca is Clase.NNT else a
        if arr.valor <= 0:
            return None
        return _cerca(1.0 / arr.valor, nnt.valor, max(tol, 0.05))
    if {ca, cb} == {Clase.NNT, Clase.REDUCCION_REL}:
        return None  # requiere riesgo basal
    if {ca, cb} == {Clase.PROPORCION, Clase.REDUCCION_REL}:
        prop = a if ca is Clase.PROPORCION else b
        red = b if ca is Clase.PROPORCION else a
        return _cerca(prop.valor / 100.0, red.valor, tol)
    return None


def _cerca(x: float, y: float, tol: float) -> bool:
    if x == y:
        return True
    denom = max(abs(x), abs(y))
    if denom == 0:
        return abs(x - y) <= tol
    return abs(x - y) / denom <= tol


def convertir_concentracion(m: Magnitud, a_unidad: str) -> Optional[Magnitud]:
    """Convierte mg/dL <-> mmol/L usando el peso molecular del analito."""
    if m.clase is not Clase.CONCENTRACION or not m.analito:
        return None
    pm = _PESO_MOLECULAR.get(m.analito.lower())
    if pm is None:
        return None
    u = (m.unidad or "").lower()
    a_unidad = a_unidad.lower()
    if u == a_unidad:
        return m
    if u == "mmol/l" and a_unidad == "mg/dl":
        v = m.valor * pm
    elif u == "mg/dl" and a_unidad == "mmol/l":
        v = m.valor / pm
    elif u == "umol/l" and a_unidad == "mg/dl":
        v = m.valor * pm
    else:
        return None
    nueva = Magnitud(**{**m.dict(), "clase": m.clase, "comparador": m.comparador})
    nueva.valor = v
    nueva.unidad = a_unidad
    if m.ic_inf is not None:
        nueva.ic_inf = m.ic_inf * pm if a_unidad == "mg/dl" else m.ic_inf / pm
    if m.ic_sup is not None:
        nueva.ic_sup = m.ic_sup * pm if a_unidad == "mg/dl" else m.ic_sup / pm
    return nueva


# ---------------------------------------------------------------------------
# Acuerdo
# ---------------------------------------------------------------------------


class Acuerdo(str, Enum):
    IDENTICO = "identico"          # misma clase, misma unidad, valor dentro de tolerancia estricta
    EQUIVALENTE = "equivalente"    # distinta clase o unidad, equivalencia establecida
    COMPATIBLE = "compatible"      # los intervalos de confianza se solapan
    DISCREPANTE = "discrepante"    # misma clase, valores incompatibles
    INCOMPARABLE = "incomparable"  # clases sin puente, o falta informacion


def comparar(a: Magnitud, b: Magnitud, tol: float = 0.02) -> Acuerdo:
    """Compara dos magnitudes y devuelve el tipo de acuerdo."""
    if a.clase is b.clase:
        # presion arterial: solo comparables si la etiqueta coincide
        if a.clase is Clase.PRESION and a.etiqueta and b.etiqueta and a.etiqueta != b.etiqueta:
            return Acuerdo.INCOMPARABLE

        va, vb = a.valor, b.valor
        ua, ub = (a.unidad or ""), (b.unidad or "")

        if a.clase is Clase.CONCENTRACION and ua != ub:
            conv = convertir_concentracion(b, ua)
            if conv is None:
                return Acuerdo.INCOMPARABLE
            vb = conv.valor
            ub = ua

        if ua != ub and not (ua == "" or ub == ""):
            return Acuerdo.INCOMPARABLE

        # dosis: compara dosis diaria total cuando ambas la tienen
        if a.clase is Clase.DOSIS and a.por_dia is not None and b.por_dia is not None:
            va, vb = a.por_dia, b.por_dia

        if a.comparador is not b.comparador and Comparador.IGUAL not in (a.comparador, b.comparador):
            if a.comparador is not b.comparador:
                return Acuerdo.DISCREPANTE

        if _cerca(va, vb, tol):
            return Acuerdo.IDENTICO
        if _solapan(a, b):
            return Acuerdo.COMPATIBLE
        return Acuerdo.DISCREPANTE

    eq = equivalentes(a, b, tol)
    if eq is True:
        return Acuerdo.EQUIVALENTE
    if eq is False:
        return Acuerdo.DISCREPANTE
    return Acuerdo.INCOMPARABLE


def _solapan(a: Magnitud, b: Magnitud) -> bool:
    ra = _intervalo(a)
    rb = _intervalo(b)
    if ra is None or rb is None:
        return False
    return ra[0] <= rb[1] and rb[0] <= ra[1]


def _intervalo(m: Magnitud) -> Optional[tuple[float, float]]:
    if m.ic_inf is not None and m.ic_sup is not None:
        return (m.ic_inf, m.ic_sup)
    if m.comparador is Comparador.RANGO and m.valor_sup is not None:
        return (m.valor, m.valor_sup)
    return None


def agrupar(mags: Iterable[Magnitud], tol: float = 0.02) -> list[list[Magnitud]]:
    """Agrupa magnitudes en clases de equivalencia.

    Dos magnitudes caen en el mismo grupo si su acuerdo es IDENTICO,
    EQUIVALENTE o COMPATIBLE. Se usa para medir consenso entre elicitaciones
    sin depender de la redaccion.
    """
    grupos: list[list[Magnitud]] = []
    for m in mags:
        colocada = False
        for g in grupos:
            if comparar(g[0], m, tol) in (Acuerdo.IDENTICO, Acuerdo.EQUIVALENTE, Acuerdo.COMPATIBLE):
                g.append(m)
                colocada = True
                break
        if not colocada:
            grupos.append([m])
    grupos.sort(key=len, reverse=True)
    return grupos


# Factor a partir del cual una discrepancia deja de ser imprecision y pasa a ser
# un error de categoria. NO es el mismo para todas las clases, y suponer que si
# lo era fue un error de diseno con consecuencias clinicas: en una dosis, un
# factor 2 es una sobredosis, no una aproximacion. El umbral generico de 10 solo
# atrapaba el error de la coma decimal y dejaba pasar el error de la mitad o el
# doble, que es mucho mas frecuente y igual de letal.
FACTOR_ALARMA = {
    "dosis": 1.6,            # media dosis o dosis doble: nunca es imprecision
    "concentracion": 1.8,
    "presion": 1.4,          # 130 frente a 180 es otra conducta clinica
    "tfg": 1.5,              # cruza estadios de enfermedad renal
    "conteo": 2.0,
}
FACTOR_ALARMA_DEFECTO = 9.5  # para razones de riesgo y adimensionales


def factor_de_alarma(clase) -> float:
    nombre = clase.value if hasattr(clase, "value") else str(clase)
    return FACTOR_ALARMA.get(nombre, FACTOR_ALARMA_DEFECTO)


def orden_de_magnitud_distinto(a: Magnitud, b: Magnitud,
                               factor: Optional[float] = None) -> bool:
    """Detecta una discrepancia que ya no es imprecision sino error de categoria.

    Un verificador textual puntua '10 mg' y '100 mg' como casi identicos. Y uno
    con umbral fijo en 10 trata '10 mg' y '20 mg' como una diferencia menor,
    cuando es una dosis doble. El factor depende de la clase.
    """
    if a.clase is not b.clase:
        return False
    va = a.por_dia if a.por_dia is not None else a.valor
    vb = b.por_dia if b.por_dia is not None else b.valor
    if va <= 0 or vb <= 0:
        return False
    f = factor if factor is not None else factor_de_alarma(a.clase)
    return max(va, vb) / min(va, vb) >= f


__all__ = [
    "Clase", "Comparador", "Magnitud", "Acuerdo",
    "parsear", "comparar", "agrupar", "equivalentes", "plausible",
    "convertir_concentracion", "orden_de_magnitud_distinto",
    "FACTOR_ALARMA", "factor_de_alarma",
]
