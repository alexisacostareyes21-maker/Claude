"""La voz de ORIONS: la frontera entre educacion y apoyo a la decision clinica.

Este es el riesgo que puede matar el producto, y es mas urgente que el de
derechos de autor. Una demanda por derechos de autor se pelea; una clasificacion
como software de apoyo a la decision clinica sin registro sanitario cierra el
producto por via administrativa, y no hace falta que nadie gane un juicio.

La frontera no la fija el contenido: la fija la VOZ y el REFERENTE.

    "La NOM-030-SSA2 fija una meta de presion de X"        -> educacion
    "El ensayo Y inscribio pacientes con eGFR de 25 a 75"   -> educacion
    "Inicie un iSGLT2 si el eGFR es mayor o igual a 20"     -> apoyo a la decision
    "Para tu paciente de 54 anos con eGFR 28, la dosis es"  -> dispositivo medico

Las tres diferencias son verificables por codigo:

1. MODO DEONTICO. Un enunciado en imperativo o con "debe" pone a ORIONS como
   emisor de una norma. ORIONS no emite normas: transcribe las de otros,
   atribuidas y ancladas. La misma cifra, dicha en voz propia o en voz atribuida,
   cae a un lado u otro de la frontera.

2. REFERENTE. Un enunciado referido a una poblacion (PICO), a un documento o a
   un mecanismo es educacion. Uno referido a UNA persona concreta es practica
   clinica. El esquema no admite el valor "paciente", y no se puede agregar sin
   revision regulatoria.

3. DERIVACION NO COLAPSABLE. El criterio central de la guia de Clinical Decision
   Support Software de la FDA, en la seccion 520(o)(1)(E) de la Food Drug and
   Cosmetic Act, es que el profesional pueda REVISAR INDEPENDIENTEMENTE las bases
   de la recomendacion. Un modo "respuesta rapida" que muestra la conclusion sin
   la cadena de derivacion y sus anclas destruye exactamente ese criterio. Por
   eso la vista colapsada no es una preferencia de diseno: es la que cruza la
   frontera.

Una consecuencia que conviene aceptar de frente: ORIONS no puede tener un boton
de "dime que hacer". Ese boton es el mas pedido y el mas vendible, y es el que
convierte la plataforma en un dispositivo medico sin registro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class Referente(str, Enum):
    """A que se refiere un enunciado. Enum CERRADO.

    No existe el valor "paciente", y agregarlo no es una decision de ingenieria:
    es un cambio de categoria regulatoria del producto entero.
    """

    POBLACION_PICO = "poblacion_pico"   # un grupo definido por criterios
    DOCUMENTO = "documento"             # lo que dice una fuente
    MECANISMO = "mecanismo"             # fisiologia causal


@dataclass
class Emisor:
    """Quien dice la norma. ORIONS nunca es el emisor.

    Los tres campos son obligatorios juntos. Un enunciado normativo sin cuerpo,
    sin ancla o sin fecha no se almacena ni se muestra: la atribucion incompleta
    equivale a emitirla en voz propia.
    """

    cuerpo: str        # VA/DoD, USPSTF, CDC, etiqueta FDA, NOM-030-SSA2, CENETEC
    ancla: str         # NCT, SPL set id, PMCID, numeral de la norma
    fecha: str         # ISO 8601 o el ano de la fuente

    def completo(self) -> bool:
        return bool(self.cuerpo.strip() and self.ancla.strip() and self.fecha.strip())

    def __str__(self) -> str:
        return f"{self.cuerpo} ({self.ancla}, {self.fecha})"


# Formas normativas en voz propia. Solo son admisibles con atribucion completa.
# Cada entrada es (patron, nombre de la forma).
FORMAS_NORMATIVAS = [
    (re.compile(r"\b(?:debe|deben|debera|deberan|deberia|deberian)\b", re.I), "deber"),
    (re.compile(r"\bhay\s+que\b", re.I), "hay que"),
    (re.compile(r"\b(?:se\s+recomienda|se\s+sugiere|se\s+indica|se\s+aconseja)\b", re.I),
     "recomendacion impersonal"),
    (re.compile(r"\b(?:inicie|inicia|iniciar|comience|administre|administra|ajuste|"
                r"ajusta|suspenda|suspende|indique|indica|prescriba|prescribe|titule|"
                r"titula|aumente|disminuya|agregue|anada|sustituya|refiera|derive)\b",
                re.I), "imperativo clinico"),
    (re.compile(r"\bla\s+dosis\s+es\b", re.I), "dosis en voz propia"),
    # Admite hasta dos palabras intermedias, para cubrir "la meta DE PRESION es"
    # y "el objetivo DE LDL es" sin tener que enumerar cada parametro clinico.
    (re.compile(r"\b(?:el|la)\s+(?:meta|objetivo|target|blanco|umbral|corte)"
                r"(?:\s+\w+){0,2}\s+es\b", re.I), "meta en voz propia"),
    (re.compile(r"\b(?:primera|segunda|tercera)\s+linea\b", re.I), "ordinal de eleccion"),
    (re.compile(r"\b(?:de|el|la)\s+eleccion\b", re.I), "farmaco de eleccion"),
    (re.compile(r"\btratamiento\s+de\s+eleccion\b", re.I), "tratamiento de eleccion"),
    (re.compile(r"\bes\s+(?:el|la)\s+(?:mejor|idoneo|idonea|preferido|preferida)\b", re.I),
     "juicio de preferencia"),
]

# Marcadores de que el enunciado se refiere a UNA persona concreta.
_PERSONA_CONCRETA = [
    (re.compile(r"\b(?:mi|tu|su|nuestro|este|esta|el)\s+paciente\b", re.I),
     "referencia a un paciente concreto"),
    (re.compile(r"\btengo\s+(?:un|una)\s+(?:paciente|caso)\b", re.I), "caso propio"),
    (re.compile(r"\b(?:que|cuanto|cual)\s+le\s+(?:doy|damos|indico|pongo|receto)\b", re.I),
     "pregunta de conducta individual"),
    (re.compile(r"\bpaciente\s+de\s+\d{1,3}\s*(?:anos|a)\b", re.I),
     "persona identificada por edad"),
    (re.compile(r"\ben\s+(?:mi|este)\s+caso\b", re.I), "caso individual"),
]

# Vistas que colapsan la derivacion. Cada una destruye el criterio de revision
# independiente de la guia de la FDA.
_VISTAS_PROHIBIDAS = {
    "resumen_ejecutivo", "que_hacer", "respuesta_rapida", "conclusion",
    "recomendacion_final", "tldr", "solo_la_respuesta", "conducta",
}


@dataclass
class HallazgoVoz:
    codigo: str
    detalle: str
    gravedad: str = "alta"
    fragmento: str = ""

    def dict(self) -> dict:
        return {"codigo": self.codigo, "detalle": self.detalle,
                "gravedad": self.gravedad, "fragmento": self.fragmento}


# ---------------------------------------------------------------------------
# 1. Modo deontico
# ---------------------------------------------------------------------------


def formas_normativas(texto: str) -> list[tuple[str, str]]:
    """Devuelve las formas normativas halladas, como (nombre, fragmento)."""
    out = []
    for pat, nombre in FORMAS_NORMATIVAS:
        m = pat.search(texto or "")
        if m:
            out.append((nombre, m.group(0)))
    return out


def revisar_voz(texto: str, emisor: Optional[Emisor] = None) -> list[HallazgoVoz]:
    """Verifica que un enunciado normativo venga atribuido y anclado.

    La regla no prohibe el contenido normativo: prohibe que ORIONS lo diga en
    voz propia. "La NOM-030 fija una meta de X" es educacion; "la meta es X" es
    ORIONS emitiendo una norma. Es la misma cifra y lados distintos de la
    frontera.
    """
    halladas = formas_normativas(texto)
    if not halladas:
        return []
    if emisor is not None and emisor.completo():
        # con atribucion completa la forma normativa es cita, no emision
        return []
    faltan = []
    if emisor is None:
        faltan = ["cuerpo emisor", "ancla", "fecha"]
    else:
        if not emisor.cuerpo.strip():
            faltan.append("cuerpo emisor")
        if not emisor.ancla.strip():
            faltan.append("ancla")
        if not emisor.fecha.strip():
            faltan.append("fecha")
    return [
        HallazgoVoz(
            codigo="NORMATIVO_SIN_ATRIBUIR",
            detalle=(f"forma normativa '{nombre}' en voz propia, sin {', '.join(faltan)}. "
                     f"ORIONS no emite normas: transcribe las de otros, atribuidas y "
                     f"ancladas. Reformular como 'segun <cuerpo> (<ancla>, <fecha>), ...'"),
            gravedad="alta", fragmento=frag,
        )
        for nombre, frag in halladas
    ]


# ---------------------------------------------------------------------------
# 2. Referente
# ---------------------------------------------------------------------------


def revisar_referente(texto: str, referente: Optional[Referente] = None) -> list[HallazgoVoz]:
    """Detecta enunciados referidos a una persona concreta.

    Es la frontera mas nitida de todas: un enunciado sobre una poblacion es
    educacion medica y uno sobre una persona identificada es practica clinica,
    sin importar quien lo escriba ni con que descargo de responsabilidad.
    """
    out = []
    for pat, nombre in _PERSONA_CONCRETA:
        m = pat.search(texto or "")
        if m:
            out.append(HallazgoVoz(
                codigo="REFERENTE_INDIVIDUAL",
                detalle=(f"{nombre}: el enunciado se refiere a una persona concreta y no "
                         f"a una poblacion. Un enunciado sobre una poblacion es educacion; "
                         f"uno sobre una persona es practica clinica, y ningun descargo de "
                         f"responsabilidad cambia esa clasificacion"),
                gravedad="alta", fragmento=m.group(0),
            ))
    if referente is not None and referente not in Referente:
        out.append(HallazgoVoz(
            codigo="REFERENTE_INVALIDO",
            detalle=f"referente '{referente}' fuera del enum cerrado",
            gravedad="alta",
        ))
    return out


def entrada_admisible(texto: str) -> tuple[bool, str]:
    """Compuerta de entrada: rechaza lo que trae datos de un paciente real.

    No es un filtro de contenido sino de SUPERFICIE: si ORIONS acepta la
    pregunta "mi paciente de 54 anos con eGFR 28, que dosis le doy", ya esta
    dando apoyo a la decision clinica, por mucho que la respuesta sea prudente.
    La respuesta correcta es no aceptar la pregunta y reformularla a poblacion.
    """
    hall = revisar_referente(texto)
    if hall:
        return (False, hall[0].detalle)
    # edad + sexo + cifra concreta en la misma frase es un caso, no una pregunta
    t = (texto or "").lower()
    tiene_edad = re.search(r"\b\d{1,3}\s*(?:anos|a)\b", t)
    tiene_sexo = re.search(r"\b(?:masculino|femenino|hombre|mujer|varon)\b", t)
    tiene_cifra = re.search(r"\b\d+(?:[.,]\d+)?\s*(?:mg/dl|mmol/l|ml/min|mmhg|%)", t)
    if tiene_edad and tiene_sexo and tiene_cifra:
        return (False, "edad, sexo y una cifra de laboratorio en la misma consulta: "
                       "es la descripcion de una persona concreta, no una pregunta de "
                       "poblacion. Reformular sin el caso")
    return (True, "")


# ---------------------------------------------------------------------------
# 3. Derivacion no colapsable
# ---------------------------------------------------------------------------


def revisar_vista(nombre_vista: str, muestra_derivacion: bool,
                  anclas_visibles: int) -> list[HallazgoVoz]:
    """La conclusion no puede mostrarse sin su cadena de derivacion y sus anclas.

    El criterio de la seccion 520(o)(1)(E) de la Food Drug and Cosmetic Act es
    que el profesional pueda revisar independientemente las bases de la
    recomendacion. Una vista que colapsa la derivacion destruye ese criterio, y
    es justo la vista mas pedida y mas vendible.
    """
    out = []
    clave = (nombre_vista or "").strip().lower().replace(" ", "_").replace("-", "_")
    if clave in _VISTAS_PROHIBIDAS:
        out.append(HallazgoVoz(
            codigo="VISTA_COLAPSADA",
            detalle=(f"la vista '{nombre_vista}' entrega la conclusion sin la derivacion. "
                     f"El criterio de revision independiente de la guia de Clinical "
                     f"Decision Support Software de la FDA exige que las bases esten a la "
                     f"vista; una vista de conclusion las oculta por diseno"),
            gravedad="alta",
        ))
    if not muestra_derivacion:
        out.append(HallazgoVoz(
            codigo="DERIVACION_OCULTA",
            detalle="la vista no muestra la cadena de derivacion",
            gravedad="alta",
        ))
    if anclas_visibles < 1:
        out.append(HallazgoVoz(
            codigo="ANCLAS_OCULTAS",
            detalle=("la vista no expone ninguna ancla re-consultable: sin ella el "
                     "profesional no puede verificar la base de forma independiente"),
            gravedad="alta",
        ))
    return out


def revisar_pluralidad(opciones: Sequence[dict]) -> list[HallazgoVoz]:
    """Una pregunta clinica nunca se responde con una sola opcion.

    Dos razones que apuntan al mismo diseno. Regulatoria: una salida unica es
    una recomendacion, y un abanico con su evidencia es material de estudio.
    Pedagogica: lo que ensena razonamiento clinico es comparar opciones y ver
    donde las fuentes discrepan, no memorizar la respuesta.
    """
    out = []
    if len(opciones) < 2:
        out.append(HallazgoVoz(
            codigo="SALIDA_UNICA",
            detalle=(f"solo {len(opciones)} opcion(es): una salida unica es una "
                     f"recomendacion. Se exigen dos o mas con su evidencia, y la "
                     f"discordancia entre fuentes cuando exista"),
            gravedad="alta",
        ))
    sin_ancla = [o for o in opciones if not o.get("ancla")]
    if sin_ancla:
        out.append(HallazgoVoz(
            codigo="OPCION_SIN_ANCLA",
            detalle=f"{len(sin_ancla)} opcion(es) sin ancla re-consultable",
            gravedad="media",
        ))
    return out


# ---------------------------------------------------------------------------
# Revision completa
# ---------------------------------------------------------------------------


@dataclass
class ReporteVoz:
    hallazgos: list[HallazgoVoz] = field(default_factory=list)

    @property
    def del_lado_educativo(self) -> bool:
        return not any(h.gravedad == "alta" for h in self.hallazgos)

    def dict(self) -> dict:
        return {"del_lado_educativo": self.del_lado_educativo,
                "hallazgos": [h.dict() for h in self.hallazgos]}


def revisar(texto: str, emisor: Optional[Emisor] = None,
            referente: Optional[Referente] = None,
            nombre_vista: str = "", muestra_derivacion: bool = True,
            anclas_visibles: int = 1,
            opciones: Optional[Sequence[dict]] = None) -> ReporteVoz:
    """Pasa un enunciado y su presentacion por los tres controles de frontera."""
    r = ReporteVoz()
    r.hallazgos.extend(revisar_voz(texto, emisor))
    r.hallazgos.extend(revisar_referente(texto, referente))
    if nombre_vista or not muestra_derivacion:
        r.hallazgos.extend(revisar_vista(nombre_vista, muestra_derivacion,
                                         anclas_visibles))
    if opciones is not None:
        r.hallazgos.extend(revisar_pluralidad(opciones))
    return r


def atribuir(texto: str, emisor: Emisor) -> str:
    """Reescribe un enunciado normativo como transcripcion atribuida.

    No es cosmetica: es el cambio que mueve el enunciado del lado regulado al
    lado educativo, y deja la fuente a la vista para que se pueda verificar.
    """
    limpio = (texto or "").strip().rstrip(".")
    if limpio[:1].isupper():
        limpio = limpio[0].lower() + limpio[1:]
    return f"Segun {emisor}: {limpio}."


__all__ = [
    "Referente", "Emisor", "HallazgoVoz", "ReporteVoz", "FORMAS_NORMATIVAS",
    "formas_normativas", "revisar_voz", "revisar_referente", "entrada_admisible",
    "revisar_vista", "revisar_pluralidad", "revisar", "atribuir",
]
