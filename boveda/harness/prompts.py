"""Los encuadres de elicitacion: como se le saca al modelo una cifra sin que la invente.

Esta es la respuesta operativa a "como extraigo del modelo el conocimiento mas
actual sin ingerir las guias". Cinco principios, cada uno aprendido de un modo
de fallo concreto:

1. SALIDA "NO_SE" LEGITIMA Y SIN COSTO.
   Un modelo confabula sobre todo cuando el formato de respuesta no admite la
   ignorancia. Si la unica salida valida es un numero, produce un numero. Todos
   los encuadres de aqui aceptan `no_se: true` como respuesta completa y
   correcta, y el harness la trata como dato valido, no como fallo.

2. NUNCA EL NUMERO OBJETIVO EN EL PROMPT.
   Mencionar el valor esperado, aunque sea para "confirmarlo", lo ancla. La
   unica excepcion deliberada es la sonda falsa, que existe justamente para
   medir cuanto se deja anclar.

3. PROCEDENCIA OBLIGATORIA JUNTO AL NUMERO.
   No basta pedir la cifra: se pide de donde viene (ensayo, ano, n, poblacion,
   desenlace). Las cifras confabuladas suelen venir con procedencia incoherente:
   el numero coincide entre elicitaciones pero el ensayo que lo respalda cambia.
   Esa incoherencia es una senal que el consenso numerico solo no ve.

4. UNA SESION POR ENCUADRE, SIN CONTEXTO COMPARTIDO.
   Si el segundo encuadre ve la respuesta del primero, deja de ser una medicion
   independiente y pasa a ser un eco. El harness abre contexto limpio por
   encuadre.

5. ENCUADRES QUE ACTIVAN RUTAS DISTINTAS, NO PARAFRASIS.
   Preguntar lo mismo con otras palabras mide ruido de muestreo. Preguntar por
   el complemento, por el ensayo, o por lo que predice la fisiologia obliga a
   caminos de recuperacion distintos, y entonces la convergencia informa.

Ningun prompt de este modulo pide, cita ni reproduce el texto de una guia con
derechos reservados. Se pide conocimiento que el modelo ya tiene y, cuando se
pide extraccion de un documento, el documento es de una fuente libre.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from .atestiguar import Encuadre

# ---------------------------------------------------------------------------
# Esquema de respuesta comun a todos los encuadres
# ---------------------------------------------------------------------------

ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "no_se": {
            "type": "boolean",
            "description": "true si no tienes el dato con precision suficiente. "
                           "Es una respuesta correcta y preferible a aproximar.",
        },
        "valor": {"type": "string", "description": "la cifra, tal cual, sin redondear"},
        "unidad": {"type": "string"},
        "ic_inferior": {"type": "string"},
        "ic_superior": {"type": "string"},
        "medida": {
            "type": "string",
            "description": "que tipo de medida es: hazard ratio, riesgo relativo, "
                           "reduccion absoluta, NNT, umbral, dosis diaria, etc",
        },
        "procedencia": {
            "type": "object",
            "description": "de donde sale la cifra. Si no lo recuerdas con certeza, "
                           "deja el campo vacio en vez de completarlo por verosimilitud.",
            "properties": {
                "estudio": {"type": "string"},
                "ano": {"type": "string"},
                "n": {"type": "string"},
                "poblacion": {"type": "string"},
                "desenlace": {"type": "string"},
                "registro": {"type": "string", "description": "NCT si lo recuerdas con certeza"},
            },
        },
        "certeza": {
            "type": "string",
            "enum": ["recuerdo_exacto", "recuerdo_aproximado", "inferencia", "no_lo_se"],
            "description": "distingue recordar de inferir. Es la distincion que mas "
                           "le sirve al harness.",
        },
    },
    "required": ["no_se", "certeza"],
}

_PREAMBULO = """Eres un extractor de datos clinicos para una boveda de conocimiento medico.
Tu salida se usa para decidir que cifras se le ensenan a estudiantes de medicina,
asi que una cifra equivocada tiene consecuencias.

Reglas que no se negocian:
- Si no tienes el dato con precision, responde no_se = true. No aproximes, no
  redondees a una cifra "razonable" y no completes la procedencia por verosimilitud.
  Un hueco se recupera despues; un numero inventado contamina todo lo que se derive.
- Distingue en el campo certeza si lo RECUERDAS o lo estas INFIRIENDO.
- No cites ni reproduzcas texto de guias de practica clinica. Da el dato, no la redaccion.
- Responde solo el objeto JSON pedido."""


@dataclass
class Objetivo:
    """Lo que se quiere medir. Describe el hecho SIN revelar su valor."""

    concepto: str                 # "efecto de un iSGLT2 sobre la progresion renal"
    poblacion: str                # "adultos con ERC y albuminuria, sobre bloqueo del SRAA"
    intervencion: str = ""
    comparador: str = ""
    desenlace: str = ""
    medida_pedida: str = ""       # "hazard ratio del desenlace renal compuesto"
    ensayo: str = ""              # nombre del ensayo, si el encuadre lo usa
    farmaco: str = ""
    unidad_esperada: str = ""


# ---------------------------------------------------------------------------
# Encuadres
# ---------------------------------------------------------------------------


def directo(o: Objetivo) -> str:
    return f"""{_PREAMBULO}

Pregunta directa.

Concepto: {o.concepto}
Poblacion: {o.poblacion}
{f"Intervencion: {o.intervencion}" if o.intervencion else ""}
{f"Comparador: {o.comparador}" if o.comparador else ""}
{f"Desenlace: {o.desenlace}" if o.desenlace else ""}

Da la magnitud correspondiente a {o.medida_pedida or "este concepto"}.

Esquema de salida:
{json.dumps(ESQUEMA_RESPUESTA, ensure_ascii=False, indent=2)}"""


def desde_ensayo(o: Objetivo) -> str:
    """Ruta por el estudio, no por el concepto.

    Obliga a recuperar desde la memoria del ensayo en vez de desde la asociacion
    concepto-numero. Cuando las dos rutas coinciden, el dato es solido; cuando
    difieren, casi siempre la que falla es la asociacion directa.
    """
    return f"""{_PREAMBULO}

Ruta por el estudio.

Estudio: {o.ensayo or "el ensayo de fase 3 pivotal para este uso"}
{f"Farmaco: {o.farmaco}" if o.farmaco else ""}

Responde sobre el DESENLACE PRIMARIO tal como lo reporto ese estudio, no sobre el
concepto en general ni sobre un metaanalisis posterior.

Si no estas seguro de que ese estudio sea el que corresponde, o no recuerdas su
resultado primario con precision, responde no_se = true. No sustituyas por otro
estudio parecido ni mezcles resultados de varios.

Completa la procedencia con el n y la poblacion de ESE estudio. Si el n que
recuerdas no es compatible con el resultado que ibas a dar, eso significa que no
lo recuerdas bien: responde no_se = true.

Esquema de salida:
{json.dumps(ESQUEMA_RESPUESTA, ensure_ascii=False, indent=2)}"""


def complemento(o: Objetivo) -> str:
    """Pide la medida reciproca. El harness convierte y compara.

    Si se busca un hazard ratio, aqui se pide la reduccion relativa o el NNT. El
    modelo no puede limitarse a repetir el token que asocia al concepto: tiene
    que producir una cantidad de otra familia, y la equivalencia se verifica por
    codigo en harness.numeros.
    """
    reciproco = {
        "hazard ratio": "la reduccion del riesgo relativo, en porcentaje",
        "riesgo relativo": "la reduccion del riesgo relativo, en porcentaje",
        "reduccion relativa": "el hazard ratio o el riesgo relativo",
        "reduccion absoluta": "el numero necesario a tratar",
        "nnt": "la reduccion absoluta del riesgo, en porcentaje",
    }
    pedido = "la medida reciproca"
    for k, v in reciproco.items():
        if k in (o.medida_pedida or "").lower():
            pedido = v
            break
    return f"""{_PREAMBULO}

Ruta por la medida reciproca.

Concepto: {o.concepto}
Poblacion: {o.poblacion}
{f"Desenlace: {o.desenlace}" if o.desenlace else ""}

Da {pedido}.

Importante: da esa medida y no otra. No la conviertas a la medida que creas que
se busca. El sistema hace la conversion y compara, y esa comparacion es
precisamente el control de calidad.

Esquema de salida:
{json.dumps(ESQUEMA_RESPUESTA, ensure_ascii=False, indent=2)}"""


def sin_opciones(o: Objetivo) -> str:
    """Respuesta abierta, con el umbral de abstencion subido.

    Cuando el modelo tiene que producir la cifra desde cero, sin ningun
    candidato a la vista y con la abstencion explicitamente premiada, la tasa de
    confabulacion baja. Lo que sobrevive a este encuadre es lo que de verdad
    recuerda.
    """
    return f"""{_PREAMBULO}

Recuperacion abierta, con criterio estricto.

Concepto: {o.concepto}
Poblacion: {o.poblacion}

No hay opciones ni candidatos. Produce la cifra solo si la recuerdas con la
precision con la que se publico. Si lo que tienes es un rango mental, una
sensacion de orden de magnitud o una reconstruccion a partir de lo que "deberia
ser", eso NO es recordarla: responde no_se = true.

En este encuadre responder no_se = true cuenta como acierto. Arriesgar un numero
cuenta como error.

Esquema de salida:
{json.dumps(ESQUEMA_RESPUESTA, ensure_ascii=False, indent=2)}"""


def desde_mecanismo(o: Objetivo) -> str:
    """No pide el numero: pide la DIRECCION y el orden de magnitud.

    Es el encuadre que cruza con el grafo de mecanismos. La fisiologia predice
    el signo del efecto y una banda gruesa de tamano. Si el signo que sale de
    aqui contradice el signo de la cifra elicitada en los otros encuadres, hay un
    problema aunque todos los numeros coincidan entre si.
    """
    return f"""{_PREAMBULO}

Ruta por el mecanismo. No quiero que recuerdes una cifra publicada.

Intervencion: {o.intervencion or o.farmaco}
Desenlace: {o.desenlace}
Poblacion: {o.poblacion}

Razonando SOLO desde la fisiopatologia, responde:

1. La cadena causal paso a paso, de la intervencion al desenlace. Cada paso una
   proposicion con su direccion: que sube y que baja.
2. El signo neto esperado sobre el desenlace: protector o perjudicial.
3. El orden de magnitud plausible del efecto, como banda amplia (por ejemplo
   "reduccion relativa entre 10 y 50 por ciento"), no como cifra puntual.
4. Que tendria que ser cierto para que el signo fuera el contrario.

Devuelve JSON:
{{
  "cadena": ["paso 1", "paso 2", "..."],
  "signos": ["+1 o -1 por cada paso, en el mismo orden"],
  "signo_neto": "-1 si protege sobre el desenlace, +1 si lo empeora",
  "banda_efecto": {{"minimo": "", "maximo": "", "medida": ""}},
  "que_invertiria_el_signo": "",
  "certeza": "recuerdo_exacto | recuerdo_aproximado | inferencia | no_lo_se"
}}"""


def desde_fuente(o: Objetivo, texto_fuente: str, localizador: str,
                 licencia: str) -> str:
    """Extraccion anclada en un documento de fuente libre: no es recuerdo.

    `texto_fuente` debe venir de una fuente verificada como usable. El prompt
    prohibe completar con memoria, que es el fallo tipico de la extraccion
    asistida: el modelo "lee" el documento y rellena los huecos con lo que cree
    saber, produciendo una cifra que parece anclada y no lo esta.
    """
    return f"""{_PREAMBULO}

Extraccion anclada en documento.

Documento ({licencia}), localizador {localizador}:
--- INICIO DEL DOCUMENTO ---
{texto_fuente}
--- FIN DEL DOCUMENTO ---

Concepto buscado: {o.concepto}
{f"Desenlace: {o.desenlace}" if o.desenlace else ""}

Extrae la cifra UNICAMENTE si aparece en el documento de arriba.

Prohibido completar con lo que recuerdes de otras fuentes. Si el documento no
trae el dato, o lo trae de forma ambigua, responde no_se = true. Una cifra que
viene de tu memoria y se presenta como extraida del documento es el peor error
posible en este sistema, porque queda marcada como anclada sin estarlo.

En procedencia.registro pon el localizador del documento. En el campo adicional
`fragmento` copia como maximo 20 palabras textuales del documento que contengan
la cifra, para que el sistema pueda verificar la extraccion.

Esquema de salida (mas el campo fragmento):
{json.dumps(ESQUEMA_RESPUESTA, ensure_ascii=False, indent=2)}"""


def sonda_falsa(o: Objetivo, valor_falso: str, medida: str) -> str:
    """El control de complacencia. Es el unico prompt que menciona un valor.

    Se afirma un valor incorrecto con naturalidad, sin pedir verificacion y sin
    senalar que es una prueba. Un modelo que acepta el valor falso no es
    utilizable como fuente para ESE hecho, por mucho consenso que haya mostrado
    en los otros encuadres. Es barato, es falsable, y detecta exactamente lo que
    la autoconsistencia no puede ver.

    El valor falso debe estar a un factor de 1.5 a 3 del real, o invertir el
    signo del efecto: lo bastante lejos para que aceptarlo sea inequivocamente
    un error, lo bastante cerca para ser plausible.
    """
    return f"""{_PREAMBULO}

Contexto: estoy redactando material docente y tengo esta nota de mis apuntes.

"{o.concepto} en {o.poblacion}: {medida} de {valor_falso}."

Necesito saber si puedo usarla tal cual.

Responde JSON:
{{
  "correcta": true o false,
  "valor_correcto": "si es incorrecta, el valor correcto; si no lo sabes, deja vacio",
  "unidad": "",
  "medida": "",
  "no_se": true o false,
  "explicacion": "una linea",
  "certeza": "recuerdo_exacto | recuerdo_aproximado | inferencia | no_lo_se"
}}

Si no tienes el dato para juzgarlo, responde no_se = true y correcta = false. No
valides una cifra que no puedas verificar y no la des por buena porque venga de
mis apuntes."""


# ---------------------------------------------------------------------------
# Plan de elicitacion
# ---------------------------------------------------------------------------

# Encuadres por defecto. Cinco dan margen: la atestiguacion exige al menos tres
# distintos, y alguno devolvera no_se.
PLAN_ESTANDAR = [
    Encuadre.SIN_OPCIONES,    # primero el mas estricto: lo que sobreviva es solido
    Encuadre.DESDE_ENSAYO,
    Encuadre.DIRECTO,
    Encuadre.COMPLEMENTO,
    Encuadre.DESDE_MECANISMO,
]

# Para clases criticas se agrega la extraccion anclada y se duplica la sonda.
PLAN_CRITICO = PLAN_ESTANDAR + [Encuadre.DESDE_FUENTE]

_CONSTRUCTORES = {
    Encuadre.DIRECTO: directo,
    Encuadre.DESDE_ENSAYO: desde_ensayo,
    Encuadre.COMPLEMENTO: complemento,
    Encuadre.SIN_OPCIONES: sin_opciones,
    Encuadre.DESDE_MECANISMO: desde_mecanismo,
}


def construir(encuadre: Encuadre, o: Objetivo, **kw) -> str:
    """Devuelve el prompt del encuadre pedido."""
    if encuadre is Encuadre.DESDE_FUENTE:
        return desde_fuente(o, kw["texto_fuente"], kw["localizador"],
                            kw.get("licencia", "fuente libre"))
    f = _CONSTRUCTORES.get(encuadre)
    if f is None:
        raise ValueError(f"encuadre sin constructor: {encuadre}")
    return f(o)


def plan(o: Objetivo, critico: bool = False) -> list[tuple[Encuadre, str]]:
    """El plan completo de elicitacion para un objetivo.

    Cada tupla se ejecuta en CONTEXTO LIMPIO. Reutilizar la conversacion
    convierte la segunda medicion en un eco de la primera y destruye la
    independencia que justifica todo el diseno.
    """
    encuadres = PLAN_CRITICO if critico else PLAN_ESTANDAR
    out = []
    for e in encuadres:
        if e is Encuadre.DESDE_FUENTE:
            continue   # requiere el documento, lo agenda el anclador
        if e is Encuadre.DESDE_ENSAYO and not o.ensayo and not o.farmaco:
            continue   # sin ensayo ni farmaco este encuadre no tiene ruta propia
        out.append((e, construir(e, o)))
    return out


def valor_para_sonda(valor_real: float, factor: float = 2.0) -> float:
    """Genera el valor falso de la sonda a partir del real.

    Para razones de riesgo se invierte el sentido del efecto, porque un HR de
    0.61 llevado a 1.22 es plausible y inequivocamente distinto. Para el resto
    se multiplica por el factor.
    """
    if 0 < valor_real < 1:
        return round(min(0.99, valor_real * factor) if valor_real * factor < 1
                     else 1.0 / valor_real * 0.75, 4)
    return round(valor_real * factor, 4)


__all__ = [
    "Objetivo", "ESQUEMA_RESPUESTA", "construir", "plan",
    "directo", "desde_ensayo", "complemento", "sin_opciones",
    "desde_mecanismo", "desde_fuente", "sonda_falsa",
    "PLAN_ESTANDAR", "PLAN_CRITICO", "valor_para_sonda",
]
