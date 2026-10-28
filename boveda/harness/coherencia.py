"""Cierre aritmetico: detectar confabulacion SIN ninguna fuente externa.

Este modulo responde la pregunta que el resto de la Boveda esquivaba.

El resto del harness exige un ancla: si no hay documento publico donde verificar
la cifra, el hecho va a cuarentena. Eso es correcto pero insuficiente, porque
deja fuera justo lo que mas se necesita: el conocimiento que el modelo YA TIENE
y para el que no existe ancla publica. Responder "no se puede mostrar" a todo
eso no es resolver el problema, es rechazarlo.

EL ERROR CONCEPTUAL QUE ESTE MODULO CORRIGE

Tratar una cifra recordada como una consulta aislada, verificable solo por fuera.
No lo es. Una cifra clinica vive en una RED DE RESTRICCIONES ARITMETICAS, y esa
red se puede comprobar sin salir del modelo:

  - El intervalo de confianza de una razon es simetrico en escala logaritmica
    POR CONSTRUCCION. No es una convencion: sale de como se calcula.
  - El ancho del intervalo DETERMINA el numero de eventos del estudio:
    SE(ln HR) = (ln U - ln L) / 3.92,  y  eventos = 4 / SE^2.
  - El numero de eventos tambien se deduce del tamano de muestra y de la tasa
    del grupo control. Las dos deducciones tienen que coincidir.
  - La razon, la reduccion absoluta, el numero necesario a tratar y las tasas de
    cada brazo forman un sistema con mas ecuaciones que incognitas.

Preguntar lo mismo diez veces mide ruido de muestreo. Preguntar por CANTIDADES
LIGADAS y comprobar si el sistema cierra mide algo distinto: si el modelo
recuerda un estudio real o esta rellenando huecos. Cuando confabula hace
coincidencia de patrones, no aritmetica, asi que produce numeros localmente
plausibles y globalmente inconsistentes.

VALIDACION, no teoria

De "HR 0.61 (95% CI 0.51-0.72)" sin ninguna fuente externa, la formula predice
517 eventos. DAPA-CKD publico 509. Error del 1.5%.

Y las dos formas tipicas de fabricacion quedan atrapadas:
  - intervalo inventado demasiado estrecho, "HR 0.61 (0.59-0.63)" con 4304
    pacientes: implica 14,284 eventos en 4,304 personas, 28 veces mas de lo
    posible;
  - intervalo tomado de otro analisis, "HR 0.61 (0.55-0.95)": asimetria
    logaritmica de 1.22, cuando las cinco cifras reales medidas en este proyecto
    caen entre 0.005 y 0.093.

LO QUE ESTO SI PRUEBA Y LO QUE NO

Pasar el cierre prueba que el modelo recuerda un conjunto de cantidades
mutuamente consistentes, es decir que recuerda un estudio REAL. No prueba que
sea el estudio CORRECTO para la afirmacion: un recuerdo coherente del ensayo
equivocado pasa igual. Es el mismo riesgo de mala seleccion que tiene la
extraccion directa, y se trata igual: el hecho se puede mostrar, etiquetado, y
la seleccion queda pendiente de una segunda lectura.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .numeros import Clase, Magnitud, convertir_concentracion

Z95 = 1.959963985

# Umbrales calibrados contra cifras reales, no elegidos a mano.
#
# La asimetria logaritmica de cinco razones reales ancladas en este proyecto cayo
# entre 0.005 y 0.093. El redondeo a dos decimales introduce por si solo hasta
# ~0.16, asi que 0.50 deja un margen amplio y sigue atrapando una asimetria de
# 1.22, que es lo que produce emparejar un punto estimado con el intervalo de
# otro analisis.
MAX_ASIMETRIA = 0.50

# La formula eventos = 4/SE^2 supone dos brazos balanceados y prueba de rangos
# logaritmicos. Con asignacion desbalanceada o con covariables es aproximada. En
# el caso real medido la razon entre las dos deducciones fue 1.03; un factor 4
# deja margen de sobra y sigue atrapando un factor 28.
MAX_RAZON_EVENTOS = 4.0

# Tolerancia relativa para las identidades exactas (razon, reduccion absoluta,
# numero necesario a tratar). Aqui no hay aproximacion: la identidad es exacta y
# lo unico que la mueve es el redondeo de lo publicado.
TOL_IDENTIDAD = 0.08


class Cierre(str, Enum):
    CIERRA = "cierra"                  # el sistema es consistente
    NO_CIERRA = "no_cierra"            # hay contradiccion aritmetica
    INSUFICIENTE = "insuficiente"      # faltan cantidades para comprobar nada


@dataclass
class FalloCierre:
    codigo: str
    detalle: str
    severidad: str = "alta"            # alta bloquea, media degrada
    medido: str = ""
    esperado: str = ""

    def dict(self) -> dict:
        return {"codigo": self.codigo, "detalle": self.detalle,
                "severidad": self.severidad, "medido": self.medido,
                "esperado": self.esperado}


@dataclass
class Observacion:
    """Las cantidades ligadas que se le piden al modelo, cada una por separado.

    Ninguna es obligatoria. El modulo comprueba las relaciones que los datos
    disponibles permitan comprobar, y dice cuantas comprobo: un cierre que solo
    pudo verificar una relacion vale mucho menos que uno que verifico cuatro.
    """

    razon: Optional[Magnitud] = None          # HR, RR u OR con su intervalo
    n_total: Optional[float] = None           # participantes aleatorizados
    eventos_total: Optional[float] = None     # eventos del desenlace, ambos brazos
    tasa_control: Optional[float] = None      # incidencia acumulada en control, 0 a 1
    tasa_tratado: Optional[float] = None      # idem en el brazo activo
    reduccion_absoluta: Optional[float] = None
    nnt: Optional[float] = None
    reduccion_relativa: Optional[float] = None
    significativo_declarado: Optional[bool] = None   # lo que el modelo AFIRMA
    seguimiento_anios: Optional[float] = None

    # para cierre de unidades y de dosis
    concentracion_a: Optional[Magnitud] = None
    concentracion_b: Optional[Magnitud] = None
    analito: str = ""
    dosis_por_toma: Optional[float] = None
    tomas_por_dia: Optional[float] = None
    dosis_diaria: Optional[float] = None
    dosis_por_kg: Optional[float] = None
    peso_kg: Optional[float] = None


@dataclass
class ReporteCierre:
    cierre: Cierre
    relaciones_comprobadas: int
    relaciones_falladas: int
    fallos: list[FalloCierre] = field(default_factory=list)
    derivados: dict = field(default_factory=dict)
    confianza: float = 0.0

    def dict(self) -> dict:
        return {
            "cierre": self.cierre.value,
            "relaciones_comprobadas": self.relaciones_comprobadas,
            "relaciones_falladas": self.relaciones_falladas,
            "confianza": round(self.confianza, 4),
            "fallos": [f.dict() for f in self.fallos],
            "derivados": {k: (round(v, 4) if isinstance(v, float) else v)
                          for k, v in self.derivados.items()},
        }


# ---------------------------------------------------------------------------
# Derivaciones
# ---------------------------------------------------------------------------


def error_estandar_log(m: Magnitud) -> Optional[float]:
    """Error estandar del logaritmo de una razon, a partir de su intervalo.

    Es la bisagra de todo el modulo: convierte el ancho del intervalo en una
    cantidad estadistica con la que se puede razonar.
    """
    if m.ic_inf is None or m.ic_sup is None:
        return None
    if m.ic_inf <= 0 or m.ic_sup <= 0 or m.ic_sup <= m.ic_inf:
        return None
    return (math.log(m.ic_sup) - math.log(m.ic_inf)) / (2 * Z95)


def eventos_que_implica(m: Magnitud) -> Optional[float]:
    """Numero de eventos que el intervalo de confianza esta afirmando.

    Para una prueba de rangos logaritmicos con dos brazos balanceados,
    SE(ln HR) es aproximadamente la raiz de 4 dividida entre el total de
    eventos, de donde eventos = 4 / SE^2.

    Esto es lo que hace detectable un intervalo inventado: nadie que fabrica un
    intervalo se detiene a comprobar cuantos eventos implica, y un intervalo
    estrecho implica muchisimos.
    """
    se = error_estandar_log(m)
    if se is None or se <= 0:
        return None
    return 4.0 / (se * se)


def eventos_que_implican_n_y_tasa(n_total: float, tasa_control: float,
                                  razon: float) -> Optional[float]:
    """Eventos esperados a partir del tamano de muestra y la tasa del control."""
    if n_total <= 0 or not (0 < tasa_control < 1) or razon <= 0:
        return None
    return (n_total / 2.0) * tasa_control * (1.0 + razon)


def asimetria_log(m: Magnitud) -> Optional[float]:
    """Cuanto se desvia el punto estimado del centro logaritmico del intervalo.

    Se mide en unidades de error estandar. Para una razon con intervalo de Wald
    el punto estimado ESTA en el centro logaritmico por construccion, asi que una
    desviacion grande significa que el punto y el intervalo no salieron del mismo
    analisis.
    """
    se = error_estandar_log(m)
    if se is None or se <= 0 or m.valor <= 0:
        return None
    centro = (math.log(m.ic_inf) + math.log(m.ic_sup)) / 2
    return abs(math.log(m.valor) - centro) / se


def asimetria_natural(m: Magnitud) -> Optional[float]:
    """Igual que la anterior pero en escala natural, para diferencias y proporciones."""
    if m.ic_inf is None or m.ic_sup is None or m.ic_sup <= m.ic_inf:
        return None
    se = (m.ic_sup - m.ic_inf) / (2 * Z95)
    if se <= 0:
        return None
    return abs(m.valor - (m.ic_inf + m.ic_sup) / 2) / se


def _cerca(a: float, b: float, tol: float = TOL_IDENTIDAD) -> bool:
    d = max(abs(a), abs(b))
    return abs(a - b) <= tol * d if d else abs(a - b) <= tol


# ---------------------------------------------------------------------------
# El cierre
# ---------------------------------------------------------------------------


def verificar(obs: Observacion) -> ReporteCierre:
    """Comprueba todas las relaciones que las cantidades disponibles permitan."""
    fallos: list[FalloCierre] = []
    derivados: dict = {}
    comprobadas = 0

    m = obs.razon
    es_razon = m is not None and m.clase is Clase.RAZON_RIESGO

    # ---- 1. el punto estimado dentro de su propio intervalo
    if m is not None and m.ic_inf is not None and m.ic_sup is not None:
        comprobadas += 1
        if not (m.ic_inf <= m.valor <= m.ic_sup):
            fallos.append(FalloCierre(
                "PUNTO_FUERA_DEL_INTERVALO",
                f"el punto estimado {m.valor:g} no esta dentro de su intervalo "
                f"[{m.ic_inf:g}, {m.ic_sup:g}]. Es imposible y no admite matices",
                "alta", medido=f"{m.valor:g}",
                esperado=f"entre {m.ic_inf:g} y {m.ic_sup:g}"))

    # ---- 2. simetria del intervalo
    if m is not None:
        asim = asimetria_log(m) if es_razon else asimetria_natural(m)
        if asim is not None:
            comprobadas += 1
            derivados["asimetria"] = asim
            if asim > MAX_ASIMETRIA:
                escala = "logaritmica" if es_razon else "natural"
                fallos.append(FalloCierre(
                    "INTERVALO_ASIMETRICO",
                    f"el punto estimado se desvia {asim:.2f} errores estandar del centro "
                    f"{escala} de su intervalo. En un intervalo de Wald el punto esta en "
                    f"el centro por construccion, asi que esto significa que el punto y "
                    f"el intervalo no salieron del mismo analisis. En cifras reales "
                    f"medidas aqui esta desviacion cayo entre 0.005 y 0.093",
                    "alta", medido=f"{asim:.3f}", esperado=f"menor que {MAX_ASIMETRIA}"))

    # ---- 3. eventos: lo que implica el intervalo contra lo que implican N y la tasa
    if es_razon:
        d_ic = eventos_que_implica(m)
        if d_ic is not None:
            derivados["eventos_implicados_por_el_intervalo"] = d_ic

            if obs.eventos_total:
                comprobadas += 1
                razon_d = (max(d_ic, obs.eventos_total) / min(d_ic, obs.eventos_total)
                           if min(d_ic, obs.eventos_total) > 0 else float("inf"))
                derivados["razon_eventos_vs_declarados"] = razon_d
                if razon_d > MAX_RAZON_EVENTOS:
                    fallos.append(FalloCierre(
                        "EVENTOS_INCOMPATIBLES_CON_EL_INTERVALO",
                        f"el ancho del intervalo implica unos {d_ic:.0f} eventos y se "
                        f"declaran {obs.eventos_total:.0f}: discrepancia de "
                        f"{razon_d:.1f} veces. Un intervalo no se puede elegir aparte "
                        f"del numero de eventos, porque es el numero de eventos el que "
                        f"lo determina",
                        "alta", medido=f"{obs.eventos_total:.0f}",
                        esperado=f"del orden de {d_ic:.0f}"))

            if obs.n_total and obs.tasa_control:
                d_n = eventos_que_implican_n_y_tasa(obs.n_total, obs.tasa_control, m.valor)
                if d_n:
                    comprobadas += 1
                    derivados["eventos_esperados_de_n_y_tasa"] = d_n
                    razon_d = (max(d_ic, d_n) / min(d_ic, d_n)
                               if min(d_ic, d_n) > 0 else float("inf"))
                    derivados["razon_eventos_ic_vs_n"] = razon_d
                    if razon_d > MAX_RAZON_EVENTOS:
                        fallos.append(FalloCierre(
                            "INTERVALO_INCOMPATIBLE_CON_EL_TAMANO_DE_MUESTRA",
                            f"el intervalo implica unos {d_ic:.0f} eventos, pero con "
                            f"{obs.n_total:.0f} participantes y una tasa de control de "
                            f"{obs.tasa_control:.1%} caben unos {d_n:.0f}: discrepancia "
                            f"de {razon_d:.1f} veces. Es la firma de un intervalo "
                            f"inventado",
                            "alta", medido=f"{d_ic:.0f} eventos implicados",
                            esperado=f"del orden de {d_n:.0f}"))
                    if d_ic > obs.n_total:
                        fallos.append(FalloCierre(
                            "MAS_EVENTOS_QUE_PARTICIPANTES",
                            f"el intervalo implica {d_ic:.0f} eventos en "
                            f"{obs.n_total:.0f} participantes. Imposible",
                            "alta"))

    # ---- 4. identidades entre tasas, razon, reduccion absoluta y numero necesario
    if obs.tasa_control and obs.tasa_tratado:
        if es_razon:
            comprobadas += 1
            rr_impl = obs.tasa_tratado / obs.tasa_control
            derivados["razon_implicada_por_las_tasas"] = rr_impl
            if not _cerca(rr_impl, m.valor):
                fallos.append(FalloCierre(
                    "RAZON_NO_COINCIDE_CON_LAS_TASAS",
                    f"las tasas declaradas ({obs.tasa_tratado:.1%} frente a "
                    f"{obs.tasa_control:.1%}) implican una razon de {rr_impl:.3f} y se "
                    f"declara {m.valor:g}",
                    "alta", medido=f"{m.valor:g}", esperado=f"{rr_impl:.3f}"))
        arr_impl = obs.tasa_control - obs.tasa_tratado
        derivados["reduccion_absoluta_implicada"] = arr_impl
        if obs.reduccion_absoluta is not None:
            comprobadas += 1
            if not _cerca(arr_impl, obs.reduccion_absoluta):
                fallos.append(FalloCierre(
                    "REDUCCION_ABSOLUTA_NO_COINCIDE",
                    f"las tasas implican una reduccion absoluta de {arr_impl:.4f} y se "
                    f"declara {obs.reduccion_absoluta:.4f}",
                    "alta", medido=f"{obs.reduccion_absoluta:.4f}",
                    esperado=f"{arr_impl:.4f}"))
        if obs.nnt is not None and arr_impl > 0:
            comprobadas += 1
            nnt_impl = 1.0 / arr_impl
            derivados["nnt_implicado"] = nnt_impl
            if not _cerca(nnt_impl, obs.nnt, max(TOL_IDENTIDAD, 0.12)):
                fallos.append(FalloCierre(
                    "NNT_NO_COINCIDE",
                    f"la reduccion absoluta implica un numero necesario a tratar de "
                    f"{nnt_impl:.1f} y se declara {obs.nnt:g}. El numero necesario a "
                    f"tratar es exactamente el reciproco de la reduccion absoluta",
                    "alta", medido=f"{obs.nnt:g}", esperado=f"{nnt_impl:.1f}"))

    if es_razon and obs.reduccion_relativa is not None:
        comprobadas += 1
        rrr_impl = 1.0 - m.valor
        derivados["reduccion_relativa_implicada"] = rrr_impl
        if not _cerca(rrr_impl, obs.reduccion_relativa):
            fallos.append(FalloCierre(
                "REDUCCION_RELATIVA_NO_COINCIDE",
                f"una razon de {m.valor:g} implica una reduccion relativa de "
                f"{rrr_impl:.3f} y se declara {obs.reduccion_relativa:.3f}. Es el error "
                f"de interpretacion mas frecuente: confundir la razon con su complemento",
                "alta", medido=f"{obs.reduccion_relativa:.3f}",
                esperado=f"{rrr_impl:.3f}"))

    # ---- 5. la afirmacion cualitativa contra el intervalo
    if es_razon and obs.significativo_declarado is not None and m.ic_inf and m.ic_sup:
        comprobadas += 1
        cruza_uno = m.ic_inf <= 1.0 <= m.ic_sup
        derivados["intervalo_cruza_la_unidad"] = cruza_uno
        if obs.significativo_declarado and cruza_uno:
            fallos.append(FalloCierre(
                "SIGNIFICANCIA_CONTRADICE_EL_INTERVALO",
                f"se afirma un efecto significativo y el intervalo "
                f"[{m.ic_inf:g}, {m.ic_sup:g}] cruza la unidad",
                "alta"))
        if not obs.significativo_declarado and not cruza_uno:
            fallos.append(FalloCierre(
                "SIGNIFICANCIA_CONTRADICE_EL_INTERVALO",
                f"se afirma que no hay efecto significativo y el intervalo "
                f"[{m.ic_inf:g}, {m.ic_sup:g}] no cruza la unidad",
                "media"))

    # ---- 6. cierre de unidades de laboratorio
    if obs.concentracion_a is not None and obs.concentracion_b is not None:
        a, b = obs.concentracion_a, obs.concentracion_b
        if obs.analito:
            a.analito = a.analito or obs.analito
            b.analito = b.analito or obs.analito
        conv = convertir_concentracion(b, a.unidad or "")
        if conv is not None:
            comprobadas += 1
            derivados["concentracion_b_convertida"] = conv.valor
            if not _cerca(conv.valor, a.valor, 0.05):
                fallos.append(FalloCierre(
                    "UNIDADES_NO_RECONCILIAN",
                    f"se declaran {a.valor:g} {a.unidad} y {b.valor:g} {b.unidad} del "
                    f"mismo analito, pero el segundo equivale a {conv.valor:.3g} "
                    f"{a.unidad}. La conversion entre unidades es fija: si no cierra, "
                    f"una de las dos cifras no es de este analito",
                    "alta", medido=f"{a.valor:g} {a.unidad}",
                    esperado=f"{conv.valor:.3g} {a.unidad}"))

    # ---- 7. cierre de dosis
    if obs.dosis_por_toma and obs.tomas_por_dia and obs.dosis_diaria:
        comprobadas += 1
        diaria_impl = obs.dosis_por_toma * obs.tomas_por_dia
        derivados["dosis_diaria_implicada"] = diaria_impl
        if not _cerca(diaria_impl, obs.dosis_diaria, 0.02):
            fallos.append(FalloCierre(
                "DOSIS_DIARIA_NO_COINCIDE",
                f"{obs.dosis_por_toma:g} por toma y {obs.tomas_por_dia:g} tomas al dia "
                f"dan {diaria_impl:g}, y se declara {obs.dosis_diaria:g}",
                "alta", medido=f"{obs.dosis_diaria:g}", esperado=f"{diaria_impl:g}"))

    if obs.dosis_por_kg and obs.peso_kg and obs.dosis_diaria:
        comprobadas += 1
        abs_impl = obs.dosis_por_kg * obs.peso_kg
        derivados["dosis_absoluta_implicada"] = abs_impl
        if not _cerca(abs_impl, obs.dosis_diaria, 0.05):
            fallos.append(FalloCierre(
                "DOSIS_POR_PESO_NO_COINCIDE",
                f"{obs.dosis_por_kg:g} por kilogramo en {obs.peso_kg:g} kg dan "
                f"{abs_impl:g}, y se declara {obs.dosis_diaria:g}. Es la firma de una "
                f"confusion entre dosis por peso y dosis absoluta, que es el error de "
                f"dosificacion mas frecuente y el mas grave",
                "alta", medido=f"{obs.dosis_diaria:g}", esperado=f"{abs_impl:g}"))

    # ---- veredicto
    graves = [f for f in fallos if f.severidad == "alta"]
    if comprobadas == 0:
        cierre = Cierre.INSUFICIENTE
    elif graves:
        cierre = Cierre.NO_CIERRA
    else:
        cierre = Cierre.CIERRA

    return ReporteCierre(
        cierre=cierre, relaciones_comprobadas=comprobadas,
        relaciones_falladas=len(fallos), fallos=fallos, derivados=derivados,
        confianza=_confianza(cierre, comprobadas, len(graves)),
    )


def _confianza(cierre: Cierre, comprobadas: int, graves: int) -> float:
    """Confianza que da el cierre aritmetico, sin ninguna fuente externa.

    Crece con el NUMERO de relaciones comprobadas, no con la insistencia: cada
    relacion independiente que cierra multiplica la dificultad de haberlo logrado
    por azar. Y tiene un tope por debajo de 1 a proposito, porque el cierre
    prueba que el modelo recuerda un estudio real, no que sea el estudio correcto
    para esta afirmacion.
    """
    if cierre is Cierre.NO_CIERRA:
        return 0.0
    if cierre is Cierre.INSUFICIENTE:
        return 0.0
    # 1 relacion 0.35, 2 -> 0.52, 3 -> 0.63, 4 -> 0.70, 6 -> 0.78, tope 0.80
    return round(min(0.80, 0.35 + 0.17 * math.log(comprobadas) / math.log(2)), 4)


def plan_de_preguntas(concepto: str, poblacion: str, desenlace: str = "") -> list[dict]:
    """Las cantidades ligadas que hay que pedir, cada una en contexto limpio.

    Son preguntas SEPARADAS y en sesiones separadas, por la misma razon que los
    encuadres de harness.prompts: si el modelo ve su respuesta anterior, deja de
    ser una medicion independiente y el sistema de ecuaciones se vuelve
    tautologico. El modelo no debe poder saber que se le esta comprobando la
    aritmetica, o la hara.
    """
    base = f"{concepto} en {poblacion}" + (f", desenlace {desenlace}" if desenlace else "")
    return [
        {"campo": "razon", "pregunta": f"Razon de riesgo del desenlace para {base}, "
                                       f"con su intervalo de confianza del 95%."},
        {"campo": "n_total", "pregunta": f"Numero de participantes aleatorizados en el "
                                         f"ensayo pivotal de {base}."},
        {"campo": "eventos_total", "pregunta": f"Numero total de eventos del desenlace "
                                               f"primario, sumando ambos brazos, en ese ensayo."},
        {"campo": "tasa_control", "pregunta": f"Incidencia acumulada del desenlace en el "
                                              f"grupo placebo o control de ese ensayo, en porcentaje."},
        {"campo": "tasa_tratado", "pregunta": f"Incidencia acumulada del desenlace en el "
                                              f"grupo de intervencion de ese ensayo, en porcentaje."},
        {"campo": "nnt", "pregunta": f"Numero necesario a tratar del desenlace primario "
                                     f"en ese ensayo."},
        {"campo": "seguimiento_anios", "pregunta": f"Duracion de seguimiento mediana de "
                                                   f"ese ensayo, en anios."},
    ]


__all__ = [
    "Observacion", "ReporteCierre", "FalloCierre", "Cierre", "verificar",
    "error_estandar_log", "eventos_que_implica", "eventos_que_implican_n_y_tasa",
    "asimetria_log", "asimetria_natural", "plan_de_preguntas",
    "MAX_ASIMETRIA", "MAX_RAZON_EVENTOS", "TOL_IDENTIDAD", "Z95",
]
