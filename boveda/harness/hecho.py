"""La unidad atomica de la Boveda: el Hecho anclado.

Un Hecho NO es un parrafo, ni una ficha, ni una recomendacion copiada. Es una
proposicion clinica minima con su magnitud normalizada, su poblacion, su ancla
en una fuente publica re-consultable, y su cadena causal.

Por que esta es la unidad correcta:

1. Legal. Una guia protege su EXPRESION: su redaccion, su seleccion y su orden.
   Un hecho atomico con su propio enunciado, su propia ancla en evidencia
   primaria publica y su propio orden derivado del grafo no reproduce ninguna
   de esas tres cosas. La proteccion no alcanza a los datos ni a las ideas.

2. Frescura. Cuando sale un ensayo nuevo, no se reescribe un capitulo: se
   invalida el ancla de los hechos afectados y se recalcula la derivacion.

3. Pedagogia. Un hecho atomico es lo que se puede preguntar, programar en
   repeticion espaciada y rastrear en el modelo del estudiante. Un parrafo no.

4. Trazabilidad. Cada cifra que ORIONS muestra apunta a un NCT, un PMCID, un
   SPL de etiqueta o una NOM. Lo que no tiene ancla no se muestra como hecho.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from .numeros import Magnitud, Clase


class ClaseHecho(str, Enum):
    UMBRAL = "umbral"                    # corte diagnostico o de decision
    DOSIS = "dosis"                      # cantidad y frecuencia
    EFECTO = "efecto"                    # tamano de efecto de una intervencion
    CRITERIO = "criterio"                # criterio diagnostico o de clasificacion
    SECUENCIA = "secuencia"              # orden de pasos o de lineas de tratamiento
    CONTRAINDICACION = "contraindicacion"
    TIEMPO_VENTANA = "ventana"           # ventana terapeutica
    EPIDEMIOLOGIA = "epidemiologia"      # prevalencia, incidencia


class TipoAncla(str, Enum):
    """Jerarquia de anclas, de la mas fuerte a la mas debil.

    El orden importa: determina el veredicto maximo que un hecho puede alcanzar.
    """

    REGISTRO_ENSAYO = "registro_ensayo"      # ClinicalTrials.gov, con NCT y resultados
    ETIQUETA_REGULADOR = "etiqueta"          # FDA SPL / DailyMed, COFEPRIS
    NORMA_OFICIAL = "norma"                  # NOM, texto normativo mexicano
    GUIA_GOBIERNO = "guia_gobierno"          # VA/DoD, USPSTF, CDC, NIH, AHRQ
    ARTICULO_CC_BY = "articulo_cc_by"        # PMC con licencia de uso comercial
    ARTICULO_ABSTRACT = "articulo_abstract"  # resumen de PubMed
    DERIVADA = "derivada"                    # calculada desde otros hechos anclados
    SIN_ANCLA = "sin_ancla"                  # solo memoria del modelo


# Veredicto maximo alcanzable segun el tipo de ancla mas fuerte disponible.
TECHO_POR_ANCLA = {
    TipoAncla.REGISTRO_ENSAYO: "VERDE",
    TipoAncla.ETIQUETA_REGULADOR: "VERDE",
    TipoAncla.NORMA_OFICIAL: "VERDE",
    TipoAncla.GUIA_GOBIERNO: "VERDE",
    TipoAncla.ARTICULO_CC_BY: "VERDE",
    TipoAncla.ARTICULO_ABSTRACT: "AMBAR",
    TipoAncla.DERIVADA: "AMBAR",
    TipoAncla.SIN_ANCLA: "AMBAR",
}


@dataclass
class Ancla:
    """Un punto re-consultable donde vive la cifra, en una fuente usable.

    `localizador` debe permitir que otra persona recupere exactamente el mismo
    dato: NCT05654623, PMC9876543, SPL set id, NOM-015-SSA2-2010 numeral 7.4.
    `cita_corta` puede guardar hasta unas 20 palabras textuales al amparo del
    derecho de cita del articulo 148 de la Ley Federal del Derecho de Autor,
    siempre citando la fuente. Nunca mas que eso, y nunca tablas ni figuras.
    """

    tipo: TipoAncla
    localizador: str
    url: str = ""
    magnitud: Optional[Magnitud] = None
    cita_corta: str = ""
    fecha_consulta: str = ""          # ISO 8601, lo escribe el harness
    licencia: str = ""                # dominio publico, CC BY 4.0, norma, etc
    verificada: bool = False          # el harness confirmo que la cifra esta ahi

    def dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        d["magnitud"] = self.magnitud.dict() if self.magnitud else None
        return d


@dataclass
class Poblacion:
    """El PICO sin el que una cifra no significa nada.

    Una meta de presion de 130 es un hecho distinto en un diabetico de 50 anos
    y en un paciente de 85 con fragilidad. La Boveda no guarda cifras sueltas:
    guarda cifras con su poblacion.
    """

    condicion: str
    edad_min: Optional[int] = None
    edad_max: Optional[int] = None
    inclusion: list[str] = field(default_factory=list)
    exclusion: list[str] = field(default_factory=list)
    nivel_atencion: str = ""           # primer nivel, segundo, tercero, UCI
    pais_contexto: str = ""            # MX, US, internacional

    def clave(self) -> str:
        return "|".join([
            self.condicion.lower().strip(),
            str(self.edad_min or ""), str(self.edad_max or ""),
            ",".join(sorted(s.lower().strip() for s in self.inclusion)),
            self.nivel_atencion.lower().strip(),
        ])


@dataclass
class Hecho:
    """Una proposicion clinica minima, anclada y versionada."""

    enunciado: str                      # redaccion propia, nunca copiada
    clase: ClaseHecho
    poblacion: Poblacion
    magnitud: Optional[Magnitud] = None

    intervencion: str = ""
    comparador_clinico: str = ""        # frente a que se compara
    desenlace: str = ""

    anclas: list[Ancla] = field(default_factory=list)
    mecanismo: list[str] = field(default_factory=list)   # ids de aristas del grafo

    delta_mexico: str = ""              # diferencia con NOM, CENETEC, Cuadro Basico
    trampa_enarm: str = ""

    veredicto: str = "GRIS"             # lo asigna atestiguar.py
    confianza: float = 0.0              # 0 a 1
    diagnostico: dict = field(default_factory=dict)

    version: int = 1
    vigente: bool = True
    revisar_si: list[str] = field(default_factory=list)  # disparadores de frescura
    firmado_por: str = ""               # medico validador, si lo hubo
    reemplaza: str = ""                 # id del hecho que deja obsoleto

    def id(self) -> str:
        """Identificador estable: depende del significado, no de la redaccion.

        Dos hechos con la misma poblacion, intervencion, desenlace y clase son
        EL MISMO hecho aunque esten redactados distinto. Eso permite detectar
        contradicciones y versionar sin duplicar.
        """
        semilla = "::".join([
            self.clase.value,
            self.poblacion.clave(),
            self.intervencion.lower().strip(),
            self.comparador_clinico.lower().strip(),
            self.desenlace.lower().strip(),
            (self.magnitud.unidad or "") if self.magnitud else "",
            (self.magnitud.clase.value if self.magnitud else ""),
        ])
        return "H" + hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:16]

    def ancla_mas_fuerte(self) -> Optional[Ancla]:
        orden = list(TipoAncla)
        verificadas = [a for a in self.anclas if a.verificada]
        if not verificadas:
            return None
        return min(verificadas, key=lambda a: orden.index(a.tipo))

    def techo(self) -> str:
        a = self.ancla_mas_fuerte()
        return TECHO_POR_ANCLA[a.tipo] if a else TECHO_POR_ANCLA[TipoAncla.SIN_ANCLA]

    def mostrable(self) -> bool:
        """Solo VERDE y AMBAR se muestran. AMBAR va etiquetado como no anclado.

        ROJO y NEGRO nunca llegan al estudiante. Un hecho ausente le cuesta
        una pregunta; un hecho equivocado le cuesta una conducta clinica.
        """
        return self.veredicto in ("VERDE", "AMBAR")

    def dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id()
        d["clase"] = self.clase.value
        d["magnitud"] = self.magnitud.dict() if self.magnitud else None
        d["anclas"] = [a.dict() for a in self.anclas]
        d["techo"] = self.techo()
        d["mostrable"] = self.mostrable()
        return d

    def json(self) -> str:
        return json.dumps(self.dict(), ensure_ascii=False, indent=2)


__all__ = ["Hecho", "Ancla", "Poblacion", "ClaseHecho", "TipoAncla", "TECHO_POR_ANCLA"]
