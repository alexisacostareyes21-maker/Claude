"""Independencia: los controles que impiden que la Boveda sea un espejo de una guia.

La defensa de ORIONS ("no ingerimos la guia, reconstruimos la evidencia") tiene
un punto ciego: una guia protege tres cosas, y la reconstruccion solo neutraliza
la primera.

    REDACCION   ─► neutralizada: cada hecho tiene enunciado propio
    SELECCION   ─► NO neutralizada: que temas se incluyen y cuales se omiten
    DISPOSICION ─► NO neutralizada: en que orden y con que prioridad

El articulo 107 de la Ley Federal del Derecho de Autor protege como compilacion
una base de datos que "por razones de seleccion y disposicion de su contenido
constituya una creacion intelectual", y el 78 nombra expresamente la parafrasis,
el compendio y la compilacion como obras derivadas. Reconstruir cada cifra desde
un ensayo publico y luego ordenarlas igual que la guia reproduce exactamente lo
que la guia aporto.

LA PRUEBA IRREFUTABLE DE COPIA, Y EL CONTROL QUE LA EVITA

El escenario concreto que hunde al producto es un solo numero:

    ORIONS dice "iniciar un iSGLT2 si el eGFR es mayor o igual a 20".
    CREDENCE inscribio pacientes con eGFR de 30 a 90.
    DAPA-CKD inscribio pacientes con eGFR de 25 a 75.
    El 20 NO EXISTE en la ventana de inscripcion de ningun ensayo.

Ese 20 solo pudo salir de la guia. Es una prueba irrefutable, y lo peor es que
pasaria todos los controles de atestiguacion: varios encuadres coincidirian en
el 20, porque el 20 es lo que el modelo aprendio de la guia.

De ahi la distincion que organiza este modulo:

    UN HECHO            "el ensayo inscribio pacientes con eGFR de 25 a 75"
                        -> esta en el registro, se puede anclar byte a byte

    UN JUICIO DE LA GUIA "iniciar si el eGFR es mayor o igual a 20"
                        -> no esta en ningun registro; es la sintesis que el
                           comite aporto, y es su expresion, no un dato

ORIONS puede publicar el primero. El segundo no es suyo, y ademas es el que lo
delata. Asi que la Boveda expone VENTANAS DE ELEGIBILIDAD con su NCT y declara
explicitamente que no emite el umbral. Para un estudiante es mas util: aprende
de donde sale el numero y por que las guias no coinciden entre si.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence

from .hecho import Hecho, ClaseHecho, Ancla
from .numeros import Clase, Magnitud

# ---------------------------------------------------------------------------
# 1. Umbrales sinteticos
# ---------------------------------------------------------------------------

# Clases de hecho donde una cifra que no esta en la fuente es un juicio de
# sintesis y no un dato, y por tanto no puede publicarse como hecho.
CLASES_DE_SINTESIS = {ClaseHecho.UMBRAL, ClaseHecho.TIEMPO_VENTANA}


def _valores_de_ancla(a: Ancla) -> list[float]:
    out: list[float] = []
    if a.magnitud is None:
        return out
    for v in (a.magnitud.valor, a.magnitud.ic_inf, a.magnitud.ic_sup,
              a.magnitud.valor_sup, a.magnitud.por_dia):
        if v is not None:
            out.append(float(v))
    return out


def coincide_byte_a_byte(valor: float, anclas: Iterable[Ancla],
                         tol: float = 1e-9) -> bool:
    """True si el valor aparece literalmente en alguna ancla verificada.

    Deliberadamente estricto, sin tolerancia relativa: la tolerancia es lo que
    permite que un 25 del registro se convierta en un 20 "equivalente". Aqui la
    pregunta no es si dos cantidades son clinicamente equivalentes, sino si esta
    cifra exacta vino de la fuente o la puso alguien.
    """
    for a in anclas:
        if not a.verificada:
            continue
        for v in _valores_de_ancla(a):
            if abs(v - valor) <= tol:
                return True
    return False


@dataclass
class HallazgoIndependencia:
    codigo: str
    detalle: str
    gravedad: str = "alta"      # baja, media, alta
    hecho_id: str = ""

    def dict(self) -> dict:
        return {"codigo": self.codigo, "detalle": self.detalle,
                "gravedad": self.gravedad, "hecho_id": self.hecho_id}


def umbral_sintetico(h: Hecho) -> Optional[HallazgoIndependencia]:
    """Detecta un umbral cuya cifra no esta en ninguna de sus anclas.

    Es el control mas importante del modulo y el unico que atrapa la prueba
    irrefutable de copia. Un umbral que ningun registro contiene no es un hecho
    reconstruido: es el juicio de sintesis de un comite.
    """
    if h.clase not in CLASES_DE_SINTESIS or h.magnitud is None:
        return None
    if coincide_byte_a_byte(h.magnitud.valor, h.anclas):
        return None
    disponibles = sorted({v for a in h.anclas for v in _valores_de_ancla(a)})
    return HallazgoIndependencia(
        codigo="UMBRAL_SINTETICO",
        detalle=(
            f"el umbral {h.magnitud.valor:g} no aparece en ninguna ancla verificada "
            f"(las anclas contienen {disponibles or 'nada'}). Un umbral que ningun "
            f"registro contiene es el juicio de sintesis de un comite, no un dato "
            f"reconstruido, y publicarlo es la prueba mas directa de que salio de la "
            f"guia. Reformular como ventana de elegibilidad del ensayo."
        ),
        gravedad="alta", hecho_id=h.id(),
    )


def reformular_como_ventana(h: Hecho) -> Hecho:
    """Convierte un umbral en la ventana de elegibilidad que si esta en la fuente.

    Es la reparacion, no solo la deteccion. El hecho resultante dice lo que el
    registro dice y nada mas, y deja explicito que ORIONS no emite el umbral.
    Pedagogicamente es mejor: el estudiante aprende de donde sale el numero y por
    que las guias discrepan entre si.
    """
    anclas_ver = [a for a in h.anclas if a.verificada and a.magnitud is not None]
    if not anclas_ver:
        h.veredicto = "ROJO"
        h.diagnostico["independencia"] = (
            "no se puede reformular como ventana: no hay ancla verificada con una "
            "magnitud de la que tomar la ventana"
        )
        return h
    m = anclas_ver[0].magnitud
    inf = m.ic_inf if m.ic_inf is not None else m.valor
    sup = m.ic_sup if m.ic_sup is not None else (m.valor_sup if m.valor_sup is not None
                                                 else m.valor)
    h.clase = ClaseHecho.CRITERIO
    h.magnitud = Magnitud(clase=m.clase, valor=inf, unidad=m.unidad,
                          valor_sup=sup, bruto=m.bruto)
    h.magnitud.comparador = m.comparador
    h.enunciado = (
        f"El ensayo registrado en {anclas_ver[0].localizador} inscribio pacientes con "
        f"{m.unidad or 'el parametro'} entre {inf:g} y {sup:g}. ORIONS no emite un "
        f"umbral de inicio: expone la ventana en que se estudio la intervencion."
    )
    h.diagnostico["independencia"] = "reformulado como ventana de elegibilidad"
    return h


# ---------------------------------------------------------------------------
# 2. Gradaciones ajenas
# ---------------------------------------------------------------------------

# Las letras y niveles de gradacion SON la expresion de la guia: codifican el
# juicio del comite sobre la fuerza de la evidencia, que es precisamente su
# aporte. Reproducirlos es copiar lo unico que la guia aporto sobre un dato
# publico.
_GRADACIONES = [
    (re.compile(r"\b(?:nivel\s+de\s+)?evidencia\s+[ABCE]\b", re.I), "gradacion por letra"),
    (re.compile(r"\bclase\s+(?:I{1,3}|IV|1|2[ab]?|3)\s*[,\-]?\s*nivel\s+[ABC]\b", re.I),
     "clase y nivel de recomendacion"),
    (re.compile(r"\b[12][ABCD]\b"), "nivel GRADE"),
    (re.compile(r"\bGRADE\s+(?:certeza|calidad|evidencia|nivel)?\s*"
                r"(?:alta|moderada|baja|muy\s+baja)\b", re.I), "certeza GRADE"),
    (re.compile(r"\brecomendacion\s+(?:fuerte|debil|condicional)\b", re.I),
     "fuerza de recomendacion"),
    (re.compile(r"\bgrado\s+[ABCDI]\b", re.I), "grado de recomendacion"),
]


def gradacion_ajena(texto: str) -> list[str]:
    """Encuentra marcas de gradacion de una guia en un texto."""
    out = []
    for pat, nombre in _GRADACIONES:
        m = pat.search(texto or "")
        if m:
            out.append(f"{nombre}: '{m.group(0)}'")
    return out


def revisar_gradacion(h: Hecho) -> Optional[HallazgoIndependencia]:
    campos = " | ".join([h.enunciado, h.trampa_enarm, h.delta_mexico])
    marcas = gradacion_ajena(campos)
    if not marcas:
        return None
    return HallazgoIndependencia(
        codigo="GRADACION_AJENA",
        detalle=(f"el hecho reproduce gradaciones de una guia ({'; '.join(marcas)}). "
                 f"Las letras y niveles codifican el juicio del comite sobre la fuerza "
                 f"de la evidencia, que es su aporte y su expresion. ORIONS debe emitir "
                 f"sus propios campos mecanicos: n del ensayo, tipo de desenlace, "
                 f"amplitud del intervalo, numero de anclas independientes."),
        gravedad="alta", hecho_id=h.id(),
    )


# ---------------------------------------------------------------------------
# 3. Independencia de la seleccion
# ---------------------------------------------------------------------------


class OrigenSeleccion(str, Enum):
    """Por que un tema entro a la Boveda. No admite "porque la guia lo incluye"."""

    EPIDEMIOLOGIA_MX = "epidemiologia_mx"       # carga de enfermedad en Mexico
    PERFIL_ENARM = "perfil_enarm"               # peso del dominio en el examen
    CUADRO_BASICO = "cuadro_basico"             # disponibilidad real del insumo
    DENSIDAD_ANCLA = "densidad_ancla"           # cuanta evidencia primaria publica hay
    PRIMER_NIVEL = "primer_nivel"               # relevancia en el primer nivel de atencion
    HUECO_DOCENTE = "hueco_docente"             # lo que la oferta actual no cubre bien


@dataclass
class Justificacion:
    """Por que este tema esta en la Boveda, con su rastro.

    Campo obligatorio. Existe para poder demostrar que la seleccion es propia y
    derivada de criterios verificables, en vez de tener que argumentar que no se
    copio.
    """

    origen: OrigenSeleccion
    evidencia: str                     # el dato que lo justifica
    peso: float = 0.0                  # 0 a 1, contribucion a la prioridad

    def dict(self) -> dict:
        return {"origen": self.origen.value, "evidencia": self.evidencia,
                "peso": self.peso}


def revisar_justificacion(h: Hecho) -> Optional[HallazgoIndependencia]:
    """Un hecho sin justificacion de inclusion propia es un hecho heredado."""
    just = h.diagnostico.get("justificacion")
    if not just:
        return HallazgoIndependencia(
            codigo="SELECCION_SIN_JUSTIFICAR",
            detalle=("el hecho no declara por que esta en la Boveda. Sin una "
                     "justificacion propia y verificable, la seleccion queda "
                     "indistinguible de la de la guia, y la seleccion si es expresion "
                     "protegida (articulo 107 de la Ley Federal del Derecho de Autor)."),
            gravedad="media", hecho_id=h.id(),
        )
    texto = str(just).lower()
    for frase in ("porque la guia", "la guia lo incluye", "segun la ada",
                  "segun kdigo", "segun la aha", "la esc lo recomienda"):
        if frase in texto:
            return HallazgoIndependencia(
                codigo="SELECCION_HEREDADA",
                detalle=(f"la justificacion de inclusion apela a una guia externa "
                         f"('{frase}'). Ese es exactamente el aporte que la guia protege. "
                         f"La inclusion tiene que salir de la funcion de prioridad propia."),
                gravedad="alta", hecho_id=h.id(),
            )
    return None


# ---------------------------------------------------------------------------
# 4. Disposicion: orden demostrablemente derivado
# ---------------------------------------------------------------------------


def clave_de_orden(h: Hecho) -> tuple:
    """La clave de ordenamiento canonica de la Boveda.

    Primero la magnitud del efecto absoluto, luego la precision (amplitud del
    intervalo), luego la fecha del ancla. Las tres salen de los datos, ninguna
    de un juicio editorial.

    Que el orden sea una funcion PURA y RECOMPUTABLE es lo que permite
    demostrarlo en vez de alegarlo: cualquiera recomputa y verifica.
    """
    m = h.magnitud
    if m is None:
        return (3, 0.0, 0.0, h.id())

    # magnitud del efecto: cuanto se aleja de la nulidad
    if m.clase is Clase.RAZON_RIESGO:
        efecto = abs(1.0 - m.valor)
    elif m.clase in (Clase.REDUCCION_REL, Clase.REDUCCION_ABS):
        efecto = abs(m.valor)
    elif m.clase is Clase.NNT:
        efecto = 1.0 / m.valor if m.valor > 0 else 0.0
    else:
        return (2, 0.0, 0.0, h.id())

    if m.ic_inf is not None and m.ic_sup is not None and m.valor != 0:
        amplitud = abs(m.ic_sup - m.ic_inf) / abs(m.valor)
    else:
        amplitud = 9.99      # sin intervalo va despues, no antes

    fecha = ""
    a = h.ancla_mas_fuerte()
    if a is not None:
        fecha = a.fecha_consulta or ""

    return (0, -efecto, amplitud, fecha, h.id())


def orden_canonico(hechos: Sequence[Hecho]) -> list[Hecho]:
    """Ordena por la clave canonica. Esta funcion ES la disposicion de ORIONS."""
    return sorted(hechos, key=clave_de_orden)


def orden_es_derivado(publicados: Sequence[Hecho]) -> Optional[HallazgoIndependencia]:
    """Verifica que el orden publicado sea el que la funcion canonica produce.

    El valor de esto es probatorio: si el orden coincide con el recomputado, la
    disposicion es demostrablemente derivada de los datos y no de la guia. Si no
    coincide, alguien la reordeno a mano, y entonces hay que explicar con que
    criterio, que es justo la pregunta que no conviene tener que contestar.
    """
    esperado = [h.id() for h in orden_canonico(publicados)]
    real = [h.id() for h in publicados]
    if esperado == real:
        return None
    primera = next((i for i, (a, b) in enumerate(zip(real, esperado)) if a != b), 0)
    return HallazgoIndependencia(
        codigo="ORDEN_NO_DERIVADO",
        detalle=(f"el orden publicado no coincide con el que produce la funcion "
                 f"canonica; la primera divergencia esta en la posicion {primera}. "
                 f"Un orden recomputable se demuestra; uno ajustado a mano hay que "
                 f"justificarlo."),
        gravedad="media",
    )


# ---------------------------------------------------------------------------
# Revision completa
# ---------------------------------------------------------------------------


@dataclass
class ReporteIndependencia:
    hallazgos: list[HallazgoIndependencia] = field(default_factory=list)
    publicables: list[Hecho] = field(default_factory=list)
    bloqueados: list[Hecho] = field(default_factory=list)

    @property
    def limpio(self) -> bool:
        return not any(h.gravedad == "alta" for h in self.hallazgos)

    def dict(self) -> dict:
        return {
            "limpio": self.limpio,
            "hallazgos": [h.dict() for h in self.hallazgos],
            "publicables": len(self.publicables),
            "bloqueados": len(self.bloqueados),
        }


def revisar(hechos: Sequence[Hecho], reparar: bool = False) -> ReporteIndependencia:
    """Pasa el conjunto por los cuatro controles de independencia.

    Un hallazgo de gravedad alta BLOQUEA el hecho. No es una advertencia que se
    anota y se publica igual: es la diferencia entre una boveda defendible y una
    que ya perdio el pleito antes de empezarlo.
    """
    rep = ReporteIndependencia()
    for h in hechos:
        propios: list[HallazgoIndependencia] = []
        u = umbral_sintetico(h)
        if u:
            if reparar:
                reformular_como_ventana(h)
                u2 = umbral_sintetico(h)
                if u2:
                    propios.append(u2)
            else:
                propios.append(u)
        for chequeo in (revisar_gradacion, revisar_justificacion):
            r = chequeo(h)
            if r:
                propios.append(r)
        rep.hallazgos.extend(propios)
        if any(x.gravedad == "alta" for x in propios):
            h.veredicto = "ROJO"
            h.diagnostico["independencia_bloqueo"] = [x.codigo for x in propios]
            rep.bloqueados.append(h)
        else:
            rep.publicables.append(h)

    o = orden_es_derivado(rep.publicables)
    if o:
        rep.hallazgos.append(o)
    return rep


__all__ = [
    "umbral_sintetico", "reformular_como_ventana", "coincide_byte_a_byte",
    "gradacion_ajena", "revisar_gradacion", "OrigenSeleccion", "Justificacion",
    "revisar_justificacion", "clave_de_orden", "orden_canonico", "orden_es_derivado",
    "revisar", "ReporteIndependencia", "HallazgoIndependencia", "CLASES_DE_SINTESIS",
]
