"""Pruebas de la compuerta de imagen.

Las que importan son las que prueban el ORDEN de las reglas, porque el orden
es la decision de diseno: el error que casi mata el caso fue preguntar por el
dinero antes que por la publicacion.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from boveda.harness.imagenes import (
    CATALOGO, EXCLUIDAS, PISTAS_ABIERTAS, Activo, Capa, Declarante,
    MotivoImagen, Uso, Verificacion, admisible, restricciones_aguas_abajo,
)

fallos = []
n = 0


def ok(cond, msg):
    global n
    n += 1
    if not cond:
        fallos.append(msg)


def activo_bueno(**kw) -> Activo:
    """Un activo CC BY 4.0 de Servier, modificado, listo para publicar."""
    base = dict(
        clave="nefron", fuente="servier", licencia_literal="CC BY",
        version="4.0", url_entrada="https://smart.servier.com/x/1",
        fecha_descarga="2026-10-28",
        permite_publicacion=True, permite_comercial=True, permite_derivadas=True,
        alt="Esquema del nefron con el tubulo proximal rotulado",
        revisor_clinico="Dra. N. N., ced. 0000000",
    )
    base.update(kw)
    return Activo(**base)


# --- El caso base pasa -----------------------------------------------------
d = admisible(activo_bueno())
ok(bool(d), f"un CC BY 4.0 completo deberia pasar: {d.motivo}")
d = admisible(activo_bueno(), capa=Capa.COMERCIAL)
ok(bool(d), "y tambien en capa comercial")


# --- EL CASO BIORENDER: prohibe publicar, no cobrar ------------------------
# Permite comercio pero no publicacion. La intuicion dice que si no cobras
# estas a salvo; la clausula dice lo contrario.
d = admisible(activo_bueno(permite_publicacion=False), capa=Capa.GRATUITA)
ok(not d, "un activo que no permite PUBLICAR debe caer en la capa GRATUITA")
ok(d.codigo is MotivoImagen.NO_PERMITE_PUBLICAR,
   f"y el motivo debe ser la publicacion, no el dinero: {d.codigo}")


# --- El carril que no es de derecho de autor -------------------------------
# Licencia impecable, foto ilegal de publicar.
d = admisible(activo_bueno(persona_identificable=True))
ok(not d, "una foto de persona identificable sin consentimiento debe caer "
          "aunque la licencia sea CC BY impecable")
ok(d.codigo is MotivoImagen.PERSONA_IDENTIFICABLE, f"motivo: {d.codigo}")

# Con consentimiento para ORIONS pasa, pero deja advertencia.
d = admisible(activo_bueno(persona_identificable=True,
                           consentimiento_para_orions=True))
ok(bool(d), "con consentimiento otorgado a ORIONS deberia pasar")
ok(any("archivar el documento" in a for a in d.advertencias),
   "y debe advertir que hay que archivar el consentimiento")

# EL ORDEN: un activo que falla por las dos cosas reporta al paciente primero.
d = admisible(activo_bueno(persona_identificable=True, permite_publicacion=False))
ok(d.codigo is MotivoImagen.PERSONA_IDENTIFICABLE,
   "cuando fallan paciente Y publicacion, manda el paciente: ninguna licencia "
   f"levanta ese rechazo y por eso va primero. Dio {d.codigo}")


# --- ND mata las dos capas porque traducir ya es derivar -------------------
for capa in (Capa.GRATUITA, Capa.COMERCIAL):
    d = admisible(activo_bueno(licencia_literal="CC BY-NC-ND", version="4.0"),
                  capa=capa)
    ok(not d, f"CC BY-NC-ND debe caer tambien en capa {capa.value}")
    ok(d.codigo is MotivoImagen.SIN_DERIVADAS,
       f"y el motivo es el ND, no el NC: {d.codigo}")

# CC BY-ND sin NC: igual cae, por el ND.
d = admisible(activo_bueno(licencia_literal="CC BY-ND", version="4.0"))
ok(not d and d.codigo is MotivoImagen.SIN_DERIVADAS, "CC BY-ND cae por el ND")


# --- NC solo cae en la capa comercial, y avisa en la gratuita -------------
d = admisible(activo_bueno(licencia_literal="CC BY-NC", version="4.0"),
              capa=Capa.GRATUITA)
ok(bool(d), f"CC BY-NC deberia servir en la capa gratuita: {d.motivo}")
ok(any("se des-licencia" in a for a in d.advertencias),
   "y debe advertir que la version ya publicada no se des-licencia despues")
d = admisible(activo_bueno(licencia_literal="CC BY-NC", version="4.0"),
              capa=Capa.COMERCIAL)
ok(not d and d.codigo is MotivoImagen.NO_COMERCIAL, "CC BY-NC cae en comercial")


# --- ShareAlike: contagio ------------------------------------------------
d = admisible(activo_bueno(licencia_literal="CC BY-SA", version="4.0"))
ok(not d, "CC BY-SA no entra")
ok(d.codigo is MotivoImagen.SHARE_ALIKE, f"motivo: {d.codigo}")


# --- Marca de agua: condicion sobre el pixel -----------------------------
d = admisible(activo_bueno(marca_de_agua_obligatoria=True), uso=Uso.COMPUESTA)
ok(not d, "un activo con marca de agua obligatoria no entra en figura compuesta")
ok(d.codigo is MotivoImagen.MARCA_DE_AGUA, f"motivo: {d.codigo}")

# Intacta y sin modificar, si entra.
d = admisible(activo_bueno(marca_de_agua_obligatoria=True, fue_modificado=False),
              uso=Uso.INTACTA)
ok(bool(d), f"intacta deberia entrar: {d.motivo}")
ok(any("reencodeo" in a for a in d.advertencias),
   "y debe advertir de excluirla del paso de reescalado, que puede cortarla")


# --- Sin version declarada: cuarentena ----------------------------------
d = admisible(activo_bueno(version=None))
ok(not d and d.codigo is MotivoImagen.SIN_VERSION,
   "un CC BY sin version declarada va a cuarentena: las obligaciones cambian "
   "entre 3.0 y 4.0")
# Dominio publico no tiene version, y no debe caer por eso.
d = admisible(activo_bueno(licencia_literal="DOMINIO PUBLICO", version=None))
ok(bool(d), f"dominio publico no declara version y no debe caer por eso: {d.motivo}")


# --- Dataset con DUA: regimen distinto ----------------------------------
d = admisible(activo_bueno(licencia_literal="PhysioNet Credentialed"))
ok(not d and d.codigo is MotivoImagen.LICENCIA_DE_DATASET,
   f"un DUA firmado no es una licencia de contenido: {d.codigo}")


# --- Licencia desconocida: falla cerrado --------------------------------
d = admisible(activo_bueno(licencia_literal="libre para uso educativo"))
ok(not d and d.codigo is MotivoImagen.LICENCIA_DESCONOCIDA,
   "la lista es blanca y la comparacion exacta: todo valor nuevo queda fuera")


# --- Logotipo: la marca sobrevive al dominio publico -------------------
d = admisible(activo_bueno(licencia_literal="DOMINIO PUBLICO", version=None,
                           es_logotipo_o_marca=True))
ok(not d and d.codigo is MotivoImagen.LOGOTIPO_O_MARCA,
   "el dominio publico libera el copyright, no la marca")


# --- Procedencia, alt y revision clinica -------------------------------
d = admisible(activo_bueno(url_entrada=""))
ok(not d and d.codigo is MotivoImagen.SIN_PROCEDENCIA, "sin URL no hay defensa")
d = admisible(activo_bueno(alt="   "))
ok(not d and d.codigo is MotivoImagen.SIN_TEXTO_ALTERNATIVO,
   "sin texto alternativo no publica")
d = admisible(activo_bueno(revisor_clinico=""))
ok(not d and d.codigo is MotivoImagen.SIN_REVISION_CLINICA,
   "la licencia aprobada no suple el cotejo clinico")


# --- El agregador advierte -------------------------------------------
d = admisible(activo_bueno(fuente="bioicons", declarada_por=Declarante.AGREGADOR))
ok(bool(d) and any("agregador" in a for a in d.advertencias),
   "un activo declarado por agregador debe pasar con advertencia")


# --- fue_modificado arranca en True, y eso cambia el credito ---------
a = Activo(clave="x", fuente="servier", licencia_literal="CC BY", version="4.0",
           url_entrada="u", fecha_descarga="2026-10-28")
ok(a.fue_modificado is True,
   "fue_modificado debe arrancar en True: traducir los rotulos al espanol ya "
   "es modificar, y en ORIONS eso pasa siempre")
texto = a.atribucion("Image provided by {url}", "Image adapted from {url}")
ok("adapted" in texto,
   f"el credito por defecto debe ser 'adapted from', no 'provided by': {texto}")
a.fue_modificado = False
ok("provided" in a.atribucion("Image provided by {url}", "Image adapted from {url}"),
   "y 'provided by' solo cuando el activo esta intacto")


# --- La trampa que va en direccion contraria -------------------------
faltas = restricciones_aguas_abajo(tiene_drm=True, tos_prohibe_descarga=True,
                                   activos_cc=12)
ok(len(faltas) == 2,
   f"DRM y ToS restrictivo sobre activos CC son dos incumplimientos de ORIONS "
   f"contra las licencias que SI tiene, no del reves: {len(faltas)}")
ok(not restricciones_aguas_abajo(True, True, 0),
   "sin activos CC no hay restriccion aguas abajo que incumplir")


# --- El catalogo declara su nivel de verificacion -------------------
ok(len(CATALOGO) >= 5, f"el catalogo tiene {len(CATALOGO)} fuentes")
for clave, f in CATALOGO.items():
    ok(isinstance(f.verificacion, Verificacion),
       f"{clave} debe declarar como se verifico")
    ok(f.capa_gratuita in {"verde", "ambar", "rojo"}, f"{clave}: capa gratuita")
    ok(f.capa_comercial in {"verde", "ambar", "rojo"}, f"{clave}: capa comercial")
    if f.verificacion is not Verificacion.PRIMARIO_LEIDO:
        ok(bool(f.pendiente),
           f"{clave} no se leyo al primario y debe decir que falta")

ok(CATALOGO["togotv"].verificacion is Verificacion.PRIMARIO_LEIDO,
   "TogoTV se leyo en su repositorio oficial")
ok(CATALOGO["bioart"].verificacion is Verificacion.INDICE_CONCORDANTE,
   "BIOART NO se leyo al primario: el HTML esta bloqueado desde este contenedor")
ok(CATALOGO["bioart"].capa_comercial == "ambar",
   "y por eso su capa comercial es ambar, por falta de lectura, no por prohibicion")
ok(any("muestra insuficiente" in p for p in CATALOGO["bioart"].pendiente),
   "la justificacion escrita de 'solo Public Domain' debe ser la muestra "
   "insuficiente, no 'nadie exhibio una entrada NC'")

ok("biorender" in EXCLUIDAS and "publish" in EXCLUIDAS["biorender"],
   "BioRender excluida, y por la clausula de publicacion")
ok(len(EXCLUIDAS) >= 8, f"{len(EXCLUIDAS)} exclusiones duras en codigo")
ok(len(PISTAS_ABIERTAS) >= 10, f"{len(PISTAS_ABIERTAS)} pistas abiertas")


print(f"test_imagenes: {n} aserciones")
if fallos:
    for f in fallos:
        print("  FALLO:", f)
    sys.exit(1)
