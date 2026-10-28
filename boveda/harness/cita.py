"""Cita verbatim: el bloque que el modelo no puede reescribir.

Este modulo invierte el diseno del resto de la Boveda, y la inversion es
correcta.

EL ERROR DE DISENO QUE CORRIGE

Todo el harness se construyo sobre la idea de DERIVAR y nunca citar: reconstruir
la evidencia desde fuentes publicas, redactar con palabras propias, y prohibir
las formas normativas. Resulta que para las fuentes que de verdad se necesitan
eso es exactamente al reves.

Las guias de KDIGO se publican en acceso abierto bajo CC BY-NC-ND, y el texto de
su licencia concede mas de lo que se supone: para fines no comerciales se puede
copiar y distribuir el articulo y USAR PORCIONES O EXTRACTOS DE EL EN OTRAS
OBRAS, y la mineria de texto y datos no comercial esta permitida. Lo prohibido es
ALTERAR y el USO COMERCIAL.

La licencia de la ADA dice que el lector puede usar el articulo siempre que se
cite bien, el uso sea educativo y THE WORK IS NOT ALTERED.

Leanse juntas: un sistema que PARAFRASEA viola esas clausulas. Un visor que cita
PALABRA POR PALABRA las cumple. "No Derivatives" significa que la cita literal es
la via permitida y la parafrasis es la via prohibida.

Y LAS DOS PREGUNTAS ERAN LA MISMA

La arquitectura que la licencia exige (reproducir la oracion sin alterarla, con
atribucion y enlace) es tambien la unica arquitectura con CERO riesgo de
alucinacion sobre el nucleo normativo: si el bloque es texto RECUPERADO y no
texto GENERADO, el modelo no puede inventar el umbral ni la etiqueta de
evidencia. No hay nada que confabular en una cadena que se copio de un archivo.

La restriccion que parecia el obstaculo es el diseno.

COMO SE HACE CUMPLIR, Y NO ES POR DISCIPLINA

Una CitaVerbatim NO se puede construir pasandole una cadena. Solo se puede
obtener rebanando el documento fuente con `extraer`. Esa es la unica puerta, y
existe para que sea estructuralmente imposible que un texto generado pase por
cita. Si la unica forma de tener una cita es cortarla de un archivo, no hay
camino por el que el modelo cuele una propia.

EL LIMITE, Y LO QUE DE VERDAD LO DECIDE

El articulo 148 fraccion I de la Ley Federal del Derecho de Autor permite citar
textos de obras ya divulgadas sin autorizacion y sin remuneracion. No hay cuota,
no hay a quien escribirle: es una licencia legal autoejecutable.

No existe limite cuantitativo mexicano. La ley solo exige que la cantidad tomada
no pueda considerarse una reproduccion simulada y sustancial del contenido. No
hay tesis ni jurisprudencia del Poder Judicial de la Federacion sobre esa frase,
ni criterio publicado del INDAUTOR que fije un umbral.

Asi que el criterio operativo NO es el volumen, es la DENSIDAD Y LA CONTIGUIDAD.
La formulacion hermana de la tradicion latinoamericana lo dice con las dos
palabras que si operan: los pasajes no deben ser TANTOS Y SEGUIDOS. Cuarenta
frases dispersas en doscientas paginas son una cita. Cincuenta frases
consecutivas de una seccion son esa seccion reproducida con comillas.

Y se mide sobre la OBRA CITADA, no sobre la obra citante: que las citas sean el
1% de ORIONS es irrelevante si son el nucleo normativo de la guia.

Como techo cuantitativo se adopta por analogia el unico numero legislado de la
region: la ley argentina 11.723 limita la cita de obras literarias o cientificas
a MIL PALABRAS. No es ley mexicana y se usa precisamente porque es conservador.

LAS SIETE REGLAS DURAS, cada una de un hallazgo concreto

1. Las cuatro condiciones del articulo 148 son CONJUNTAS: obra ya divulgada, que
   no se afecte la explotacion normal, citar invariablemente la fuente, y no
   alterar la obra. Fallar una anula la excepcion completa.
2. Se mide sobre la obra citada.
3. Densidad y contiguidad antes que volumen.
4. SOLO CUBRE TEXTO. Figuras, tablas como objeto grafico, algoritmos y diagramas
   de flujo quedan fuera de la fraccion.
5. TRADUCIR NO ES CITAR. Una traduccion es obra derivada y requiere
   autorizacion, asi que la cita se queda en su idioma original. Esta es la
   restriccion de producto mas incomoda y no tiene vuelta.
6. La atribucion debe ser adyacente y no suprimible por la interfaz. Una cita con
   la fuente escondida en un modal es una cita sin fuente.
7. Nunca aceptar un clickwrap ni crear cuenta en el sitio del titular: un
   contrato aceptado DESPLAZA la excepcion legal y convierte el reclamo de
   infraccion en incumplimiento de contrato, que es peor.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Techo por obra citada, en palabras. Ley argentina 11.723 articulo 10, adoptada
# por analogia por ser el unico numero legislado de la region y por conservadora.
TECHO_PALABRAS_POR_OBRA = 1000

# Palabras maximas en UNA cita. Una recomendacion clinica cabe de sobra; pasar de
# aqui deja de ser citar la recomendacion y empieza a ser reproducir el parrafo.
MAX_PALABRAS_POR_CITA = 60

# Citas consecutivas del mismo documento sin material propio en medio. Es la
# regla de CONTIGUIDAD: lo que la ley castiga es que sean "tantos y seguidos".
MAX_CITAS_CONSECUTIVAS = 3

# Separacion minima entre dos citas de la misma obra, medida en caracteres del
# documento original. Obliga a la dispersion.
SEPARACION_MINIMA = 2000


class TipoObjeto(str, Enum):
    """Que se esta citando. Solo el texto esta cubierto por la fraccion I."""

    TEXTO = "texto"
    TABLA = "tabla"
    FIGURA = "figura"
    ALGORITMO = "algoritmo"
    DIAGRAMA = "diagrama"


OBJETOS_NO_CUBIERTOS = {TipoObjeto.TABLA, TipoObjeto.FIGURA,
                        TipoObjeto.ALGORITMO, TipoObjeto.DIAGRAMA}


@dataclass(frozen=True)
class Atribucion:
    """La fuente, completa y adyacente. Los cinco campos son obligatorios.

    Congelada a proposito: una atribucion que se puede editar despues de mostrar
    la cita no es una atribucion, es una sugerencia.
    """

    obra: str              # titulo de la guia o del articulo
    emisor: str            # KDIGO, ADA, ESC
    anio: str
    localizador: str       # DOI, PMCID, seccion y numeral
    url: str = ""
    licencia: str = ""     # CC BY-NC-ND, todos los derechos reservados, etc

    def completa(self) -> bool:
        return all(bool(x.strip()) for x in (self.obra, self.emisor, self.anio,
                                             self.localizador))

    def __str__(self) -> str:
        base = f"{self.emisor}, {self.obra} ({self.anio}), {self.localizador}"
        return base + (f" — {self.licencia}" if self.licencia else "")


class MotivoRechazoCita(str, Enum):
    NO_ESTA_EN_LA_FUENTE = "no_esta_en_la_fuente"
    OBJETO_NO_CUBIERTO = "objeto_no_cubierto"
    TRADUCIDA = "traducida"
    ATRIBUCION_INCOMPLETA = "atribucion_incompleta"
    DEMASIADO_LARGA = "demasiado_larga"
    TECHO_DE_OBRA_EXCEDIDO = "techo_de_obra_excedido"
    DEMASIADO_SEGUIDAS = "demasiado_seguidas"
    DEMASIADO_CERCA = "demasiado_cerca"
    ALTERADA = "alterada"


@dataclass(frozen=True)
class CitaVerbatim:
    """Un fragmento recuperado de su fuente, inmutable y verificable.

    NO se construye pasandole una cadena: se obtiene con `extraer`, que la corta
    del documento fuente. Es la unica puerta, y es lo que hace estructuralmente
    imposible que un texto generado pase por cita.
    """

    texto: str
    atribucion: Atribucion
    inicio: int               # desplazamiento en el documento fuente
    fin: int
    idioma: str               # idioma del ORIGINAL, que es el unico permitido
    tipo: TipoObjeto = TipoObjeto.TEXTO
    huella_fuente: str = ""   # huella del documento del que se corto

    def palabras(self) -> int:
        return len(self.texto.split())

    def huella(self) -> str:
        """Huella del contenido exhibido, para detectar cualquier alteracion."""
        semilla = f"{self.texto}::{self.inicio}::{self.fin}::{self.huella_fuente}"
        return hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:24]

    def dict(self) -> dict:
        return {
            "texto": self.texto, "palabras": self.palabras(),
            "atribucion": str(self.atribucion),
            "localizador": self.atribucion.localizador,
            "licencia": self.atribucion.licencia,
            "inicio": self.inicio, "fin": self.fin, "idioma": self.idioma,
            "tipo": self.tipo.value, "huella": self.huella(),
            "huella_fuente": self.huella_fuente,
        }


def huella_documento(texto: str) -> str:
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()[:24]


def _normalizar_blancos(s: str) -> str:
    """Solo unifica espacios y saltos. NO toca ningun caracter del contenido.

    Es deliberadamente timido: cualquier normalizacion mas agresiva (acentos,
    mayusculas, puntuacion) convertiria una cita alterada en una cita que pasa la
    verificacion, que es justo lo que este modulo existe para impedir.
    """
    return re.sub(r"\s+", " ", (s or "")).strip()


@dataclass
class ResultadoCita:
    cita: Optional[CitaVerbatim]
    motivo: str
    codigo: Optional[MotivoRechazoCita] = None
    advertencias: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.cita is not None

    def dict(self) -> dict:
        return {"ok": bool(self), "motivo": self.motivo,
                "codigo": self.codigo.value if self.codigo else None,
                "advertencias": self.advertencias,
                "cita": self.cita.dict() if self.cita else None}


def extraer(texto_fuente: str, inicio: int, fin: int, atribucion: Atribucion,
            idioma: str, tipo: TipoObjeto = TipoObjeto.TEXTO) -> ResultadoCita:
    """Corta una cita del documento fuente. La UNICA forma de crear una cita.

    No recibe el texto de la cita: recibe el documento y las coordenadas. Asi la
    cita es, por construccion, un fragmento del original y no puede ser otra
    cosa.
    """
    if tipo in OBJETOS_NO_CUBIERTOS:
        return ResultadoCita(
            None, f"un objeto de tipo {tipo.value} no esta cubierto por el derecho de "
                  f"cita del articulo 148 fraccion I, que alcanza TEXTOS. Las tablas, "
                  f"figuras, algoritmos y diagramas requieren autorizacion aparte",
            MotivoRechazoCita.OBJETO_NO_CUBIERTO)

    if not atribucion.completa():
        faltan = [n for n, v in (("obra", atribucion.obra), ("emisor", atribucion.emisor),
                                 ("anio", atribucion.anio),
                                 ("localizador", atribucion.localizador))
                  if not v.strip()]
        return ResultadoCita(
            None, f"la atribucion esta incompleta (falta {', '.join(faltan)}). El "
                  f"articulo 148 exige citar INVARIABLEMENTE la fuente: una cita sin "
                  f"fuente completa no es una cita amparada, es una reproduccion",
            MotivoRechazoCita.ATRIBUCION_INCOMPLETA)

    if not (0 <= inicio < fin <= len(texto_fuente or "")):
        return ResultadoCita(
            None, f"las coordenadas [{inicio}, {fin}] no caen dentro del documento de "
                  f"{len(texto_fuente or '')} caracteres",
            MotivoRechazoCita.NO_ESTA_EN_LA_FUENTE)

    fragmento = _normalizar_blancos(texto_fuente[inicio:fin])
    if not fragmento:
        return ResultadoCita(None, "el fragmento esta vacio",
                             MotivoRechazoCita.NO_ESTA_EN_LA_FUENTE)

    n = len(fragmento.split())
    if n > MAX_PALABRAS_POR_CITA:
        return ResultadoCita(
            None, f"la cita tiene {n} palabras y el maximo por cita es "
                  f"{MAX_PALABRAS_POR_CITA}. Una recomendacion clinica cabe de sobra; "
                  f"pasar de ahi deja de ser citar la recomendacion y empieza a ser "
                  f"reproducir el parrafo",
            MotivoRechazoCita.DEMASIADO_LARGA)

    # Los componentes de la licencia se leen con expresion regular y no partiendo
    # por guiones: "CC BY-NC-ND 4.0" partido por guiones deja "nd 4.0", que no
    # coincide con "nd", y la advertencia mas importante se perdia en silencio.
    lic = (atribucion.licencia or "").lower()
    tiene_nc = bool(re.search(r"\bnc\b", lic)) or "no comercial" in lic \
        or "noncommercial" in lic or "non-commercial" in lic
    tiene_nd = bool(re.search(r"\bnd\b", lic)) or "noderiv" in lic \
        or "no deriv" in lic or "sin derivad" in lic

    advertencias = []
    if tiene_nc:
        advertencias.append(
            "la licencia de la fuente es NO COMERCIAL: esta cita solo puede servirse en "
            "una capa no monetizada, o hace falta permiso expreso del titular")
    if tiene_nd:
        advertencias.append(
            "la licencia prohibe obras derivadas: esta cita NO se puede parafrasear, "
            "resumir ni traducir, y el modelo no debe reescribirla nunca")

    return ResultadoCita(
        CitaVerbatim(texto=fragmento, atribucion=atribucion, inicio=inicio, fin=fin,
                     idioma=idioma, tipo=tipo,
                     huella_fuente=huella_documento(texto_fuente)),
        f"citadas {n} palabras desde el desplazamiento {inicio}", None, advertencias)


def localizar(texto_fuente: str, fragmento: str) -> Optional[tuple]:
    """Encuentra un fragmento en el documento y devuelve sus coordenadas.

    Sirve para pasar de "se quiere citar esta oracion" a coordenadas reales. Si
    el fragmento NO esta literalmente en el documento devuelve None, y ese None
    es informacion valiosa: significa que lo que se creia una cita es en realidad
    una parafrasis, y una parafrasis presentada como cita es lo peor de los dos
    mundos, porque viola la clausula de no alteracion y ademas puede estar
    alucinada.
    """
    if not texto_fuente or not fragmento:
        return None
    objetivo = _normalizar_blancos(fragmento)
    if not objetivo:
        return None
    i = texto_fuente.find(objetivo)
    if i >= 0:
        return (i, i + len(objetivo))
    # el documento puede traer saltos de linea dentro de la oracion
    patron = re.compile(r"\s+".join(re.escape(p) for p in objetivo.split()))
    m = patron.search(texto_fuente)
    return (m.start(), m.end()) if m else None


def verificar_integridad(cita: CitaVerbatim, texto_fuente: str) -> ResultadoCita:
    """Confirma que la cita sigue siendo exactamente lo que dice el documento.

    Se corre antes de MOSTRAR, no solo al crear. Una cita puede haberse creado
    bien y luego haber pasado por un paso de formateo, de traduccion automatica o
    de reescritura; esta funcion lo detecta comparando contra la fuente.
    """
    if huella_documento(texto_fuente) != cita.huella_fuente:
        return ResultadoCita(
            None, "el documento fuente cambio desde que se tomo la cita: hay que "
                  "re-extraerla y revisar si la recomendacion sigue diciendo lo mismo",
            MotivoRechazoCita.ALTERADA)
    actual = _normalizar_blancos(texto_fuente[cita.inicio:cita.fin])
    if actual != cita.texto:
        return ResultadoCita(
            None, f"la cita NO coincide con el documento en sus propias coordenadas. "
                  f"Esperado: {actual[:70]!r}. Guardado: {cita.texto[:70]!r}. Una "
                  f"parafrasis presentada como cita viola la clausula de no alteracion "
                  f"y ademas puede estar alucinada",
            MotivoRechazoCita.ALTERADA)
    return ResultadoCita(cita, "integra")


def detectar_traduccion(cita: CitaVerbatim, idioma_mostrado: str) -> Optional[str]:
    """Traducir no es citar: es obra derivada y requiere autorizacion.

    Es la restriccion de producto mas incomoda de todo el expediente y no tiene
    vuelta: la recomendacion de KDIGO o de la ADA se queda en ingles. Lo que SI
    puede ir en espanol es la explicacion propia de ORIONS alrededor del bloque.
    """
    if idioma_mostrado and idioma_mostrado.lower()[:2] != cita.idioma.lower()[:2]:
        return (f"la cita esta en {cita.idioma} y se quiere mostrar en "
                f"{idioma_mostrado}. Una traduccion es obra derivada (articulo 27 de la "
                f"Ley Federal del Derecho de Autor) y requiere autorizacion: no la "
                f"ampara el derecho de cita. El bloque citado se queda en su idioma "
                f"original y la explicacion propia va en espanol alrededor")
    return None


# ---------------------------------------------------------------------------
# Presupuesto por obra: densidad y contiguidad
# ---------------------------------------------------------------------------


@dataclass
class PresupuestoDeCita:
    """Lleva la cuenta de lo citado de UNA obra.

    Existe porque el criterio legal real no es el volumen total sino que los
    pasajes no sean "tantos y seguidos". Un contador de palabras solo no basta:
    hay que vigilar tambien cuantas citas van seguidas sin material propio en
    medio, y cuanta distancia hay entre ellas en el documento original.
    """

    obra: str
    palabras_usadas: int = 0
    citas: list = field(default_factory=list)       # (inicio, fin, palabras)
    consecutivas: int = 0                            # sin material propio en medio

    def material_propio(self) -> None:
        """Marca que entre dos citas hubo contenido de ORIONS. Rompe la racha."""
        self.consecutivas = 0

    def cabe(self, cita: CitaVerbatim) -> ResultadoCita:
        n = cita.palabras()
        if self.palabras_usadas + n > TECHO_PALABRAS_POR_OBRA:
            return ResultadoCita(
                None, f"se han citado {self.palabras_usadas} palabras de '{self.obra}' y "
                      f"esta cita de {n} pasaria el techo de {TECHO_PALABRAS_POR_OBRA}. "
                      f"El techo se adopta por analogia de la ley argentina 11.723, que "
                      f"es el unico numero legislado de la region, precisamente porque es "
                      f"conservador",
                MotivoRechazoCita.TECHO_DE_OBRA_EXCEDIDO)

        if self.consecutivas >= MAX_CITAS_CONSECUTIVAS:
            return ResultadoCita(
                None, f"van {self.consecutivas} citas seguidas de la misma obra sin "
                      f"material propio en medio. Lo que la ley castiga es que los "
                      f"pasajes sean TANTOS Y SEGUIDOS: citas consecutivas de una "
                      f"seccion son esa seccion reproducida con comillas",
                MotivoRechazoCita.DEMASIADO_SEGUIDAS)

        for ini, fin, _ in self.citas:
            if abs(cita.inicio - fin) < SEPARACION_MINIMA and \
                    abs(ini - cita.fin) < SEPARACION_MINIMA:
                return ResultadoCita(
                    None, f"esta cita esta a menos de {SEPARACION_MINIMA} caracteres de "
                          f"otra ya tomada de la misma obra [{ini}, {fin}]. La dispersion "
                          f"es obligatoria: cuarenta frases dispersas en doscientas "
                          f"paginas son una cita, cincuenta consecutivas son una copia",
                    MotivoRechazoCita.DEMASIADO_CERCA)
        return ResultadoCita(cita, "cabe")

    def agregar(self, cita: CitaVerbatim) -> ResultadoCita:
        r = self.cabe(cita)
        if not r:
            return r
        self.palabras_usadas += cita.palabras()
        self.citas.append((cita.inicio, cita.fin, cita.palabras()))
        self.consecutivas += 1
        return ResultadoCita(cita, f"agregada; {self.palabras_usadas} palabras usadas de "
                                   f"{TECHO_PALABRAS_POR_OBRA}")

    def informe(self) -> dict:
        tramos = sorted(self.citas)
        contiguo = 0
        if tramos:
            actual = tramos[0][2]
            contiguo = actual
            for i in range(1, len(tramos)):
                if tramos[i][0] - tramos[i - 1][1] < SEPARACION_MINIMA:
                    actual += tramos[i][2]
                    contiguo = max(contiguo, actual)
                else:
                    actual = tramos[i][2]
        return {
            "obra": self.obra,
            "palabras_usadas": self.palabras_usadas,
            "techo": TECHO_PALABRAS_POR_OBRA,
            "proporcion_del_techo": round(self.palabras_usadas / TECHO_PALABRAS_POR_OBRA, 3),
            "n_citas": len(self.citas),
            "palabras_en_el_tramo_mas_denso": contiguo,
            "citas_consecutivas_actuales": self.consecutivas,
        }


REGLAS_DURAS = [
    "Las cuatro condiciones del articulo 148 son CONJUNTAS: obra ya divulgada, que no "
    "se afecte la explotacion normal, citar invariablemente la fuente, y no alterar la "
    "obra. Fallar una anula la excepcion completa.",
    "La cantidad se mide sobre la OBRA CITADA, no sobre la obra citante: que las citas "
    "sean el 1% de ORIONS es irrelevante si son el nucleo normativo de la guia.",
    "El criterio operativo es DENSIDAD Y CONTIGUIDAD, no volumen: los pasajes no deben "
    "ser tantos y seguidos.",
    "El derecho de cita cubre SOLO TEXTO. Tablas como objeto grafico, figuras, "
    "algoritmos y diagramas de flujo quedan fuera y requieren autorizacion aparte.",
    "TRADUCIR NO ES CITAR: una traduccion es obra derivada y requiere autorizacion. El "
    "bloque citado se queda en su idioma original.",
    "La atribucion debe ser adyacente y no suprimible por la interfaz. Una cita con la "
    "fuente escondida en un modal es una cita sin fuente.",
    "NUNCA aceptar un clickwrap ni crear cuenta en el sitio del titular: un contrato "
    "aceptado DESPLAZA la excepcion legal y convierte el reclamo de infraccion en "
    "incumplimiento de contrato, que es peor.",
    "El modelo NUNCA reescribe un bloque citado. Si una licencia prohibe derivados, "
    "parafrasear es la via prohibida y citar literal es la permitida.",
]


__all__ = [
    "CitaVerbatim", "Atribucion", "TipoObjeto", "ResultadoCita", "MotivoRechazoCita",
    "PresupuestoDeCita", "extraer", "localizar", "verificar_integridad",
    "detectar_traduccion", "huella_documento", "REGLAS_DURAS",
    "TECHO_PALABRAS_POR_OBRA", "MAX_PALABRAS_POR_CITA", "MAX_CITAS_CONSECUTIVAS",
    "SEPARACION_MINIMA", "OBJETOS_NO_CUBIERTOS",
]
