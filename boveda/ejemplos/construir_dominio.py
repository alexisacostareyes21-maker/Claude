"""Construye un dominio real de la Boveda, contra PMC en vivo.

A diferencia de isglt2_nefroproteccion.py, que demuestra el pipeline con cifras
de muestra, este script produce HECHOS REALES: cada cifra se lee del texto de un
articulo de acceso abierto, se verifica byte a byte contra el documento, y queda
anclada con el desplazamiento exacto donde se leyo.

Lo que hace, en orden:

  1. Para cada afirmacion, ancla su cifra en un articulo de PMC. La compuerta de
     licencias corre ANTES de leer el contenido: un articulo que ORIONS no puede
     usar no se abre.
  2. Construye el Hecho con su poblacion, su cadena de mecanismos y su
     justificacion de inclusion propia.
  3. Atestigua. Una cifra leida de su fuente y verificada entra por la via de
     extraccion directa, que no exige triangulacion pero marca que falta una
     segunda lectura.
  4. Pasa los controles de independencia (no umbrales sinteticos, no gradaciones
     ajenas, orden recomputable) y de voz (no normativo sin atribuir, referente
     de poblacion).
  5. Escribe dominios/erc_isglt2.json con lo que resulto publicable y con lo que
     quedo en la cola de revision.

Requiere red hacia pmc-oa-opendata.s3.amazonaws.com.

Ejecutar:  python3 ejemplos/construir_dominio.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import independencia, voz
from harness.anclar import FetcherHTTP, anclar_en_articulo, aplicar_anclaje
from harness.atestiguar import (
    Certeza, Elicitacion, Encuadre, Procedencia, aplicar, cola_de_revision,
)
from harness.hecho import ClaseHecho, Hecho, Poblacion
from harness.independencia import Justificacion, OrigenSeleccion
from harness.numeros import parsear

HOY = "2026-10-28"   # se pasa como parametro: la Boveda no lee el reloj
SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "dominios", "erc_isglt2.json")
CACHE = "/tmp/claude-0/-home-user-Claude/d11f4837-03d4-5893-8c22-3f914f695e0d/scratchpad/cache"


def p1(t: str):
    r = parsear(t)
    return r[0] if r else None


# ---------------------------------------------------------------------------
# Las afirmaciones. La cifra NO se escribe aqui como verdad: se escribe como
# HIPOTESIS que el anclaje tiene que confirmar contra el documento. Si el
# articulo dice otra cosa, gana el articulo.
# ---------------------------------------------------------------------------

AFIRMACIONES = [
    {
        "clave": "renal-compuesto-dm",
        "pmcid": "PMC9491404",
        "cifra": "HR 0.66 (95% CI 0.58-0.75)",
        "pista": "kidney",
        "enunciado": ("En personas con enfermedad renal diabetica, agregar un inhibidor "
                      "de SGLT2 se asocia con menor riesgo del desenlace renal compuesto "
                      "frente a placebo, segun el metaanalisis anclado."),
        "intervencion": "inhibicion de SGLT2",
        "comparador": "placebo sobre tratamiento de base",
        "desenlace": "desenlace renal compuesto",
        "poblacion": Poblacion(
            condicion="enfermedad renal diabetica", edad_min=18,
            inclusion=["diabetes", "enfermedad renal cronica"],
            nivel_atencion="segundo nivel", pais_contexto="internacional"),
        "mecanismo": ["menor reabsorcion proximal de sodio",
                      "mas sodio en la macula densa",
                      "restauracion de la retroalimentacion tubuloglomerular",
                      "vasoconstriccion de la arteriola aferente",
                      "menor presion intraglomerular",
                      "menor hiperfiltracion glomerular"],
        "justificacion": Justificacion(
            OrigenSeleccion.EPIDEMIOLOGIA_MX,
            "la diabetes y la enfermedad renal cronica estan entre las primeras causas "
            "de mortalidad y de gasto en salud en Mexico", 0.95),
        "delta_mexico": ("PENDIENTE DE VERIFICAR: clave y disponibilidad en el Compendio "
                         "Nacional de Insumos para la Salud, y si esta disponible en "
                         "primer nivel o solo en segundo."),
        "trampa": ("Se confunde la caida inicial y reversible del filtrado glomerular, "
                   "que es el efecto hemodinamico esperado, con dano renal, y se suspende "
                   "el farmaco justo cuando esta funcionando."),
    },
    {
        "clave": "mortalidad-total-dm",
        "pmcid": "PMC9491404",
        "cifra": "HR 0.86 (95% CI 0.77-0.96)",
        "pista": "death",
        "enunciado": ("En la misma poblacion con enfermedad renal diabetica, el "
                      "metaanalisis anclado reporta menor mortalidad por cualquier causa "
                      "con un inhibidor de SGLT2 frente a placebo."),
        "intervencion": "inhibicion de SGLT2",
        "comparador": "placebo sobre tratamiento de base",
        "desenlace": "mortalidad por cualquier causa",
        "poblacion": Poblacion(
            condicion="enfermedad renal diabetica", edad_min=18,
            inclusion=["diabetes", "enfermedad renal cronica"],
            nivel_atencion="segundo nivel", pais_contexto="internacional"),
        "mecanismo": ["menor hiperfiltracion glomerular",
                      "menor progresion de la enfermedad renal",
                      "menor carga cardiovascular asociada a la uremia"],
        "justificacion": Justificacion(
            OrigenSeleccion.PERFIL_ENARM,
            "un desenlace duro de mortalidad es de los que mas se preguntan y de los que "
            "mas pesan al comparar intervenciones", 0.8),
        "delta_mexico": "PENDIENTE DE VERIFICAR.",
        "trampa": ("Se cita la reduccion de mortalidad como si fuera del mismo tamano que "
                   "la del desenlace renal; el intervalo de confianza de la mortalidad es "
                   "mas ancho y roza la unidad."),
    },
    {
        "clave": "renal-egfr-bajo",
        "pmcid": "PMC8591237",
        "cifra": "HR 0.70 (95% CI 0.58-0.83)",
        "pista": "",
        "enunciado": ("El beneficio renal de un inhibidor de SGLT2 se mantiene en el "
                      "subgrupo con filtrado glomerular estimado por debajo de 60, segun "
                      "el metaanalisis anclado."),
        "intervencion": "inhibicion de SGLT2",
        "comparador": "placebo",
        "desenlace": "desenlace renal primario con filtrado reducido",
        "poblacion": Poblacion(
            condicion="enfermedad renal cronica con filtrado estimado reducido",
            edad_min=18, inclusion=["filtrado glomerular estimado por debajo de 60"],
            nivel_atencion="segundo nivel", pais_contexto="internacional"),
        "mecanismo": ["menor presion intraglomerular",
                      "menor hiperfiltracion en las nefronas remanentes"],
        "justificacion": Justificacion(
            OrigenSeleccion.PRIMER_NIVEL,
            "el filtrado reducido es el escenario donde mas dudas hay sobre si conviene "
            "iniciar o suspender, y es donde el primer nivel refiere", 0.85),
        "delta_mexico": "PENDIENTE DE VERIFICAR.",
        "trampa": ("Se asume que a menor filtrado el beneficio desaparece, cuando lo que "
                   "cambia es el beneficio absoluto y no necesariamente el relativo."),
    },
    {
        "clave": "renal-macroalbuminuria",
        "pmcid": "PMC8591237",
        "cifra": "HR 0.57 (95% CI 0.48-0.67)",
        "pista": "",
        "enunciado": ("El beneficio renal es de mayor magnitud en el subgrupo con "
                      "macroalbuminuria, segun el metaanalisis anclado."),
        "intervencion": "inhibicion de SGLT2",
        "comparador": "placebo",
        "desenlace": "desenlace renal primario con macroalbuminuria",
        "poblacion": Poblacion(
            condicion="enfermedad renal cronica con macroalbuminuria", edad_min=18,
            inclusion=["cociente albumina creatinina elevado"],
            nivel_atencion="segundo nivel", pais_contexto="internacional"),
        "mecanismo": ["menor estres mecanico sobre la barrera de filtracion",
                      "menor albuminuria",
                      "menor dano tubulointersticial"],
        "justificacion": Justificacion(
            OrigenSeleccion.HUECO_DOCENTE,
            "la albuminuria como modificador del efecto, y no solo como marcador, es un "
            "punto que la ensenanza suele omitir", 0.8),
        "delta_mexico": "PENDIENTE DE VERIFICAR.",
        "trampa": ("Se trata la albuminuria solo como marcador pronostico y se pasa por "
                   "alto que tambien predice quien obtiene mas beneficio."),
    },
    {
        "clave": "progresion-renal-global",
        "pmcid": "PMC7613836",
        "cifra": "RR 0.63 (95% CI 0.58-0.69)",
        "pista": "progression",
        "enunciado": ("Agrupando los ensayos cardio-renales, la asignacion a un inhibidor "
                      "de SGLT2 se asocia con menor riesgo de progresion de la enfermedad "
                      "renal frente a placebo, con efecto similar con y sin diabetes."),
        "intervencion": "inhibicion de SGLT2",
        "comparador": "placebo",
        "desenlace": "progresion de la enfermedad renal",
        "poblacion": Poblacion(
            condicion="enfermedad renal cronica con y sin diabetes", edad_min=18,
            nivel_atencion="segundo nivel", pais_contexto="internacional"),
        "mecanismo": ["menor presion intraglomerular",
                      "menor hiperfiltracion glomerular",
                      "menor progresion de la enfermedad renal cronica"],
        "justificacion": Justificacion(
            OrigenSeleccion.DENSIDAD_ANCLA,
            "es la estimacion agrupada de mayor tamano y la que tiene mas evidencia "
            "primaria publica detras", 0.9),
        "delta_mexico": "PENDIENTE DE VERIFICAR.",
        "trampa": ("Se extrapola el efecto a poblaciones sin albuminuria, donde la "
                   "evidencia es mas escasa."),
    },
    # Caso de control: licencia CC BY-NC-ND. La compuerta debe rechazarlo ANTES
    # de leer el contenido, y asi se comprueba que la compuerta esta viva.
    {
        "clave": "control-licencia-rechazada",
        "pmcid": "PMC6518930",
        "cifra": "HR 0.66 (95% CI 0.58-0.75)",
        "pista": "",
        "enunciado": "Caso de control: este articulo no tiene licencia usable.",
        "intervencion": "control",
        "comparador": "",
        "desenlace": "control de la compuerta de licencias",
        "poblacion": Poblacion(condicion="control"),
        "mecanismo": [],
        "justificacion": Justificacion(OrigenSeleccion.DENSIDAD_ANCLA,
                                       "control negativo de la compuerta", 0.1),
        "delta_mexico": "",
        "trampa": "",
    },
]


def construir() -> dict:
    F = FetcherHTTP(cache_dir=CACHE)
    hechos: list[Hecho] = []
    bitacora_anclaje: list[dict] = []

    print("=" * 80)
    print("CONSTRUYENDO DOMINIO: inhibidores de SGLT2 en enfermedad renal cronica")
    print("fuente: PMC Cloud Service (s3://pmc-oa-opendata), en vivo")
    print("=" * 80)

    for af in AFIRMACIONES:
        hipotesis = p1(af["cifra"])
        if hipotesis is None:
            print(f"\n[{af['clave']}] la cifra hipotetica no se pudo parsear: omitido")
            continue

        print(f"\n[{af['clave']}]  {af['pmcid']}  hipotesis: {hipotesis}")
        r = anclar_en_articulo(af["pmcid"], hipotesis, F, pista=af["pista"])
        bitacora_anclaje.append({
            "clave": af["clave"], "pmcid": af["pmcid"],
            "verificada": r.ancla.verificada, "ruta": r.ruta,
            "motivo": r.motivo[:400], "licencia": r.ancla.licencia,
        })
        print(f"   anclaje: {'VERIFICADO' if r.ancla.verificada else 'NO'}  {r.motivo[:110]}")

        h = Hecho(
            enunciado=af["enunciado"], clase=ClaseHecho.EFECTO,
            poblacion=af["poblacion"],
            intervencion=af["intervencion"], comparador_clinico=af["comparador"],
            desenlace=af["desenlace"], mecanismo=af["mecanismo"],
            delta_mexico=af["delta_mexico"], trampa_enarm=af["trampa"],
            revisar_si=["aparece un ensayo de fase 3 nuevo en esta poblacion",
                        "el articulo anclado se retracta",
                        "cambia la version del articulo en el bucket de PMC"],
        )
        h.diagnostico["justificacion"] = af["justificacion"].dict()
        aplicar_anclaje(h, [r])

        # La elicitacion es la LECTURA del documento, no un recuerdo del modelo.
        elic = []
        if r.ancla.verificada and r.encontrado is not None:
            elic.append(Elicitacion(
                r.encontrado, Encuadre.DESDE_FUENTE, "extractor",
                texto_bruto=r.ancla.cita_corta, certeza=Certeza.RECUERDO_EXACTO,
                procedencia=Procedencia(estudio=af["pmcid"], registro=r.ancla.localizador),
            ))
        aplicar(h, elic, momento=HOY)
        print(f"   atestiguacion: {h.veredicto}  confianza {h.confianza}  "
              f"mostrable {h.se_muestra()}")
        if not h.se_muestra():
            print(f"      motivo: {h.mostrable()[1][:100]}")
        for a in h.diagnostico.get("alertas", []):
            print(f"      alerta: {a}")
        hechos.append(h)

    # ---- controles de independencia y de voz
    print("\n" + "=" * 80)
    print("CONTROLES")
    print("=" * 80)
    # Se ordena ANTES de revisar: la comprobacion de que el orden es derivado
    # compara el orden publicado contra el canonico, asi que revisar una lista en
    # orden de insercion reporta una divergencia que no existe en el producto.
    hechos = independencia.orden_canonico(hechos)
    rep_ind = independencia.revisar(hechos)
    print(f"independencia: {'limpio' if rep_ind.limpio else 'CON HALLAZGOS'}  "
          f"publicables {len(rep_ind.publicables)}  bloqueados {len(rep_ind.bloqueados)}")
    for hl in rep_ind.hallazgos:
        print(f"   [{hl.gravedad}] {hl.codigo}: {hl.detalle[:110]}")

    rep_voz = []
    for h in hechos:
        rv = voz.revisar(h.enunciado, referente=voz.Referente.POBLACION_PICO,
                         nombre_vista="derivacion_completa", muestra_derivacion=True,
                         anclas_visibles=len([a for a in h.anclas if a.verificada]))
        if not rep_voz and not rv.del_lado_educativo:
            pass
        rep_voz.append({"hecho": h.id(), "educativo": rv.del_lado_educativo,
                        "hallazgos": [x.dict() for x in rv.hallazgos]})
    malos = [x for x in rep_voz if not x["educativo"]]
    print(f"voz: {len(rep_voz) - len(malos)}/{len(rep_voz)} del lado educativo")
    for m in malos:
        print(f"   {m['hecho']}: {[h['codigo'] for h in m['hallazgos']]}")

    # ---- orden canonico, que es la disposicion propia de ORIONS
    publicables = [h for h in rep_ind.publicables if h.se_muestra()]
    ordenados = independencia.orden_canonico(publicables)
    print(f"\norden canonico ({len(ordenados)} hechos publicables, por magnitud de "
          f"efecto y luego precision):")
    for i, h in enumerate(ordenados, 1):
        print(f"   {i}. {h.magnitud}  {h.desenlace[:48]}")

    cola = cola_de_revision(hechos)
    print(f"\ncola de revision humana: {len(cola)} hechos")
    for h in cola:
        print(f"   [{h.veredicto}] {h.enunciado[:62]}...")

    return {
        "dominio": "inhibidores de SGLT2 en enfermedad renal cronica",
        "construido": HOY,
        "fuente_primaria": "PMC Cloud Service, s3://pmc-oa-opendata",
        "aviso_terminos": (
            "Los terminos del dataset de PMC obligan a mantener la version mas actual de "
            "los datos redistribuidos o a hacer constar que el producto puede no "
            "reflejarla. Se hace constar: este archivo es una instantanea del "
            f"{HOY} y puede no reflejar los datos mas actuales de la NLM."),
        "n_hechos": len(hechos),
        "n_publicables": len(ordenados),
        "anclaje": bitacora_anclaje,
        "independencia": rep_ind.dict(),
        "voz": rep_voz,
        "hechos_publicables": [h.dict() for h in ordenados],
        "cola_de_revision": [{"id": h.id(), "veredicto": h.veredicto,
                              "enunciado": h.enunciado,
                              "alertas": h.diagnostico.get("alertas", []),
                              "motivos": h.diagnostico.get("motivos", [])}
                             for h in cola],
    }


def main() -> int:
    datos = construir()
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"\nESCRITO: {SALIDA}")
    print(f"   {datos['n_publicables']} hechos publicables de {datos['n_hechos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
