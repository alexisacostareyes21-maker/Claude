"""Compuerta de licencias para imagen. Falla cerrado.

Por que no sirve la compuerta de texto (harness/fuentes.py)
-----------------------------------------------------------
La de texto pregunta por la comercialidad antes que por nada mas, y para
imagen ese orden es el error que casi mata el caso. La prohibicion que mata
no dice "comercial", dice "publicar":

    "Free users: You may not publish any Science Figures containing BioRender
     Content, nor may you use any Science Figures containing BioRender content
     for commercial purposes."
    -- BioRender, Basic License Terms

Son DOS prohibiciones unidas por "nor", y la primera es independiente del
cobro. Regalar la plataforma no reabre el permiso. De ahi el orden de
evaluacion de este modulo, que es su decision de diseno central:

    persona identificable  ->  publicacion  ->  comercial  ->  derivadas

Las tres diferencias de fondo con el texto
------------------------------------------
1. Armar una figura compuesta ES derivar. Para un hecho de texto, ORIONS
   extrae la cifra y la reescribe con su propia voz, y la pregunta de obra
   derivada casi nunca llega a morder. Para imagen, el acto nuclear del
   producto -recortar, recolorear, TRADUCIR LAS ETIQUETAS AL ESPANOL, pegar el
   activo junto a otros- es inequivocamente obra derivada. CC BY 4.0 §1(a)
   define "Adapted Material" con las palabras "translated, altered, arranged,
   transformed". Traducir esta en el texto. Por eso ND se rechaza en AMBAS
   capas, no solo en la comercial, y por eso fue_modificado es True por
   defecto: ORIONS es una plataforma mexicana, el 100% de sus figuras llevara
   rotulos en espanol.

2. Una imagen se SIRVE como archivo que el navegador del estudiante descarga,
   asi que mostrarla es otorgar un derecho aguas abajo. Una licencia
   "non-sublicensable" no tiene nada que transmitir. Lo que hace funcionar a
   Creative Commons aqui no es que sea sublicenciable -CC BY 4.0 §2(a)(1) dice
   expresamente "non-sublicensable"- sino que opera por concesion DIRECTA del
   licenciante a cada receptor. De ahi la regla estructural: solo entran
   licencias con concesion directa. Toda licencia propietaria por cuenta o por
   plan queda fuera por construccion, sin necesidad de leer si permite "uso
   educativo".

3. El consentimiento del paciente es un carril legal APARTE y no viaja con la
   licencia. Una foto con CC BY impecable puede ser ilegal de publicar.
   CC BY 4.0 §2(b)(1): "Moral rights, such as the right of integrity, are not
   licensed under this Public License, nor are publicity, privacy, and/or
   other similar personality rights". CC0 1.0 §4(c) va mas lejos: "Affirmer
   disclaims responsibility for obtaining any necessary consents". El fotografo
   licencia lo unico que puede licenciar, su copyright; no puede ceder lo que
   no le pertenece. Por eso persona_identificable se evalua ANTES que la
   licencia y su rechazo no lo levanta ninguna licencia.

Nivel de verificacion
---------------------
Cada entrada del catalogo declara COMO se verifico. La salida HTTPS de este
contenedor esta cerrada para los hosts de los proveedores, asi que solo se
leyeron al primario los que viven en repositorios alcanzables. Lo demas son
transcripciones concordantes entre agentes independientes: mas fuerte que la
memoria y mas debil que un primario leido. La distincion esta en el codigo
porque es la unica forma de que no se olvide.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Licencias admisibles
# ---------------------------------------------------------------------------

# Lista BLANCA por cadena exacta. Solo entran licencias que conceden el derecho
# DIRECTAMENTE a cada receptor, porque ORiONS sirve el archivo al estudiante y
# no puede transmitir un derecho que no tiene facultad de sublicenciar.
PERMITIDAS = {
    "CC0",
    "CC BY",
    "DOMINIO PUBLICO",   # declarado por la fuente, con su base legal registrada
    "MIT",
    "APACHE-2.0",
}

# Permiten comercio pero NO sirven, y conviene nombrarlas para que el motivo
# del rechazo sea preciso en vez de generico.
COMERCIAL_PERO_INSERVIBLE = {
    "CC BY-SA": ("ShareAlike: la figura compuesta nacería bajo los mismos "
                 "terminos y cualquier estudiante podria redistribuir el banco "
                 "legalmente. No es infraccion, es destruccion del activo"),
    "CC BY-ND": ("NoDerivatives: traducir los rotulos al espanol ya es derivar, "
                 "y armar una figura compuesta es 'build upon'"),
    "BSD-3-CLAUSE": ("en la practica son logotipos corporativos: la marca no "
                     "viene licenciada y la clausula 3 prohibe usar el nombre "
                     "para promocionar"),
}

NO_COMERCIAL = {
    "CC BY-NC": "prohibe el uso comercial",
    "CC BY-NC-SA": "prohibe el uso comercial y ademas contagia",
    "CC BY-NC-ND": "prohibe el uso comercial y los derivados",
}

# Regimen distinto del ToS y de Creative Commons: un contrato firmado. Es el
# que encuentra primero quien busca "chest x-ray dataset", y es rojo absoluto
# por contrato, no por derecho de autor.
LICENCIAS_DE_DATASET = {
    "PHYSIONET CREDENTIALED": ("DUA firmado que prohibe compartir los datos y "
                               "restringe el uso a investigacion cientifica "
                               "(MIMIC-CXR, MIMIC-CXR-JPG)"),
    "RESEARCH USE ONLY": ("licencia de competencia o de investigacion: no "
                          "autoriza producto (CheXpert, EyePACS, los de Kaggle)"),
}


class Declarante(str, Enum):
    """Quien declara la licencia. Donde discrepen, gana el licenciante."""
    LICENCIANTE = "licenciante"
    AGREGADOR = "agregador"


class MotivoImagen(str, Enum):
    PERSONA_IDENTIFICABLE = "persona_identificable_sin_consentimiento"
    NO_PERMITE_PUBLICAR = "no_permite_publicacion"
    SIN_CONCESION_DIRECTA = "licencia_sin_concesion_directa_al_receptor"
    NO_COMERCIAL = "no_permite_uso_comercial"
    SIN_DERIVADAS = "prohibe_obras_derivadas"
    SHARE_ALIKE = "share_alike_contagioso"
    MARCA_DE_AGUA = "marca_de_agua_obligatoria_en_figura_compuesta"
    SIN_VERSION = "licencia_sin_version_declarada"
    LICENCIA_DESCONOCIDA = "licencia_desconocida"
    LICENCIA_DE_DATASET = "licencia_de_dataset_o_dua"
    LOGOTIPO_O_MARCA = "logotipo_o_marca_no_licenciada"
    SIN_PROCEDENCIA = "procedencia_incompleta"
    SIN_TEXTO_ALTERNATIVO = "sin_texto_alternativo"
    SIN_REVISION_CLINICA = "sin_revision_clinica"


class Capa(str, Enum):
    """Las dos capas de producto. La respuesta cambia entre ellas."""
    GRATUITA = "gratuita"        # acceso libre, sin publicidad ni suscripcion
    COMERCIAL = "comercial"      # suscripcion o cualquier monetizacion


class Uso(str, Enum):
    INTACTA = "intacta"          # se muestra tal cual la entrega la fuente
    COMPUESTA = "compuesta"      # entra en una figura junto a otros elementos


@dataclass
class Dictamen:
    admisible: bool
    motivo: str
    codigo: Optional[MotivoImagen] = None
    advertencias: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.admisible

    def dict(self) -> dict:
        d = asdict(self)
        d["codigo"] = self.codigo.value if self.codigo else None
        return d


@dataclass
class Activo:
    """Un activo de imagen con su procedencia completa.

    La procedencia no es metadato decorativo: es la unica defensa si el titular
    cambia sus terminos o manda un aviso. La familia CC se concede como
    irrevocable, asi que la prueba de EN QUE ESTADO estaba la licencia al
    descargar es lo que vale.
    """

    clave: str
    fuente: str                          # clave del CATALOGO
    licencia_literal: str                # tal como la declara la fuente, sin normalizar
    url_entrada: str
    fecha_descarga: str
    version: Optional[str] = None        # None => cuarentena, no se publica
    declarada_por: Declarante = Declarante.LICENCIANTE
    sha_indice: Optional[str] = None     # cuando viene de un repositorio
    autor: str = ""
    url_autor: str = ""

    # Permisos. permite_publicacion es SEPARADO de permite_comercial a
    # proposito: confundirlos es el error de BioRender.
    permite_publicacion: bool = False
    permite_comercial: bool = False
    permite_derivadas: bool = False
    share_alike: bool = False
    marca_de_agua_obligatoria: bool = False
    es_logotipo_o_marca: bool = False

    # Carril aparte del derecho de autor.
    persona_identificable: bool = False
    consentimiento_para_orions: bool = False

    # fue_modificado arranca en True porque traducir los rotulos al espanol ya
    # es modificar, y en ORIONS eso pasa siempre. El default importa: si
    # arrancara en False, el generador de creditos escribiria "provided by"
    # donde corresponde "adapted from", que es incumplimiento de
    # CC BY 4.0 §3(a)(1)(B), "indicate if You modified the Licensed Material".
    fue_modificado: bool = True

    alt: str = ""                        # vacio => no publica
    revisor_clinico: str = ""            # vacio => no publica

    def licencia(self) -> str:
        """La cadena normalizada para comparar contra las listas."""
        return self.licencia_literal.strip().upper()

    def procedencia_completa(self) -> bool:
        return bool(self.fuente and self.url_entrada and self.fecha_descarga
                    and self.licencia_literal)

    def atribucion(self, plantilla_intacta: str, plantilla_adaptada: str) -> str:
        """El credito, en la forma que corresponde al estado del activo."""
        base = plantilla_adaptada if self.fue_modificado else plantilla_intacta
        if self.autor:
            base = base.replace("{autor}", self.autor)
        if self.url_autor:
            base = base.replace("{url_autor}", self.url_autor)
        return base.replace("{url}", self.url_entrada).replace(
            "{licencia}", self.licencia_literal)


def admisible(activo: Activo, capa: Capa = Capa.GRATUITA,
              uso: Uso = Uso.COMPUESTA) -> Dictamen:
    """Decide si un activo de imagen puede mostrarse.

    El ORDEN de las reglas es la decision de diseno, igual que en
    harness/atestiguar.py: primero lo que descalifica sin apelacion, y solo
    despues lo que depende de la capa.
    """
    adv: list[str] = []
    lic = activo.licencia()

    # --- Regla 0: el carril que no es de derecho de autor. ------------------
    # Se evalua primero y ninguna licencia lo levanta. Identificable incluye
    # rostro, region ocular, iris, tatuajes, joyeria o ropa distintiva, cicatriz
    # o lesion caracteristica, fondo reconocible, e identificadores quemados en
    # una radiografia o presentes en los metadatos DICOM.
    if activo.persona_identificable and not activo.consentimiento_para_orions:
        return Dictamen(
            False,
            ("persona identificable sin consentimiento otorgado a ORIONS. El "
             "consentimiento que el paciente dio a otra publicacion NO viaja: "
             "nueva finalidad, nuevo consentimiento. Ninguna licencia lo "
             "levanta porque el fotografo no puede ceder lo que no le pertenece"),
            MotivoImagen.PERSONA_IDENTIFICABLE,
        )
    if activo.persona_identificable:
        adv.append("persona identificable CON consentimiento: archivar el "
                   "documento firmado y verificar que cubra reuso por ORIONS, "
                   "no solo la publicacion original")

    # --- Regla 1: procedencia. Sin ella no hay defensa posible. -------------
    if not activo.procedencia_completa():
        return Dictamen(
            False,
            "procedencia incompleta: falta fuente, URL de entrada, fecha de "
            "descarga o la cadena literal de licencia",
            MotivoImagen.SIN_PROCEDENCIA,
        )

    # --- Regla 2: licencias que son contratos, no licencias. ---------------
    if lic in LICENCIAS_DE_DATASET:
        return Dictamen(False,
                        f"licencia de dataset: {LICENCIAS_DE_DATASET[lic]}",
                        MotivoImagen.LICENCIA_DE_DATASET)

    # --- Regla 3: la publicacion, ANTES que el dinero. ---------------------
    if not activo.permite_publicacion:
        return Dictamen(
            False,
            ("la licencia no permite PUBLICAR, que es independiente de cobrar. "
             "Mostrar la figura en una web abierta a estudiantes es publicacion "
             "y distribucion, no 'presentacion educativa'. Regalar la "
             "plataforma no reabre el permiso"),
            MotivoImagen.NO_PERMITE_PUBLICAR,
        )

    # --- Regla 4: concesion directa al receptor. ---------------------------
    # ORIONS sirve el archivo, asi que otorga un derecho aguas abajo. Una
    # licencia por cuenta o por plan no tiene nada que transmitir.
    if lic not in PERMITIDAS:
        if lic in COMERCIAL_PERO_INSERVIBLE:
            codigo = (MotivoImagen.SHARE_ALIKE if "SA" in lic.split("-")
                      else MotivoImagen.SIN_DERIVADAS)
            return Dictamen(False,
                            f"{activo.licencia_literal}: "
                            f"{COMERCIAL_PERO_INSERVIBLE[lic]}",
                            codigo)
        if lic in NO_COMERCIAL:
            # NC bloquea la capa comercial siempre; y si ademas trae ND,
            # bloquea las dos, porque traducir ya es derivar.
            if "ND" in lic.split("-"):
                return Dictamen(False,
                                f"{activo.licencia_literal}: el ND mata las dos "
                                f"capas, porque traducir los rotulos al espanol "
                                f"ya es obra derivada y armar la figura es "
                                f"'build upon'",
                                MotivoImagen.SIN_DERIVADAS)
            if capa is Capa.COMERCIAL:
                return Dictamen(False,
                                f"{activo.licencia_literal}: "
                                f"{NO_COMERCIAL[lic]}",
                                MotivoImagen.NO_COMERCIAL)
            adv.append(f"{activo.licencia_literal} solo sirve en capa gratuita: "
                       f"si ORIONS monetiza, este activo hay que retirarlo, y "
                       f"la version ya publicada no se des-licencia quitandolo "
                       f"despues")
        else:
            return Dictamen(
                False,
                f"licencia no reconocida: {activo.licencia_literal!r}. La lista "
                f"es blanca y la comparacion es de cadena exacta, asi que todo "
                f"valor no visto antes queda fuera por defecto",
                MotivoImagen.LICENCIA_DESCONOCIDA,
            )

    # --- Regla 5: sin version declarada, cuarentena. -----------------------
    # Las obligaciones cambian entre versiones: CC BY 3.0 §4(a) prohibe
    # sublicenciar y §7(a) termina la licencia al incumplir sin el periodo de
    # subsanacion de 30 dias que §6(b)(1) de la 4.0 si concede.
    if lic.startswith("CC BY") and not activo.version:
        return Dictamen(
            False,
            "la fuente no declara version de la licencia. No se publica, o se "
            "publica bajo la obligacion mas exigente de las versiones "
            "candidatas y se registra que la fuente no la declaro",
            MotivoImagen.SIN_VERSION,
        )

    # --- Regla 6: marca de agua. Es condicion sobre el PIXEL. --------------
    # Ninguna linea de credito la satisface: viaja dentro del archivo y es
    # acumulativa con la atribucion, no alternativa.
    if activo.marca_de_agua_obligatoria:
        if uso is Uso.COMPUESTA or activo.fue_modificado:
            return Dictamen(
                False,
                "marca de agua obligatoria: el activo solo puede mostrarse "
                "INTACTO, con la marca visible. No entra en figura compuesta ni "
                "admite recorte, recoloreado ni traduccion de rotulos",
                MotivoImagen.MARCA_DE_AGUA,
            )
        adv.append("marca de agua obligatoria: excluir este activo del paso de "
                   "reencodeo o reescalado, porque un recorte automatico de "
                   "margenes puede cortarla sin que nadie lo decida")

    # --- Regla 7: derivadas. En ORIONS siempre se deriva. ------------------
    if activo.fue_modificado and not activo.permite_derivadas:
        return Dictamen(False,
                        "el activo fue modificado y la licencia no permite "
                        "obras derivadas",
                        MotivoImagen.SIN_DERIVADAS)
    if activo.share_alike:
        return Dictamen(False,
                        "ShareAlike: la figura compuesta nacería bajo los "
                        "mismos terminos y el NC o el SA se le queda pegado "
                        "para siempre",
                        MotivoImagen.SHARE_ALIKE)

    # --- Regla 8: marca. Sobrevive al dominio publico. ---------------------
    if activo.es_logotipo_o_marca:
        return Dictamen(False,
                        "logotipo o marca: el dominio publico libera el "
                        "copyright, no autoriza usar la marca ni dar a "
                        "entender que el titular avala el producto",
                        MotivoImagen.LOGOTIPO_O_MARCA)

    # --- Regla 9: comercial, por fin. --------------------------------------
    if capa is Capa.COMERCIAL and not activo.permite_comercial:
        return Dictamen(False,
                        "la licencia no permite uso comercial",
                        MotivoImagen.NO_COMERCIAL)

    # --- Regla 10: lo que no es licencia y tampoco es opcional. ------------
    # Nada se publica con la licencia aprobada y la clinica en blanco. Y un
    # banco de figuras sin texto alternativo es invisible para un estudiante
    # con baja vision.
    if not activo.alt.strip():
        return Dictamen(False,
                        "sin texto alternativo: la compuerta no publica una "
                        "figura que un estudiante con baja vision no puede leer",
                        MotivoImagen.SIN_TEXTO_ALTERNATIVO)
    if not activo.revisor_clinico.strip():
        return Dictamen(False,
                        "sin revision clinica: la compuerta de licencia y la "
                        "compuerta clinica son distintas, y la licencia "
                        "aprobada no suple el cotejo de nomenclatura",
                        MotivoImagen.SIN_REVISION_CLINICA)

    if activo.declarada_por is Declarante.AGREGADOR:
        adv.append("licencia declarada por un agregador, que no audita la "
                   "cadena de titularidad: preferir el licenciante aguas arriba "
                   "cuando el activo exista alli, y acreditar con la linea que "
                   "el licenciante recomienda")

    return Dictamen(True, "admisible", None, adv)


# ---------------------------------------------------------------------------
# Restricciones que ORIONS se impone a si mismo
# ---------------------------------------------------------------------------

def restricciones_aguas_abajo(tiene_drm: bool, tos_prohibe_descarga: bool,
                              activos_cc: int) -> list[str]:
    """La trampa que va en direccion contraria: lo que ORIONS IMPONE.

    CC BY 4.0 §2(a)(5)(B): "No downstream restrictions. You may not offer or
    impose any additional or different terms or conditions on, or apply any
    Effective Technological Measures to, the Licensed Material if doing so
    restricts exercise of the Licensed Rights by any recipient."

    El ToS tipico de una plataforma de suscripcion ("todo el contenido es
    propiedad de ORIONS, prohibida su reproduccion") y el DRM o anti-clic-
    derecho aplicados encima de los iconos CC son exactamente los terminos
    adicionales y las Medidas Tecnologicas Efectivas que la licencia prohibe.
    Es ORIONS incumpliendo la licencia del icono que esta usando legalmente.
    """
    faltas = []
    if activos_cc and tiene_drm:
        faltas.append(
            "DRM o medidas anti-descarga sobre activos CC: son 'Effective "
            "Technological Measures' prohibidas por CC BY 4.0 §2(a)(5)(B). Si "
            "hay que proteger tecnicamente una figura, construirla solo con "
            "CC0, dominio publico y arte propio")
    if activos_cc and tos_prohibe_descarga:
        faltas.append(
            "el ToS impone terminos adicionales sobre material licenciado. "
            "Hace falta un carve-out expreso: los activos de terceros bajo "
            "licencia abierta identificados en la pagina de creditos se rigen "
            "por su propia licencia y los usuarios conservan los derechos que "
            "esa licencia les concede")
    return faltas


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

class Verificacion(str, Enum):
    PRIMARIO_LEIDO = "primario_leido"
    INDICE_CONCORDANTE = "indice_de_busqueda_concordante"
    NO_VERIFICADO = "no_verificado"


@dataclass
class FuenteImagen:
    clave: str
    nombre: str
    licencia: str
    verificacion: Verificacion
    capa_gratuita: str                   # verde | ambar | rojo
    capa_comercial: str
    hallazgo: str
    atribucion_intacta: str = ""
    atribucion_adaptada: str = ""
    accion: str = ""
    clausula_verbatim: str = ""
    pendiente: list[str] = field(default_factory=list)


CATALOGO: dict[str, FuenteImagen] = {
    "togotv": FuenteImagen(
        clave="togotv",
        nombre="DBCLS TogoTV / Togo Picture Gallery",
        licencia="CC BY 4.0",
        verificacion=Verificacion.PRIMARIO_LEIDO,
        capa_gratuita="verde", capa_comercial="verde",
        hallazgo=("la fuente mejor verificada del expediente: su clausula se leyo en el "
                  "repositorio oficial del sitio (github.com/dbcls/togotv, master, HEAD "
                  "55b774e, clave picture_liscense_text en static/json/en.json; estable "
                  "desde c28287c, 2023-10-21). Comercial expreso, derivadas expresas, "
                  "figuras compuestas nombradas literalmente, ubicacion del credito LIBRE, "
                  "ninguna clausula asesina, cero retencion. Entrega svg/png/AI editables. "
                  "Es ademas el upstream del 22.6% de Bioicons (634 iconos), asi que usarlo "
                  "directo elimina al intermediario que no garantiza titularidad"),
        clausula_verbatim=("it can be freely reprinted, modified, and reused (including "
                           "secondary use for commercial purposes) without permission, "
                           "provided that you 'give proper credit (source), provide a link "
                           "to the license, and indicate any changes'"),
        atribucion_intacta=("The image of {clave} is from TogoTV ((c) 2016 DBCLS TogoTV, "
                            "CC-BY-4.0 https://creativecommons.org/licenses/by/4.0/)"),
        atribucion_adaptada=("Adaptado de TogoTV ((c) 2016 DBCLS TogoTV, CC-BY-4.0 "
                             "https://creativecommons.org/licenses/by/4.0/), con rotulos "
                             "traducidos al espanol"),
        accion="PRIMERA FUENTE del nucleo. Anatomico y medico, no solo biologia molecular",
        pendiente=["el texto rector es el japones (ja.json) y no se leyo verbatim ni se "
                   "comparo con en.json",
                   "picture_liscense_text prueba el aviso que el sitio renderiza, no la "
                   "titularidad de DBCLS sobre cada imagen",
                   "Japon no tiene derecho sui generis de base de datos pero si copyright "
                   "de compilacion (art. 12bis) y un derecho de integridad fuerte e "
                   "irrenunciable (art. 20)"],
    ),
    "servier": FuenteImagen(
        clave="servier",
        nombre="SMART Servier Medical Art",
        licencia="CC BY 4.0",
        verificacion=Verificacion.INDICE_CONCORDANTE,
        capa_gratuita="verde", capa_comercial="verde",
        hallazgo=("la UNICA fuente con permiso comercial PRE-CONCEDIDO en pagina oficial "
                  "para el caso exacto de ORIONS. A la pregunta de curso de pago o "
                  "plataforma de suscripcion responde que si. Declara que no emite cartas "
                  "de permiso porque CC BY 4.0 ya ES el permiso: no hay a quien escribirle. "
                  "3,000+ ilustraciones. Cero retencion: es biblioteca de descarga, no "
                  "editor en la nube"),
        clausula_verbatim="Yes, that's fine - as long as you provide the correct attribution",
        atribucion_intacta=("Image(s) provided by Servier Medical Art "
                            "(https://smart.servier.com), licensed under CC BY 4.0 "
                            "(https://creativecommons.org/licenses/by/4.0/)"),
        atribucion_adaptada=("Image adapted from Servier Medical Art "
                             "(https://smart.servier.com/), licensed under CC BY 4.0"),
        accion=("CABALLO DE BATALLA por cobertura. Dos limites: su FAQ permite la app "
                "'as long as it's not marketed as a standalone image library or "
                "collection' y su ToS excluye 'databases' de la licencia, asi que ORIONS "
                "usa ilustraciones SELECCIONADAS dentro de sus figuras y NO publica una "
                "pantalla navegable del acervo. Y jamas el nombre ni el logo de Servier en "
                "la interfaz: es farmaceutica y ORIONS ensena terapeutica"),
        pendiente=["conflicto de version real: Bioicons etiqueta sus 1,374 iconos de "
                   "Servier como cc-by-3.0 mientras las paginas vigentes dicen 4.0",
                   "titular frances: derecho sui generis de bases de datos (Directiva "
                   "96/9/CE), pista INDEPENDIENTE del derecho de autor sobre cada "
                   "ilustracion",
                   "falta el verbatim de la FAQ y en que pagina exacta se formula"],
    ),
    "bioart": FuenteImagen(
        clave="bioart",
        nombre="NIH BIOART Source (NIAID)",
        licencia="DOMINIO PUBLICO",       # por entrada; solo se admiten las asi marcadas
        verificacion=Verificacion.INDICE_CONCORDANTE,
        capa_gratuita="verde", capa_comercial="ambar",
        hallazgo=("la concesion comercial es expresa e incondicional, y la remision a la "
                  "entrada gobierna solo la ATRIBUCION, no la comercialidad. ~30 entradas "
                  "muestreadas en el rango de IDs 20-712 muestran todas 'Licensing: Public "
                  "Domain' y 'Credit: Courtesy of NIAID'. Acervo producido en casa (NIAID "
                  "Visual & Medical Arts) y cerrado a contribuciones externas. La "
                  "restriccion que sobrevive NO es de copyright, es de MARCA, y por eso no "
                  "la levanta el dominio publico"),
        clausula_verbatim=("The illustrations and content provided on the NIH BioArt Source "
                           "are free for any use, including educational, research, "
                           "informational, and commercial purposes. Please review the "
                           "license associated with the specific entry for any attribution "
                           "requirements."),
        atribucion_intacta=("Illustration from NIAID NIH BioArt Source ({url}), "
                            "ubicada directamente debajo de la imagen"),
        atribucion_adaptada=("Adaptado de una ilustracion de NIAID NIH BioArt Source "
                             "({url}). El NIH no avala este producto"),
        accion=("ADMITIR solo entradas etiquetadas 'Public Domain'. Las 'CC-BY' van a "
                "cuarentena porque no declaran version. Nunca el logo NIH/NIAID, nunca "
                "'avalado/respaldado/en colaboracion con', linea de no-aval donde aparezca. "
                "Frontera de alcance: lo aprobado es bioart.niaid.nih.gov/bioart/###; los "
                "graficos de www.niaid.nih.gov quedan prohibidos salvo permiso expreso. No "
                "apoyarse en 17 USC 105, que es dominio publico solo en EE.UU. y no decide "
                "el estatus en Mexico: apoyarse en la concesion expresa de /terms"),
        pendiente=["30 fichas de ~712 con cero NC observados acota la prevalencia a menos "
                   "de ~10% con 95% de confianza; NO establece que no existan entradas "
                   "NC/ND. La regla 'solo Public Domain' es correcta y su justificacion "
                   "escrita debe ser 'muestra insuficiente para descartar NC'",
                   "el HTML primario de /terms no se leyo: el ambar comercial es por eso, "
                   "no por prohibicion",
                   "NIH Policy Manual 1186 (leido): los nombres y logos del NIH son solo "
                   "para uso gubernamental, con mitigacion por disclaimer"],
    ),
    "bioicons": FuenteImagen(
        clave="bioicons",
        nombre="Bioicons",
        licencia="por icono: cc-0, mit, cc-by-3.0, cc-by-4.0",
        verificacion=Verificacion.PRIMARIO_LEIDO,
        capa_gratuita="verde", capa_comercial="verde",
        hallazgo=("expone la licencia de cada activo de forma legible por maquina por dos "
                  "vias: el campo license de static/icons/icons.json y la propia ruta del "
                  "archivo (license/category/author). Censo de 2,804 entradas re-corrido por "
                  "dos agentes y coincidente al entero: cc-by-3.0 1375 (49.0%, de los cuales "
                  "1374 son Servier), cc-by-4.0 883 (31.5%, 634 de DBCLS), cc-0 465 (16.6%), "
                  "mit 39 (1.4%), cc-by-sa-4.0 35, cc-by-sa-3.0 4, bsd 3. CERO licencias no "
                  "comerciales y CERO ND. La compuerta automatica es construible"),
        clausula_verbatim=("Download on click: Simply click on the icon and the vector in svg "
                           "format will be downloaded. You can use this on the web, in "
                           "graphics software and in Microsoft Office products."),
        atribucion_adaptada=("{clave} icon by {autor} {url_autor} is licensed under "
                             "{licencia}, modificado"),
        accion=("ADMITIR con lista negra de 42 iconos (1.5%): cc-by-sa-4.0, cc-by-sa-3.0 y "
                "bsd. Nucleo sin friccion: los 504 cc-0 + mit. Congelar el SHA del commit de "
                "icons.json con la fecha de ingesta: es la unica prueba de bajo que terminos "
                "se descargo cada activo"),
        pendiente=["Bioicons NO audita la cadena de titularidad, la declara el contribuyente, "
                   "y hay al menos una etiqueta mal puesta (TensorFlow marcado bsd cuando "
                   "aguas arriba es Apache-2.0)",
                   "coste real de excluir los SA: bajo por conteo pero ALTO por utilidad "
                   "clinica, porque entre ellos estan SARS-CoV-2, dendritic_cell, "
                   "epithelial_cell, Gram_Positive/Negative y los diagramas TP/FP/TN/FN: "
                   "inmunologia, pared bacteriana y epidemiologia nuclear de ENARM. "
                   "Reponerlos con CC0, TogoTV, Servier o arte propio"],
    ),
    "propio_grafo": FuenteImagen(
        clave="propio_grafo",
        nombre="Diagramas renderizados por codigo desde el grafo de mecanismos",
        licencia="obra propia",
        verificacion=Verificacion.PRIMARIO_LEIDO,
        capa_gratuita="verde", capa_comercial="verde",
        hallazgo=("la unica ruta sin licenciante, sin cesion condicionada, sin retencion del "
                  "proveedor, sin paciente y a costo cero. Librerias verificadas al primario: "
                  "matplotlib (tipo PSF) concede 'prepare derivative works' y 'display "
                  "publicly' y su condicion de aviso recae sobre el SOFTWARE; D3 es ISC; "
                  "Graphviz es EPL-2.0 y su definicion de Distribute ('making available in "
                  "any manner that enables the transfer of a copy') significa que renderizar "
                  "en servidor y servir solo el SVG no dispara copyleft, mientras enviar "
                  "Graphviz en WASM al navegador si lo haria; ColorBrewer dentro de "
                  "matplotlib es Apache 2.0 pelado"),
        accion=("CONSTRUIR. Cubre por completo: mecanismos con propagacion de signo, "
                "cascadas, ejes hormonales, farmacodinamia y farmacocinetica conceptual, "
                "algoritmos diagnosticos y terapeuticos, arboles de decision, y curvas y "
                "tablas conceptuales (sensibilidad/especificidad, razones de verosimilitud, "
                "ROC, tablas 2x2) -- que es justo donde quedaron los iconos ShareAlike "
                "excluidos, asi que renderizar en casa repone esa perdida sin pedir licencia"),
        pendiente=["NO EXISTE todavia: cero imports de matplotlib, graphviz, pydot, svgwrite, "
                   "cairo, PIL o plotly en el repositorio, y Grafo.explicar() devuelve texto, "
                   "no figura. Es un plan, no un activo",
                   "la base juridica mas fuerte NO es la autoria humana sino LFDA art. 14, "
                   "que excluye de proteccion las ideas, procedimientos y metodos: redibujar "
                   "el ALGORITMO de una guia es legitimo por la dicotomia idea/expresion. "
                   "Copiar su figura concreta no lo es",
                   "LFDA art. 108 protege las bases de datos NO originales por cinco anos: si "
                   "las figuras no acumulan derecho de autor, el ACERVO COMPILADO si puede "
                   "ser el activo defendible",
                   "el riesgo residual no es infraccion, es NO EXCLUSIVIDAD: ORIONS puede "
                   "mostrar y monetizar una figura no protegida, pero no puede impedir que un "
                   "competidor la copie",
                   "no embeber archivos de fuente tipografica en el SVG sin revisar su "
                   "licencia: servir una webfont OFL ES distribucion"],
    ),
}


# Exclusiones duras. Estan en el codigo y no en un documento porque un
# documento no detiene un commit.
EXCLUIDAS: dict[str, str] = {
    "biorender": (
        "PROHIBIDA EN AMBAS CAPAS, incluida la gratuita. La clausula asesina no es "
        "comercial, es de PUBLICACION, y son dos prohibiciones acumulativas unidas por "
        "'nor': 'Free users: You may not publish any Science Figures containing BioRender "
        "Content, nor may you use any Science Figures containing BioRender content for "
        "commercial purposes.' Tres barreras mas: el Basic concede una licencia "
        "'non-assignable, non-transferable' SIN la palabra sublicense mientras el Academic "
        "si la concede expresamente, asi que ORIONS no tiene derecho que dar a sus "
        "estudiantes; 'combine the Services ... with or in any other program not authorized "
        "in writing by BioRender'; y pagar no abre la puerta, porque la Academic tambien "
        "veda el lucro y el plan de estudiante pagado (19.95 USD/mes) cae bajo el MISMO "
        "Basic. El permiso es de LISTA CERRADA, al reves de una CC: 'You may not do anything "
        "with the BioRender Content ... that is not expressly permitted'. Si ya hay figuras "
        "hechas con el plan gratuito, NO son publicables: hay que rehacerlas. Y nunca subir "
        "nada propio: los Individual Terms toman sobre el User Content compartido 'a "
        "perpetual, irrevocable, royalty-free, sublicensable license'"),
    "radiopaedia": (
        "hay una clausula escrita exactamente contra lo que ORIONS quiere hacer, y mata el "
        "uso INCLUSO sin cobrar: 'the use of numerous cases from Radiopaedia to create "
        "similar content is not fair use, even if the content is non-commercial'. Encima el "
        "ShareAlike es contagioso sobre la figura compuesta, y la version ya publicada no se "
        "des-licencia quitando la imagen despues"),
    "dermnet_compuesta": (
        "licencia PROPIETARIA descrita con vocabulario Creative Commons. El ND mata la "
        "figura compuesta en las dos capas: 'if you remix, transform, or build upon any "
        "Watermarked Images, you may not distribute the modified material'. Su definicion de "
        "comercial es mas amplia que la de CC ('circulation of over 500') y prohibe el "
        "entrenamiento de IA. En capa gratuita se admite SOLO intacta, con marca de agua "
        "visible y enlace de vuelta. Su consentimiento aguas arriba se otorgo para "
        "publicacion EN DERMNET y no es transferible"),
    "mindthegraph": (
        "descartada por ELECCION, no por prohibicion: su marca de agua debe conservarse 'as "
        "exported via the website', lo que choca de frente con traducir los rotulos al "
        "espanol, que para una plataforma mexicana no es cosmetica sino requisito; y su "
        "ShareAlike obligaria a distribuir cada figura de ORIONS bajo la misma licencia, de "
        "modo que cualquier estudiante podria redistribuir legalmente el banco. Servier da "
        "mas por menos"),
    "visiblebody": (
        "'limited, revocable, non-exclusive, non-transferrable, non-sublicensable license to "
        "access and make educational use of the Services', con exclusion expresa de usos "
        "derivados y de uso para terceros: servir la imagen a un cuerpo de estudiantes es "
        "sublicenciar y componer una figura es derivar, doble incumplimiento sin que importe "
        "el precio"),
    "ia_generativa": (
        "NO USAR para ninguna figura anatomica o clinica, en ninguna capa, por dos razones "
        "independientes. La juridica: las tres palabras 'if any' de la cesion de OpenAI son "
        "una no-garantia disfrazada. La decisiva es la CLINICA: Duggan et al., J Hand Surg "
        "Glob Online 2025;7(6):100845, 1,500 imagenes y seis generadores, 'failed to portray "
        "accurate anatomy and often included fictitious structures'; J Clin Med "
        "2025;14(7):2136 sobre Midjourney v6.0 y DALL-E 3, 'neither met acceptable medical "
        "education standards'. Y el precedente de proceso: Frontiers retracto "
        "10.3389/fcell.2023.1339390 el 2024-02-16 porque 'the article does not meet the "
        "standards of editorial and scientific rigor', reconociendo que un revisor SI "
        "detecto el problema de las figuras y el articulo se publico igual. Riesgo extra: un "
        "modelo entrenado con fotografia clinica puede memorizar rasgos identificables, asi "
        "que una imagen 'sintetica' no es necesariamente anonima"),
    "mimic_cxr": (
        "PhysioNet Credentialed Health Data License 1.5.0 con DUA firmado que PROHIBE "
        "compartir los datos y restringe el uso a investigacion. Es el dataset que cualquiera "
        "encuentra primero buscando 'chest x-ray dataset'. Rojo por CONTRATO, no por derecho "
        "de autor, que es un regimen distinto y mas duro: no hay excepcion legal que lo salve"),
    "icd11": (
        "ICD-11 es CC BY-ND 3.0 IGO: los usuarios 'are not permitted to make adaptations', y "
        "la guia de referencia precisa que eso incluye LAS TRADUCCIONES sin permiso de la OMS. "
        "Para una plataforma en espanol que reetiqueta todo, es un ND en el corazon del "
        "contenido. Los mapeos y crosslinks hacia otras clasificaciones tampoco estan cubiertos"),
    "openi_sin_filtrar": (
        "Open-i es un INDICE, no un titular: 'standard copyright protection applies unless an "
        "article explicitly states otherwise' y 'users are directly and solely responsible for "
        "compliance with copyright restrictions'. Solo sirve imagen por imagen, rechazando "
        "todo lo que no sea CC BY o CC0"),
    "gray_1918_como_verdad": (
        "libre y pedagogicamente OBSOLETO, que es una trampa que no existe para texto anclado "
        "en PMC. Su nomenclatura es anterior a la Terminologia Anatomica (FIPAT/IFAA), que es "
        "el estandar vigente y el que se evalua en el ENARM, y su encuadre ignora cien anos de "
        "imagen seccional: ninguna correlacion con TC ni RM. Usar solo como material historico, "
        "NUNCA como fuente de verdad anatomica"),
}


# Pistas que el critico de completitud abrio y que valen mas que seguir
# leyendo terminos de las fuentes ya dictaminadas.
PISTAS_ABIERTAS: list[str] = [
    "ISIC Archive (api.isic-archive.com): licencia POR IMAGEN en campo legible por maquina "
    "(copyright_license con valores CC-0, CC-BY, CC-BY-NC) y colecciones enteras declaradas "
    "CC-0. Es la respuesta al hueco de dermatologia en capa comercial, y es la misma "
    "arquitectura de compuerta que ya existe para Bioicons. Nadie la habia buscado",
    "PhysioNet PTB-XL y los ECG open-access (CC BY 4.0): son SENAL CRUDA, no imagen. Se "
    "renderiza el trazo en casa: cero obra derivada ajena, cero paciente identificable, cero "
    "atribucion dentro del pixel. Resuelve el hueco del ECG y es gratis",
    "The Cancer Imaging Archive: DICOM desidentificado bajo IRB con licencia por coleccion "
    "(varias CC BY). Es la unica ruta que resuelve consentimiento aguas arriba Y copyright a "
    "la vez, que es lo que se habia declarado imposible para imagen radiologica",
    "Health Icons (healthicons.org): CC0, iconografia de salud. La candidata de menor friccion "
    "del nicho y no estaba en el expediente",
    "Wellcome Collection: el mayor acervo medico con licencia abierta del mundo, con campo de "
    "derechos por pieza y API",
    "WikiPathways (CC0) frente a KEGG, que prohibe redistribuir sus mapas y cobra licencia: es "
    "la trampa clasica de vias metabolicas",
    "RCSB PDB (CC0 desde 2022) + PubChem (dominio publico) + RDKit (BSD): estructuras de "
    "farmacos renderizadas en casa desde SMILES. Cubre farmacologia. Cuidado con DrugBank "
    "(CC BY-NC mas licencia comercial aparte)",
    "BodyParts3D / Anatomography: MISMA CASA que TogoTV (DBCLS) pero CC BY-SA 2.1 Japon. "
    "Trampa de 'misma fuente, otra licencia' que usar TogoTV como fuente principal hace casi "
    "inevitable",
    "SciELO, Redalyc y Medigraphic: figuras YA EN ESPANOL con CC por articulo. Evitan la "
    "traduccion y por tanto evitan la derivada por completo. No se evaluo el corpus "
    "hispanohablante",
    "Anatomy Standard (CC BY-NC-SA): el unico atlas libre construido sobre Terminologia "
    "Anatomica, que es el estandar que se declaro obligatorio. NC-SA, asi que no entra: la "
    "unica fuente alineada con TA esta vedada por nuestra propia regla",
    "LFDA art. 87: el retrato de una persona solo puede usarse con su consentimiento EXPRESO, "
    "y la autorizacion es REVOCABLE. Se enforza como infraccion en materia de comercio via "
    "art. 231 fr. II, con multas por IMPI: carril independiente del copyright y de la LFPDPPP",
    "NOM-004-SSA3-2012: si ORIONS produce fotografia clinica propia, el material es parte del "
    "expediente y la custodia es institucional. Un residente NO puede aportar fotos de su "
    "hospital sin autorizacion institucional, por impecable que sea el consentimiento del "
    "paciente. Y el consentimiento propio no es un documento, son TRES: uso de retrato "
    "(LFDA 87), aviso de privacidad y datos sensibles (LFPDPPP), y consentimiento del acto "
    "medico (NOM-004)",
    "Ley General de Salud arts. 300-311 y el Reglamento en materia de publicidad: el riesgo "
    "concreto es la composicion que este mismo diseno permite -- una figura con nombre "
    "COMERCIAL de un farmaco, el credito a Servier (titular farmaceutico) debajo, y un boton "
    "de suscripcion en la misma pantalla. Usar siempre denominacion generica, nunca marca",
    "LFDA arts. 18-23: los derechos morales son inalienables, irrenunciables e "
    "imprescriptibles. Traducir los rotulos y recomponer la figura de un autor extranjero "
    "puede tocar el derecho de INTEGRIDAD aunque la licencia permita derivadas. Es el unico "
    "riesgo que sobrevive a una licencia CC impecable y no esta en ninguna regla de este modulo",
    "LFDA arts. 83-84: obra por encargo y obra bajo relacion laboral. Si quien dibuja o "
    "programa esta adscrito a una universidad u hospital, su reglamento de propiedad "
    "intelectual puede asignarle la titularidad a la institucion, y el unico activo 'propio' "
    "del proyecto podria no ser propio",
    "la atribucion NO sobrevive al canal real de consumo, que es captura de pantalla y "
    "exportacion a Anki, y no se puede impedir porque CC BY §2(a)(5)(B) prohibe imponer "
    "restricciones. Hay que quemar una banda de credito legible en el lienzo del archivo "
    "exportado y escribir XMP/IPTC. Bug de pipeline concreto: cwebp, sharp e ImageMagick "
    "DESCARTAN los metadatos por defecto, asi que el paso de optimizacion destruye la "
    "atribucion embebida sin que nadie lo note. Hay que probarlo en CI",
    "pudricion del enlace = pudricion de la prueba. Toda la defensa es 'el NIH lo etiqueto "
    "asi en tal fecha'. Por activo hacen falta copia local con hash, PDF o WARC fechado de la "
    "ficha, URL de Wayback, y un kill-switch: el activo se referencia por ID dentro del "
    "contenido, NUNCA pegado en el HTML de la leccion",
]
