"""Motor de atestiguacion: decide si una cifra es confiable o va a cuarentena.

El problema real no es extraer cifras: es saber cuales estan confabuladas.

Lo que NO funciona, y por que:

  - Preguntarle al modelo varias veces lo mismo. Mide ruido de muestreo, no
    verdad. Si el modelo "recuerda" mal un numero, lo recuerda mal las diez
    veces y la autoconsistencia certifica el error.
  - Pedirle que diga su nivel de confianza. Esta mal calibrado y sube la
    confianza justo cuando el error es sistematico.
  - Verificar con similitud de texto. "10 mg" y "100 mg" son casi identicos
    textualmente y difieren en un orden de magnitud.

Lo que si funciona, y es lo que implementa este modulo:

  1. DIVERSIDAD DE ENCUADRE. La misma cifra se pide por caminos que activan
     rutas distintas: directa, desde el ensayo, desde el mecanismo, por su
     complemento, y sin opciones a la vista. Cuando varios caminos
     independientes convergen, la convergencia informa. Cuando es el mismo
     camino repetido, no.

  2. SONDA FALSA. Se le afirma al modelo un valor deliberadamente incorrecto y
     se observa si lo acepta. Si lo acepta, su recuerdo de ESE hecho no es
     utilizable, por consenso que haya mostrado. Es barato, es falsable y
     detecta lo que la autoconsistencia no ve: la complacencia.

  3. ANCLA OBLIGATORIA. Ningun hecho llega a VERDE sin una cifra localizada en
     una fuente publica re-consultable. El consenso sin ancla llega a AMBAR y
     se muestra etiquetado.

  4. COMPARACION SEMANTICA NUMERICA. Via harness.numeros, no via texto.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from .numeros import (
    Acuerdo, Clase, Magnitud, agrupar, comparar, factor_de_alarma,
    orden_de_magnitud_distinto,
)
from .hecho import Hecho, TipoAncla


class Encuadre(str, Enum):
    """Los caminos por los que se pide la misma cifra.

    No son variaciones de redaccion: son rutas de recuperacion distintas. Dos
    elicitaciones del mismo encuadre cuentan como una sola para el consenso.
    """

    DIRECTO = "directo"              # cual es el umbral / la dosis / el HR
    DESDE_ENSAYO = "desde_ensayo"    # en el ensayo X, cual fue el resultado primario
    DESDE_MECANISMO = "desde_mecanismo"  # dada la fisiologia, que magnitud se espera
    COMPLEMENTO = "complemento"      # pide la medida reciproca: RRR en vez de HR
    SIN_OPCIONES = "sin_opciones"    # respuesta abierta, sin candidatos a la vista
    DESDE_FUENTE = "desde_fuente"    # extraida de un documento recuperado, no de memoria


class Veredicto(str, Enum):
    VERDE = "VERDE"        # anclado y con consenso entre encuadres: se muestra como hecho
    AMBAR = "AMBAR"        # consenso sin ancla fuerte: se muestra etiquetado
    ROJO = "ROJO"          # dispersion: no se muestra, va a cola de revision humana
    NEGRO = "NEGRO"        # contradice el ancla, o el modelo acepto un valor falso
    GRIS = "GRIS"          # evidencia insuficiente para decidir


class Certeza(str, Enum):
    """Lo que el modelo dice sobre su propio acceso al dato.

    Es la unica forma de autoinforme que el motor usa, y solo para rebajar, nunca
    para acreditar: una elicitacion marcada como inferencia no puede sostener un
    VERDE por si sola, aunque coincida con las demas.
    """

    RECUERDO_EXACTO = "recuerdo_exacto"
    RECUERDO_APROXIMADO = "recuerdo_aproximado"
    INFERENCIA = "inferencia"
    NO_LO_SE = "no_lo_se"


@dataclass
class Procedencia:
    """De donde dice el modelo que viene la cifra.

    Sirve para un control que el consenso numerico no da: cuando varias
    elicitaciones coinciden en el NUMERO pero nombran estudios distintos, el
    acuerdo es sospechoso. Una cifra bien recordada arrastra su estudio; una
    confabulada arrastra una procedencia que cambia entre intentos.
    """

    estudio: str = ""
    ano: str = ""
    n: str = ""
    poblacion: str = ""
    desenlace: str = ""
    registro: str = ""

    def clave(self) -> str:
        return (self.registro or self.estudio or "").lower().strip()


@dataclass
class Elicitacion:
    """Una respuesta del modelo sobre la cifra, con el camino por el que se pidio."""

    magnitud: Optional[Magnitud]
    encuadre: Encuadre
    modelo: str = ""
    texto_bruto: str = ""
    confianza_declarada: Optional[float] = None  # se registra, no se usa para decidir
    certeza: Certeza = Certeza.RECUERDO_APROXIMADO
    procedencia: Optional[Procedencia] = None
    abstuvo: bool = False        # el modelo respondio no_se, que es dato valido
    signo_mecanismo: int = 0     # del encuadre DESDE_MECANISMO: -1, 0 o +1


@dataclass
class SondaFalsa:
    """Prueba de complacencia: se afirma un valor incorrecto y se mide la reaccion.

    `valor_falso` debe estar lo bastante lejos del valor real para que aceptarlo
    sea inequivocamente un error, y lo bastante cerca para ser plausible. La
    regla practica del harness es un factor entre 1.5 y 3, o un cambio de signo
    del efecto.
    """

    valor_falso: Magnitud
    acepto: bool                 # el modelo lo dio por bueno
    corrigio_a: Optional[Magnitud] = None   # si corrigio, con que valor
    texto_bruto: str = ""


@dataclass
class Reporte:
    veredicto: Veredicto
    confianza: float
    magnitud_consenso: Optional[Magnitud]
    n_elicitaciones: int
    n_encuadres: int
    cuota_consenso: float
    tasa_abstencion: float
    anclas_verificadas: int
    ancla_mas_fuerte: Optional[str]
    motivos: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    grupos: list[list[str]] = field(default_factory=list)

    def dict(self) -> dict:
        return {
            "veredicto": self.veredicto.value,
            "confianza": round(self.confianza, 3),
            "magnitud_consenso": self.magnitud_consenso.dict() if self.magnitud_consenso else None,
            "n_elicitaciones": self.n_elicitaciones,
            "n_encuadres": self.n_encuadres,
            "cuota_consenso": round(self.cuota_consenso, 3),
            "tasa_abstencion": round(self.tasa_abstencion, 3),
            "anclas_verificadas": self.anclas_verificadas,
            "ancla_mas_fuerte": self.ancla_mas_fuerte,
            "motivos": self.motivos,
            "alertas": self.alertas,
            "grupos": self.grupos,
        }


# Parametros del umbral. Son decisiones de producto, no constantes de la
# naturaleza: subirlos reduce cobertura y aumenta precision.
MIN_ELICITACIONES = 3
MIN_ENCUADRES = 3
CUOTA_CONSENSO_VERDE = 0.67
CUOTA_CONSENSO_AMBAR = 0.60
TOL_DEFECTO = 0.02
# Clases donde un error no es un dato mal puesto sino una conducta peligrosa.
CLASES_CRITICAS = {Clase.DOSIS, Clase.PRESION, Clase.TFG, Clase.CONCENTRACION}

# Tolerancia de acuerdo POR CLASE. Una razon de riesgo de 0.61 y una de 0.62 son
# la misma conclusion clinica; una dosis de 10 mg y una de 10.5 mg no
# necesariamente, y 10 frente a 20 desde luego que no. Usar una sola tolerancia
# para todo trataba una sobredosis como un redondeo.
TOL_POR_CLASE = {
    Clase.DOSIS: 0.001,
    Clase.CONCENTRACION: 0.005,
    Clase.PRESION: 0.005,
    Clase.TFG: 0.005,
}


def tolerancia(clase, defecto: float = TOL_DEFECTO) -> float:
    return TOL_POR_CLASE.get(clase, defecto)


def atestiguar(
    hecho: Hecho,
    elicitaciones: Sequence[Elicitacion],
    sondas: Sequence[SondaFalsa] = (),
    tol: float = TOL_DEFECTO,
) -> Reporte:
    """Evalua una cifra y devuelve su veredicto con el diagnostico completo.

    El orden de las reglas es deliberado: las que descalifican van antes que las
    que acreditan. Un hecho que contradice su ancla no se rescata por tener
    consenso, y un modelo que acepto un valor falso no se rescata por nada.
    """
    motivos: list[str] = []
    alertas: list[str] = []

    validas = [e for e in elicitaciones if e.magnitud is not None and not e.abstuvo]
    abstenciones = [e for e in elicitaciones if e.abstuvo]
    mags = [e.magnitud for e in validas]
    encuadres = {e.encuadre for e in validas}
    n_enc = len(encuadres)
    intentos = len(validas) + len(abstenciones)
    tasa_abstencion = len(abstenciones) / intentos if intentos else 0.0

    anclas_ver = [a for a in hecho.anclas if a.verificada and a.magnitud is not None]
    ancla_fuerte = hecho.ancla_mas_fuerte()
    nombre_ancla = ancla_fuerte.tipo.value if ancla_fuerte else None

    if mags:
        tol = min(tol, tolerancia(mags[0].clase))
    grupos = agrupar(mags, tol) if mags else []
    dominante = grupos[0] if grupos else []
    cuota = len(dominante) / len(mags) if mags else 0.0
    consenso = _representante(dominante) if dominante else None

    def rep(v: Veredicto, conf: float) -> Reporte:
        return Reporte(
            veredicto=v, confianza=conf, magnitud_consenso=consenso,
            n_elicitaciones=len(validas), n_encuadres=n_enc, cuota_consenso=cuota,
            tasa_abstencion=tasa_abstencion,
            anclas_verificadas=len(anclas_ver), ancla_mas_fuerte=nombre_ancla,
            motivos=motivos, alertas=alertas,
            grupos=[[str(m) for m in g] for g in grupos],
        )

    # ---- Regla 0: complacencia. Descalifica antes que cualquier otra cosa.
    aceptadas = [s for s in sondas if s.acepto]
    if aceptadas:
        motivos.append(
            f"el modelo acepto {len(aceptadas)} valor(es) deliberadamente falso(s): "
            f"su recuerdo de este hecho no es utilizable"
        )
        alertas.append("SICOFANCIA")
        return rep(Veredicto.NEGRO, 0.0)

    # ---- Regla 1: contradiccion con el ancla. Peor que no tener dato.
    if consenso is not None and anclas_ver:
        for a in anclas_ver:
            ac = comparar(a.magnitud, consenso, tol)
            if ac is Acuerdo.DISCREPANTE:
                motivos.append(
                    f"el consenso ({consenso}) contradice el ancla "
                    f"{a.tipo.value}:{a.localizador} ({a.magnitud})"
                )
                alertas.append("CONTRADICE_ANCLA")
                if orden_de_magnitud_distinto(a.magnitud, consenso):
                    alertas.append("ORDEN_DE_MAGNITUD")
                return rep(Veredicto.NEGRO, 0.0)

    # ---- Regla 2: discrepancia de categoria entre elicitaciones en clase critica.
    # El factor sale de la clase, no de una constante: en una dosis, un factor 2
    # es una sobredosis y no una imprecision.
    if consenso is not None and consenso.clase in CLASES_CRITICAS:
        f_alarma = factor_de_alarma(consenso.clase)
        for m in mags:
            if orden_de_magnitud_distinto(consenso, m, f_alarma):
                motivos.append(
                    f"discrepancia de factor {f_alarma:g} o mas en una clase critica "
                    f"({consenso.clase.value}): {consenso} frente a {m}"
                )
                alertas.append("ORDEN_DE_MAGNITUD")
                return rep(Veredicto.ROJO, 0.0)

    # ---- Regla 3: evidencia insuficiente.
    if len(validas) < MIN_ELICITACIONES and not anclas_ver:
        motivos.append(
            f"solo {len(validas)} elicitacion(es) utiles y ninguna ancla verificada "
            f"(minimo {MIN_ELICITACIONES})"
        )
        return rep(Veredicto.GRIS, 0.0)

    if not mags and anclas_ver:
        # el ancla sola basta para AMBAR: el dato existe en una fuente publica,
        # pero nadie verifico que ORIONS lo este interpretando bien
        consenso = anclas_ver[0].magnitud
        motivos.append("ancla verificada sin elicitaciones: cifra presente pero sin triangular")
        return rep(Veredicto.AMBAR, 0.45)

    # ---- Regla 4: dispersion.
    if cuota < CUOTA_CONSENSO_AMBAR:
        motivos.append(
            f"sin consenso: el grupo dominante solo reune {cuota:.0%} de "
            f"{len(mags)} elicitaciones, en {len(grupos)} grupos distintos"
        )
        return rep(Veredicto.ROJO, cuota * 0.3)

    # ---- Regla 5: fallo correlacionado por falta de diversidad de encuadre.
    apto_verde = n_enc >= MIN_ENCUADRES
    if not apto_verde:
        alertas.append("ENCUADRE_UNICO")
        motivos.append(
            f"solo {n_enc} encuadre(s) distinto(s) (minimo {MIN_ENCUADRES}): el consenso "
            f"puede ser fallo correlacionado, no convergencia"
        )

    # ---- Regla 5b: el modelo se abstuvo mas veces de las que respondio.
    if tasa_abstencion >= 0.5 and intentos >= MIN_ELICITACIONES:
        apto_verde = False
        alertas.append("ABSTENCION_ALTA")
        motivos.append(
            f"el modelo se abstuvo en {len(abstenciones)}/{intentos} encuadres: el acuerdo "
            f"de los que si respondieron no compensa que la mayoria no tenga el dato"
        )

    # ---- Regla 5c: el acuerdo es solo entre inferencias, no entre recuerdos.
    dominantes_e = [e for e in validas if e.magnitud in dominante]
    if dominantes_e and not any(
        e.certeza in (Certeza.RECUERDO_EXACTO, Certeza.RECUERDO_APROXIMADO)
        for e in dominantes_e
    ):
        apto_verde = False
        alertas.append("SOLO_INFERENCIA")
        motivos.append(
            "ninguna elicitacion del grupo dominante declara recordar el dato: el consenso "
            "es entre inferencias, que pueden compartir el mismo razonamiento equivocado"
        )

    # ---- Regla 5d: coinciden en el numero pero no en de donde sale.
    procs = {e.procedencia.clave() for e in dominantes_e
             if e.procedencia and e.procedencia.clave()}
    if len(procs) > 1:
        apto_verde = False
        alertas.append("PROCEDENCIA_INCOHERENTE")
        motivos.append(
            f"el grupo dominante coincide en la cifra pero la atribuye a fuentes distintas "
            f"({', '.join(sorted(procs))}): un numero bien recordado arrastra su estudio"
        )

    # ---- Regla 5e: la fisiologia apunta al lado contrario que la cifra.
    signos_mec = {e.signo_mecanismo for e in elicitaciones if e.signo_mecanismo}
    if consenso is not None and signos_mec:
        signo_cifra = _signo_de_cifra(consenso)
        if signo_cifra and all(s == -signo_cifra for s in signos_mec):
            alertas.append("MECANISMO_OPUESTO")
            motivos.append(
                f"el encuadre de mecanismo predice signo {list(signos_mec)[0]:+d} y la cifra "
                f"implica {signo_cifra:+d}: o la cifra esta mal o la cadena causal lo esta"
            )
            return rep(Veredicto.ROJO, 0.0)

    # ---- Regla 6: acreditacion.
    conf = _confianza(cuota, n_enc, len(mags), anclas_ver, consenso)

    if anclas_ver and cuota >= CUOTA_CONSENSO_VERDE and apto_verde:
        techo = hecho.techo()
        if techo == "VERDE":
            motivos.append(
                f"anclado en {nombre_ancla} y confirmado por {len(dominante)}/{len(mags)} "
                f"elicitaciones en {n_enc} encuadres"
            )
            return rep(Veredicto.VERDE, conf)
        motivos.append(f"consenso solido pero el ancla {nombre_ancla} solo alcanza {techo}")
        return rep(Veredicto.AMBAR, conf * 0.8)

    if not anclas_ver:
        motivos.append("consenso sin ancla verificada: se muestra como no anclado")
        alertas.append("SIN_ANCLA")
    return rep(Veredicto.AMBAR, conf * 0.7)


def _signo_de_cifra(m: Magnitud) -> int:
    """Direccion del efecto que implica una magnitud, o 0 si no implica ninguna."""
    if m.clase is Clase.RAZON_RIESGO:
        if m.valor < 0.97:
            return -1
        if m.valor > 1.03:
            return 1
        return 0
    if m.clase in (Clase.REDUCCION_REL, Clase.REDUCCION_ABS):
        return -1 if m.valor > 0 else 0
    return 0


def _representante(grupo: list[Magnitud]) -> Magnitud:
    """Elige el representante del grupo: el de valor mediano.

    La mediana, no la media: una elicitacion extrema no debe arrastrar la cifra
    que ORIONS va a mostrar.
    """
    if len(grupo) == 1:
        return grupo[0]
    ordenados = sorted(grupo, key=lambda m: m.valor)
    medio = ordenados[len(ordenados) // 2]
    # prefiere un representante que traiga intervalo de confianza
    con_ic = [m for m in grupo if m.ic_inf is not None]
    if con_ic and medio.ic_inf is None:
        cerca = min(con_ic, key=lambda m: abs(m.valor - medio.valor))
        if abs(cerca.valor - medio.valor) / max(abs(medio.valor), 1e-9) <= 0.05:
            return cerca
    return medio


def _confianza(cuota: float, n_enc: int, n: int,
               anclas: list, consenso: Optional[Magnitud]) -> float:
    """Confianza en 0 a 1. Multiplicativa: cada factor puede hundirla.

    Deliberadamente conservadora. Un numero alto aqui autoriza a ORIONS a
    mostrar una cifra a un estudiante sin etiqueta de advertencia.
    """
    f_consenso = min(1.0, cuota)
    f_encuadre = min(1.0, n_enc / 5.0)
    f_volumen = min(1.0, n / 6.0)
    orden = list(TipoAncla)
    if anclas:
        mejor = min(anclas, key=lambda a: orden.index(a.tipo))
        f_ancla = {
            TipoAncla.REGISTRO_ENSAYO: 1.0,
            TipoAncla.ETIQUETA_REGULADOR: 1.0,
            TipoAncla.NORMA_OFICIAL: 0.95,
            TipoAncla.GUIA_GOBIERNO: 0.9,
            TipoAncla.ARTICULO_CC_BY: 0.85,
            TipoAncla.ARTICULO_ABSTRACT: 0.6,
            TipoAncla.DERIVADA: 0.5,
        }.get(mejor.tipo, 0.3)
    else:
        f_ancla = 0.3
    f_ic = 1.0
    if consenso is not None and consenso.ic_inf is not None and consenso.ic_sup is not None:
        if consenso.valor != 0:
            amplitud = (consenso.ic_sup - consenso.ic_inf) / abs(consenso.valor)
            f_ic = 1.0 if amplitud < 0.5 else max(0.6, 1.0 - (amplitud - 0.5) / 2)
    return round(f_consenso * f_encuadre * f_volumen * f_ancla * f_ic, 4)


def aplicar(hecho: Hecho, elicitaciones: Sequence[Elicitacion],
            sondas: Sequence[SondaFalsa] = (), tol: float = TOL_DEFECTO,
            momento: str = "") -> Hecho:
    """Atestigua, escribe el resultado en el hecho y deja constancia.

    La version anterior sobreescribia veredicto y confianza en el mismo objeto
    sin dejar rastro. Eso hacia imposible responder "que cifra, con que
    veredicto, estaba publicada el dia tal": la Boveda se actualiza y el objeto
    es el mismo. Si algun dia hay que acreditar lo que una persona vio, la
    reconstruccion no sirve y la bitacora si. El registro es append-only.
    """
    previo = (hecho.veredicto, round(hecho.confianza, 4))
    r = atestiguar(hecho, elicitaciones, sondas, tol)
    hecho.veredicto = r.veredicto.value
    hecho.confianza = r.confianza
    hecho.diagnostico = r.dict()
    if r.magnitud_consenso is not None and hecho.magnitud is None:
        hecho.magnitud = r.magnitud_consenso
    if momento:
        detalle = (f"de {previo[0]}/{previo[1]} a {hecho.veredicto}/"
                   f"{round(hecho.confianza, 4)}")
        hecho.registrar(momento, "atestiguado", detalle)
    return hecho


def cola_de_revision(hechos: Sequence[Hecho]) -> list[Hecho]:
    """Ordena los hechos que necesitan ojo humano, por costo de equivocarse.

    Primero NEGRO (hay una contradiccion viva en la Boveda), luego ROJO en
    clases criticas (dosis y umbrales), luego el resto. Este orden es lo que
    hace viable la validacion medica con presupuesto cercano a cero: el medico
    no revisa la Boveda, revisa esta cola.
    """
    def prioridad(h: Hecho) -> tuple:
        peso_veredicto = {"NEGRO": 0, "ROJO": 1, "GRIS": 2, "AMBAR": 3, "VERDE": 4}
        critica = 0 if (h.magnitud and h.magnitud.clase in CLASES_CRITICAS) else 1
        return (peso_veredicto.get(h.veredicto, 5), critica, -h.confianza)

    return sorted(
        [h for h in hechos if h.veredicto in ("NEGRO", "ROJO", "GRIS", "AMBAR")],
        key=prioridad,
    )


__all__ = [
    "Encuadre", "Veredicto", "Elicitacion", "SondaFalsa", "Reporte",
    "Certeza", "Procedencia",
    "atestiguar", "aplicar", "cola_de_revision", "tolerancia", "TOL_POR_CLASE",
    "MIN_ELICITACIONES", "MIN_ENCUADRES", "CUOTA_CONSENSO_VERDE",
]
