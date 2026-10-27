"""La compuerta de licencias: lo que puede entrar a la Boveda y lo que no.

Este modulo existe porque un inventario de fuentes en un documento no impide
nada. Las reglas de licencia tienen que estar en el camino de ingesta, de modo
que un articulo inadmisible no entre aunque alguien se equivoque al llamar.

Todo lo que esta aqui sale de la verificacion de fuentes de este proyecto, no
de memoria. Lo que no se pudo verificar esta marcado como tal y falla cerrado.

LAS CUATRO TRAMPAS QUE JUSTIFICAN ESTE MODULO

1. "USO COMERCIAL PERMITIDO" NO SIGNIFICA "DERIVABLE SIN CONTAGIO".
   PMC agrupa como "Commercial Use Allowed" a CC0, CC BY, CC BY-SA y CC BY-ND.
   Es cierto que las cuatro permiten uso comercial, y aun asi dos son
   inservibles para la Boveda: CC BY-SA obliga a licenciar lo derivado bajo los
   mismos terminos, lo que contagiaria a la Boveda entera, y CC BY-ND prohibe
   los derivados, que es exactamente lo que es un hecho atomico extraido. Por
   eso la lista es BLANCA y por cadena exacta, nunca una exclusion de lo malo.

2. LA LICENCIA ES POR ARTICULO Y POR VERSION, no por fuente.
   No existe "la licencia de PMC". Existe `license_code` en cada version de cada
   articulo. Valores literales verificados en vivo: "CC BY", "CC BY-NC", "TDM" y
   null. La comparacion es de cadena exacta, incluidas mayusculas y el espacio.

3. license_code = null CON is_pmc_openaccess = true EXISTE.
   Verificado en registros reales: un articulo puede estar en el subconjunto de
   acceso abierto y no tener licencia legible por maquina. Si el codigo trata
   null como permisivo, ingiere contenido sin permiso comprobado. null es NO.

4. EL DOMINIO PUBLICO NO ALCANZA AL CONTENIDO DE TERCEROS EMBEBIDO.
   El 17 USC 105 despoja de derechos de autor a lo que escribio el gobierno de
   EEUU. No toca una linea de lo que el gobierno reprodujo con permiso de un
   tercero. Ese material viaja dentro del PDF de dominio publico conservando sus
   derechos intactos, y ORIONS no hereda el permiso que el VA negocio para si.
   Caso concreto verificado: los criterios del DSM-5 reproducidos dentro de la
   guia VA/DoD de estres postraumatico.

DOS EXCLUSIONES DE SEGURIDAD CLINICA, no de licencia

   is_retracted: un articulo retractado JAMAS puede anclar un hecho. Es la
   exclusion mas importante de todo el modulo y no tiene nada que ver con
   derechos de autor: tiene que ver con que la Boveda no ensene una cifra que la
   literatura ya repudio.

   is_historical_ocr: articulos escaneados de los siglos XVIII a XX, con texto
   reconocido opticamente y por tanto con ruido numerico. Para una tuberia que
   extrae cifras exactas, un 8 que era un 3 es peor que no tener el articulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .hecho import TipoAncla

# ---------------------------------------------------------------------------
# Licencias
# ---------------------------------------------------------------------------

# Cadenas EXACTAS verificadas en el campo license_code del bucket publico de
# PMC. La grafia importa: la comparacion es exacta.
# Grafias confirmadas leyendo el campo real del bucket publico (2026-10-27).
LICENCIAS_VERIFICADAS = {"CC BY", "CC BY-NC", "CC BY-NC-ND", "CC0", "TDM"}

# Lista BLANCA. Solo estas entran. Todo lo demas, incluido null y cualquier
# valor no visto antes, queda fuera por defecto.
#
# Grafias verificadas contra registros reales del bucket el 2026-10-27:
# "CC BY" (mayusculas, un espacio) y "CC0" (sin espacio). La comparacion es de
# cadena exacta, asi que la grafia no es un detalle: era un riesgo abierto hasta
# que se leyo el campo real.
PERMITIDAS = {"CC BY", "CC0"}

# Permiten uso comercial pero NO sirven para la Boveda, y conviene nombrarlas
# para que el motivo del rechazo sea preciso en vez de generico.
COMERCIAL_PERO_INSERVIBLE = {
    "CC BY-SA": ("obliga a licenciar lo derivado bajo los mismos terminos: "
                 "contagiaria la Boveda entera"),
    "CC BY-ND": ("prohibe obras derivadas, y un hecho atomico extraido es "
                 "precisamente una obra derivada"),
}

NO_COMERCIAL = {
    "CC BY-NC": "prohibe el uso comercial",
    "CC BY-NC-SA": "prohibe el uso comercial y ademas contagia",
    "CC BY-NC-ND": "prohibe el uso comercial y los derivados",
}


class MotivoRechazo(str, Enum):
    LICENCIA_NO_PERMITIDA = "licencia_no_permitida"
    LICENCIA_AUSENTE = "licencia_ausente"
    LICENCIA_DESCONOCIDA = "licencia_desconocida"
    FUERA_DE_OA = "fuera_del_subconjunto_abierto"
    RETRACTADO = "retractado"
    OCR_HISTORICO = "ocr_historico"


@dataclass
class Dictamen:
    admisible: bool
    motivo: str
    codigo: Optional[MotivoRechazo] = None
    advertencias: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.admisible


def admisible_pmc(registro: dict) -> Dictamen:
    """Decide si un registro del subconjunto abierto de PMC puede entrar.

    Espera el JSON por version del bucket publico, con las claves
    `license_code`, `is_pmc_openaccess`, `is_retracted` y `is_historical_ocr`.

    Falla CERRADO: cualquier cosa que no sea un si explicito es un no.
    """
    adv: list[str] = []

    # 1. Retractacion. Va primero porque es seguridad del paciente, no licencia.
    if registro.get("is_retracted") is True:
        return Dictamen(False, (f"articulo retractado ({registro.get('pmcid', '?')}): "
                                f"nunca puede anclar un hecho clinico"),
                        MotivoRechazo.RETRACTADO)

    # 2. Ruido de reconocimiento optico en una tuberia que extrae cifras exactas.
    if registro.get("is_historical_ocr") is True:
        return Dictamen(False, ("texto reconocido opticamente de un articulo historico: "
                                "el ruido numerico lo inhabilita para extraer cifras"),
                        MotivoRechazo.OCR_HISTORICO)

    # 3. Pertenencia al subconjunto abierto.
    if registro.get("is_pmc_openaccess") is not True:
        return Dictamen(False, "no pertenece al subconjunto de acceso abierto",
                        MotivoRechazo.FUERA_DE_OA)

    # 4. Licencia. Cadena exacta, lista blanca, null es no.
    lic = registro.get("license_code")
    if lic is None:
        return Dictamen(False, ("esta en el subconjunto abierto pero sin licencia legible "
                                "por maquina (license_code = null, el grupo 'Other'): "
                                "sin permiso comprobable no entra"),
                        MotivoRechazo.LICENCIA_AUSENTE)
    if not isinstance(lic, str):
        return Dictamen(False, f"license_code no es una cadena: {lic!r}",
                        MotivoRechazo.LICENCIA_DESCONOCIDA)

    if lic in PERMITIDAS:
        if registro.get("is_manuscript") is True:
            adv.append("es manuscrito de autor, no la version publicada: las cifras "
                       "pueden diferir de la version final")
        adv.append(f"la licencia {lic} cubre la obra del autor, NO necesariamente las "
                   f"figuras, tablas o escalas que esa obra reproduzca de terceros")
        return Dictamen(True, f"licencia {lic}: uso comercial y derivados permitidos",
                        None, adv)

    if lic in COMERCIAL_PERO_INSERVIBLE:
        return Dictamen(False, (f"{lic} permite uso comercial pero "
                                f"{COMERCIAL_PERO_INSERVIBLE[lic]}"),
                        MotivoRechazo.LICENCIA_NO_PERMITIDA)
    if lic in NO_COMERCIAL:
        return Dictamen(False, f"{lic} {NO_COMERCIAL[lic]}",
                        MotivoRechazo.LICENCIA_NO_PERMITIDA)
    if lic == "TDM":
        return Dictamen(False, ("TDM autoriza mineria de textos y datos pero no es una "
                                "licencia de reuso del contenido: no habilita publicar "
                                "lo derivado en un producto"),
                        MotivoRechazo.LICENCIA_NO_PERMITIDA)

    return Dictamen(False, (f"license_code '{lic}' no esta en la lista verificada "
                            f"{sorted(LICENCIAS_VERIFICADAS)} ni en la blanca "
                            f"{sorted(PERMITIDAS)}: se rechaza por defecto"),
                    MotivoRechazo.LICENCIA_DESCONOCIDA)


# ---------------------------------------------------------------------------
# Catalogo de fuentes
# ---------------------------------------------------------------------------


@dataclass
class Fuente:
    """Una fuente verificada, con sus obligaciones y sus riesgos."""

    clave: str
    nombre: str
    tipo_ancla: TipoAncla
    base_legal: str
    permite_comercial: bool
    permite_ia: bool
    share_alike: bool
    acceso: str
    obligaciones_continuas: list[str] = field(default_factory=list)
    riesgo_terceros: str = ""
    huecos: list[str] = field(default_factory=list)
    confianza_dictamen: str = "media"
    pendiente_verificar: list[str] = field(default_factory=list)


CATALOGO: dict[str, Fuente] = {
    "clinicaltrials": Fuente(
        clave="clinicaltrials",
        nombre="ClinicalTrials.gov (registro y base de resultados), API v2",
        tipo_ancla=TipoAncla.REGISTRO_ENSAYO,
        base_legal=("licencia expresa unilateral otorgada a cualquiera sin cargo. NO es "
                    "dominio publico declarado. Esto importa: una licencia expresa vuelve "
                    "irrelevante que Mexico no tenga excepcion de mineria de textos y "
                    "datos, porque no se necesita una excepcion cuando hay licencia"),
        permite_comercial=True, permite_ia=True, share_alike=False,
        acceso="API v2 publica sin llave en https://clinicaltrials.gov/api/v2",
        obligaciones_continuas=[
            "mantener los datos actualizados en todo momento mientras se retengan: un "
            "snapshot congelado INCUMPLE los terminos. Exige sincronizacion delta con "
            "filter.advanced=AREA[LastUpdatePostDate]RANGE[...]",
            "si se expone una version congelada, declarar la fecha del snapshot de forma "
            "prominente",
            "los deberes son perpetuos mientras se retenga cualquier dato de la fuente",
        ],
        riesgo_terceros=("alto en los documentos grandes subidos por el patrocinador, que "
                         "viven FUERA del JSON. No ingerirlos: el JSON del registro basta"),
        confianza_dictamen="alta",
    ),
    "openfda": Fuente(
        clave="openfda",
        nombre="openFDA drug label y DailyMed SPL",
        tipo_ancla=TipoAncla.ETIQUETA_REGULADOR,
        base_legal="CC0 1.0 Universal, dedicacion al dominio publico declarada por la FDA",
        permite_comercial=True, permite_ia=True, share_alike=False,
        acceso=("API en https://api.fda.gov/drug/label.json, llave gratuita opcional; "
                "descarga masiva por particiones; DailyMed publica releases completos"),
        obligaciones_continuas=[
            "no implicar respaldo de la FDA ni usar su nombre o logo para sugerirlo",
            "el dataset se actualiza semanalmente: refrescar o declarar la fecha",
        ],
        riesgo_terceros=("los codigos GMDN son la UNICA prohibicion explicita de "
                         "entrenamiento de IA en todo openFDA: excluirlos"),
        huecos=["NO existe campo estructurado de ajuste renal ni hepatico: los cortes de "
                "eGFR y de depuracion de creatinina viven solo como prosa dentro de "
                "dosage_and_administration y use_in_specific_populations, asi que hay que "
                "parsearlos"],
        confianza_dictamen="alta",
    ),
    "pmc_oa": Fuente(
        clave="pmc_oa",
        nombre="PubMed Central Open Access Subset y Europe PMC",
        tipo_ancla=TipoAncla.ARTICULO_CC_BY,
        base_legal=("por articulo y por version, en el campo license_code. No existe "
                    "'la licencia de PMC'"),
        permite_comercial=True, permite_ia=True, share_alike=True,
        acceso=("PMC Cloud Service en AWS Open Data, s3://pmc-oa-opendata. ATENCION: la "
                "infraestructura clasica de descarga se DESCONTINUO en agosto de 2026, "
                "incluidos el servicio FTP y el OA Web Service API (oa.fcgi). Cualquier "
                "codigo o tutorial que use esas rutas esta roto"),
        obligaciones_continuas=[
            "mantener la version mas actual de los datos redistribuidos, o declarar "
            "claramente que el producto puede no reflejar los datos mas recientes",
            "atribucion por articulo, no por fuente: cada hecho arrastra la cita de SU "
            "articulo",
            "re-chequear is_retracted de forma periodica: un articulo se retracta DESPUES "
            "de haber sido ingerido, y entonces hay que invalidar los hechos que anclo",
        ],
        riesgo_terceros=("alto y es el riesgo mas subestimado de esta fuente: la licencia "
                         "cubre la obra del autor, no lo que la obra reproduce de otros. "
                         "Un articulo CC BY puede llevar embebidas figuras, tablas o "
                         "escalas clinicas con permiso puntual, y ese material NO hereda "
                         "la CC BY"),
        confianza_dictamen="alta",
        pendiente_verificar=[
            "la lista CERRADA y oficial de valores posibles de license_code: el README "
            "del dataset no la enumera. Verificadas empiricamente cinco grafias; "
            "cualquier valor nuevo se rechaza por defecto, que es el comportamiento "
            "correcto pero significa perder articulos en silencio hasta que alguien lo note",
            "cuantos articulos son CC BY frente al total del subconjunto abierto: los dos "
            "endpoints que lo darian siguen bloqueados en este entorno",
            "si un articulo retractado DESPUES de ser ingerido cambia su is_retracted en "
            "el bucket, y con que latencia: de eso depende el periodo del re-chequeo",
        ],
    ),
    "uspstf": Fuente(
        clave="uspstf",
        nombre="US Preventive Services Task Force (y su API ePSS)",
        tipo_ancla=TipoAncla.GUIA_GOBIERNO,
        base_legal=(
            "CORRECCION DE UN ERROR PREVIO DE ESTE PROYECTO: el USPSTF NO es dominio "
            "publico. No lo declara. AHRQ otorga un permiso CONDICIONADO que permite "
            "reproducir, redistribuir, mostrar publicamente e incorporar la obra en otros "
            "materiales, pero con la condicion de que quede INALTERADA, exige descargo "
            "para adaptaciones, exige citar el sitio del USPSTF, y contiene clausula "
            "anticomercial explicita. La exigencia de 'inalterada' es incompatible con la "
            "tesis de ORIONS, que es derivar: un hecho atomico extraido es una alteracion"
        ),
        permite_comercial=False, permite_ia=False, share_alike=False,
        acceso="API ePSS y datos estructurados de recomendaciones con sus grados",
        obligaciones_continuas=[
            "si algun dia se licencia: mantener la obra inalterada y citar el sitio, lo "
            "que en la practica impide el uso que ORIONS necesita",
        ],
        riesgo_terceros="",
        huecos=["la pieza mas valiosa del bloque de EEUU (recomendaciones preventivas con "
                "grado, en JSON, con API) resulta ser la mas restringida, y las dos unicas "
                "clausulas anticomerciales del bloque vienen de AHRQ, que es justo la "
                "agencia que sostiene al USPSTF"],
        confianza_dictamen="media",
        pendiente_verificar=["el texto literal completo del aviso de derechos de AHRQ, "
                             "para precisar el alcance exacto de la clausula anticomercial"],
    ),
    "cdc_mmwr": Fuente(
        clave="cdc_mmwr",
        nombre="CDC: MMWR y la especificacion CDSi del calendario ACIP",
        tipo_ancla=TipoAncla.GUIA_GOBIERNO,
        base_legal=("dominio publico, y es el mas limpio y mejor documentado de todo el "
                    "bloque de EEUU: el MMWR lleva compromiso de dominio publico firmado "
                    "por los autores"),
        permite_comercial=True, permite_ia=True, share_alike=False,
        acceso=("MMWR por web y por los datos de data.cdc.gov con Socrata. Y la pieza mas "
                "valiosa: CDC CDSi, Clinical Decision Support for Immunization, es el "
                "UNICO lugar donde el calendario ACIP existe como LOGICA EJECUTABLE y no "
                "como PDF (Logic Specification for ACIP Recommendations, v4.6, 151 pags)"),
        obligaciones_continuas=["no implicar respaldo del CDC"],
        riesgo_terceros="",
        huecos=["el calendario mexicano difiere del de ACIP, asi que el CDSi sirve como "
                "MOTOR de reglas (edad minima absoluta, intervalo minimo, numero de dosis) "
                "y no como contenido"],
        confianza_dictamen="media",
    ),
    "mexico_nom": Fuente(
        clave="mexico_nom",
        nombre="Normas Oficiales Mexicanas de salud, via el DOF",
        tipo_ancla=TipoAncla.NORMA_OFICIAL,
        base_legal=(
            "Ley Federal del Derecho de Autor, articulo 14 fraccion VIII, texto literal: "
            "no son objeto de proteccion 'los textos legislativos, reglamentarios, "
            "administrativos o judiciales, asi como sus traducciones oficiales. En caso de "
            "ser publicados, deberan apegarse al texto oficial y no conferiran derecho "
            "exclusivo de edicion'. Una NOM es un texto reglamentario y cae de lleno aqui. "
            "PERO la misma fraccion continua: 'Sin embargo, seran objeto de proteccion las "
            "concordancias, interpretaciones, estudios comparativos, anotaciones, "
            "comentarios y demas trabajos similares'. Esa segunda mitad corta en los dos "
            "sentidos: una Guia de Practica Clinica puede ser una interpretacion y no un "
            "texto administrativo puro, y por tanto estar protegida; y la capa comparativa "
            "de ORIONS, el delta Mexico y la discordancia entre paneles, queda protegida "
            "como obra PROPIA. Es el unico articulo del expediente que da un activo, no "
            "solo un permiso"
        ),
        permite_comercial=True, permite_ia=True, share_alike=False,
        acceso=("DOF por nota, con patron de URL por codigo y fecha. El activo tecnico es "
                "el PDF con firma electronica avanzada, disponible solo desde julio de "
                "2012. No se verifico que exista API"),
        obligaciones_continuas=[
            "apegarse al texto oficial: la exencion del articulo 14 es para el texto tal "
            "cual, no para una version editada que se presente como la norma",
            "seguir la vigencia en el DOF: una NOM derogada que siga viva en la Boveda es "
            "exposicion por informacion sanitaria erronea",
        ],
        riesgo_terceros="",
        huecos=["es la unica fuente que da el criterio OBLIGATORIO en Mexico y no el "
                "recomendado en otro pais. El ENARM se califica contra la norma mexicana y "
                "el Catalogo Maestro, no contra la ESC ni la ADA: una Boveda construida "
                "solo con evidencia primaria internacional reconstruye la ciencia y falla "
                "el examen"],
        confianza_dictamen="media",
    ),
    "mexico_cenetec": Fuente(
        clave="mexico_cenetec",
        nombre="Guias de Practica Clinica del Catalogo Maestro (CENETEC, hoy DGMoSS)",
        tipo_ancla=TipoAncla.NORMA_OFICIAL,
        base_legal=("incierta. Podria ampararse en el articulo 14 fraccion VIII como texto "
                    "administrativo, o quedar protegida por la segunda mitad de esa misma "
                    "fraccion como interpretacion o estudio comparativo. No se encontro "
                    "aviso de uso"),
        permite_comercial=False, permite_ia=False, share_alike=False,
        acceso=("INCIERTO Y URGENTE: CENETEC dejo de existir con ese nombre y es ahora la "
                "Direccion General de Modernizacion del Sector Salud. Notas de prensa de "
                "2025 afirman que el acceso a su sitio y al Catalogo Maestro fue "
                "SUSPENDIDO. Es prensa, no boletin oficial, y no se confirmo con fuente "
                "primaria. Si es cierto, ORIONS no tiene un problema de licencia con el "
                "Catalogo Maestro: tiene un problema de EXISTENCIA"),
        obligaciones_continuas=[],
        riesgo_terceros=("alto por otra via: las GPC completas estan en ResearchGate, "
                         "Studocu y sitios de ENARM. Tomarlas de ahi es PEOR que no "
                         "tomarlas, porque son copias sin cadena de custodia y el acto de "
                         "descargarlas de un espejo no autorizado agrega su propia falta"),
        huecos=["sin el Catalogo Maestro, el criterio mexicano de practica clinica no tiene "
                "fuente estructurada, y es justo lo que el ENARM evalua"],
        confianza_dictamen="baja",
        pendiente_verificar=[
            "si el Catalogo Maestro sigue publicamente accesible tras el cambio a DGMoSS: "
            "es la verificacion de mayor valor pendiente en todo el expediente, porque de "
            "ella depende la viabilidad de la capa mexicana",
            "pedir por escrito el permiso de uso educativo a la DGMoSS: es gratis "
            "intentarlo y un si cambia el calculo",
        ],
    ),
    "terminologias": Fuente(
        clave="terminologias",
        nombre="Terminologias, ontologias y grafos biomedicos (UMLS, SNOMED, LOINC, etc)",
        tipo_ancla=TipoAncla.DERIVADA,
        base_legal="NO VERIFICADO. No se obtuvo ni una linea literal de licencia",
        permite_comercial=False, permite_ia=False, share_alike=False,
        acceso=("NO VERIFICADO: egress bloqueado a snomed.org, loinc.org, nlm.nih.gov, "
                "reactome.org, genome.jp y otros"),
        obligaciones_continuas=[],
        riesgo_terceros=(
            "LA TRAMPA ESTRUCTURAL, el mismo patron que PMC: en terminologias biomedicas "
            "el permiso casi nunca es del agregado sino de CADA COMPONENTE. Los cuatro "
            "grafos que un equipo con prisa descargaria primero (UMLS, Open Targets, "
            "PrimeKG, Hetionet) son precisamente los cuatro donde la licencia de la "
            "envoltura NO describe la licencia del contenido. En UMLS cada vocabulario "
            "fuente tiene su propia categoria de restriccion y el acuerdo remite al titular"
        ),
        huecos=["si se confirma que Mexico no es miembro de SNOMED International (los "
                "miembros latinoamericanos serian Argentina, Chile y Uruguay), SNOMED CT "
                "es inviable para una empresa mexicana con presupuesto cero"],
        confianza_dictamen="baja",
        pendiente_verificar=[
            "TODO. Este dictamen es NO_VERIFICADO por imposibilidad tecnica, no por "
            "ambiguedad de las fuentes, y hasta que se verifique ninguna de estas fuentes "
            "entra a la Boveda",
            "la membresia de Mexico en SNOMED International",
            "si StatPearls lleva clausula NonCommercial y NoDerivatives: si se confirma es "
            "doblemente inusable, porque el no comercial mata el producto y el sin "
            "derivados mata la derivacion",
        ],
    ),
    "vadod": Fuente(
        clave="vadod",
        nombre="Guias de practica clinica VA/DoD",
        tipo_ancla=TipoAncla.GUIA_GOBIERNO,
        base_legal=("dominio publico por operacion de ley, 17 USC 105. No es una licencia: "
                    "es AUSENCIA de derecho. Mas fuerte que una licencia, porque nadie "
                    "puede revocarla, y mas fragil en los bordes, porque no cubre lo que "
                    "no sea obra del gobierno"),
        permite_comercial=True, permite_ia=True, share_alike=False,
        acceso=("descarga manual de PDF. NO hay API, NO hay JSON, NO hay descarga masiva "
                "oficial. La estructura de URL es predecible, lo que permite un rastreador "
                "propio: healthquality.va.gov/HEALTHQUALITY/guidelines/{CATEGORIA}/{tema}/"),
        obligaciones_continuas=[
            "versionado propio: el dominio publico no obliga a nada, pero la "
            "responsabilidad clinica si. Una guia retirada que siga viva en la Boveda es "
            "exposicion por informacion sanitaria erronea",
            "detectar la retirada de una guia, que no se anuncia por ningun canal "
            "estructurado",
        ],
        riesgo_terceros=("ALTO, y es el unico riesgo serio de esta fuente. El 17 USC 105 "
                         "despoja de derechos a lo que escribio el gobierno, no a lo que el "
                         "gobierno reprodujo con permiso de un tercero: ese material viaja "
                         "dentro del PDF conservando sus derechos, y ORIONS no hereda el "
                         "permiso que el VA negocio. Caso verificado: los criterios del "
                         "DSM-5 reproducidos en la guia de estres postraumatico. Revisar "
                         "las primeras paginas y las notas al pie de cada PDF y excluir lo "
                         "marcado"),
        huecos=[
            "INSUFICIENCIA CARDIACA: no existe guia vigente. La de 2007 esta archivada y "
            "retirada",
            "SINDROME CORONARIO AGUDO: no existe guia VA/DoD, ni vigente ni archivada",
            "ARRITMIAS: no existe",
        ],
        confianza_dictamen="media",
        pendiente_verificar=[
            "no se pudo abrir ningun PDF primario completo: el entorno bloquea "
            "healthquality.va.gov y health.mil",
            "no se encontro pagina de terminos de uso ni aviso de derechos a nivel de "
            "sitio: el dictamen de dominio publico se apoya en el 17 USC 105 y en la "
            "ausencia de aviso, no en una declaracion del propio VA",
        ],
    ),
}


def fuentes_de_ancla(tipo: TipoAncla) -> list[Fuente]:
    """Todas las fuentes que pueden sostener ese tipo de ancla."""
    return [f for f in CATALOGO.values() if f.tipo_ancla is tipo]


def fuente_de_ancla(tipo: TipoAncla) -> Optional[Fuente]:
    """La fuente USABLE para ese tipo de ancla, o None si no hay ninguna.

    Devolver "la primera del catalogo" era un error latente: varias fuentes
    comparten tipo de ancla (el USPSTF y VA/DoD son las dos guias de gobierno; la
    NOM y el Catalogo Maestro son las dos normativa mexicana) y en los dos casos
    la primera en orden alfabetico resulta ser la INUSABLE. Un ayudante que
    devuelve la fuente prohibida cuando le piden la fuente de un tipo es peor que
    no tener el ayudante.
    """
    usables = [f for f in fuentes_de_ancla(tipo) if f.permite_comercial and f.permite_ia]
    if not usables:
        return None
    # a igual usabilidad, la de dictamen mas confiable
    orden = {"alta": 0, "media": 1, "baja": 2}
    return min(usables, key=lambda f: orden.get(f.confianza_dictamen, 3))


def obligaciones_pendientes() -> list[str]:
    """Todas las obligaciones continuas, que son la lista de tareas programadas.

    Sirve para lo que suele olvidarse: el permiso no es un tramite que se cierra,
    es una carga de operacion. Esta lista es el contenido real del cron de
    cumplimiento.
    """
    out = []
    for f in CATALOGO.values():
        for o in f.obligaciones_continuas:
            out.append(f"[{f.clave}] {o}")
    return out


def huecos_de_cobertura() -> list[str]:
    """Donde NO hay fuente libre, que es lo que decide el orden de construccion."""
    out = []
    for f in CATALOGO.values():
        for h in f.huecos:
            out.append(f"[{f.clave}] {h}")
    return out


def pendientes_de_verificar() -> list[str]:
    """Lo que falta confirmar antes de lanzar. Cada linea es un riesgo abierto."""
    out = []
    for f in CATALOGO.values():
        for p in f.pendiente_verificar:
            out.append(f"[{f.clave}] {p}")
    return out


__all__ = [
    "admisible_pmc", "Dictamen", "MotivoRechazo", "Fuente", "CATALOGO",
    "PERMITIDAS", "LICENCIAS_VERIFICADAS", "COMERCIAL_PERO_INSERVIBLE", "NO_COMERCIAL",
    "fuente_de_ancla", "fuentes_de_ancla", "obligaciones_pendientes",
    "huecos_de_cobertura",
    "pendientes_de_verificar",
]
