"""Demostracion completa de la Boveda en un hecho real.

Reconstruye el hecho "un iSGLT2 reduce la progresion de la ERC" SIN tocar
ninguna guia con derechos reservados:

  - la cifra se ancla en el registro publico del ensayo y en la etiqueta del
    farmaco, ambos de dominio publico en Estados Unidos;
  - la cadena causal se escribe como grafo de fisiologia, no como parrafo;
  - la atestiguacion decide si la cifra es mostrable;
  - la pregunta de razonamiento se genera desde el grafo, con distractores
    tomados de la topologia.

ADVERTENCIA SOBRE LAS CIFRAS DE ESTE ARCHIVO
Los valores numericos y los identificadores que aparecen aqui son de DEMOSTRACION
del mecanismo del harness y NO estan verificados contra la fuente primaria: este
contenedor tiene bloqueado el acceso de red a clinicaltrials.gov y a api.fda.gov.
Antes de usar cualquier cifra de este archivo en produccion hay que correr el
anclaje real contra la fuente. El punto de la demostracion es el PIPELINE, no los
numeros.

Ejecutar:  python3 ejemplos/isglt2_nefroproteccion.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.numeros import parsear
from harness.hecho import Ancla, ClaseHecho, Hecho, Poblacion, TipoAncla
from harness.atestiguar import Elicitacion, Encuadre, SondaFalsa, aplicar, cola_de_revision
from harness.grafo import Arista, Grafo, Nivel, Nodo, Signo


def p1(t, **kw):
    r = parsear(t, **kw)
    return r[0] if r else None


# =============================================================== 1. EL GRAFO
def construir_grafo() -> tuple[Grafo, str, str]:
    """La cadena causal de la nefroproteccion por iSGLT2.

    Cada arista es una proposicion fisiologica verificable por separado. Ninguna
    reproduce la redaccion de una guia: son hechos de fisiologia renal.
    """
    g = Grafo()

    def N(nombre, nivel, variable="", unidad="", sin=None):
        return g.agregar_nodo(Nodo(nombre=nombre, nivel=nivel, variable=variable,
                                   unidad=unidad, sinonimos=sin or []))

    farmaco = N("inhibicion de SGLT2", Nivel.FARMACO,
                "ocupacion del cotransportador", sin=["dapagliflozina", "iSGLT2", "empagliflozina"])
    reabs = N("reabsorcion proximal de sodio", Nivel.CELULAR,
              "fraccion de sodio reabsorbido en el tubulo proximal", "%")
    na_md = N("sodio en la macula densa", Nivel.TISULAR,
              "concentracion de sodio en el aparato yuxtaglomerular", "mmol/L")
    tgf = N("retroalimentacion tubuloglomerular", Nivel.TISULAR,
            "tono de la senal adenosina/ATP")
    aferente = N("tono de la arteriola aferente", Nivel.ORGANO,
                 "resistencia arteriolar aferente")
    pig = N("presion intraglomerular", Nivel.ORGANO, "presion capilar glomerular", "mmHg")
    hiperf = N("hiperfiltracion glomerular", Nivel.ORGANO,
               "tasa de filtracion por nefrona", "nL/min")
    albu = N("albuminuria", Nivel.SISTEMICO, "cociente albumina/creatinina", "mg/g")
    progresion = N("progresion de la enfermedad renal cronica", Nivel.CLINICO,
                   "caida sostenida del eGFR", "mL/min/1.73m2/ano",
                   sin=["desenlace renal compuesto", "progresion renal"])

    # Nodos vecinos del mismo nivel: sirven de distractores plausibles y
    # representan vias reales que compiten por el mismo desenlace.
    glucosuria = N("glucosuria", Nivel.SISTEMICO, "glucosa urinaria", "g/dia")
    natriuresis = N("natriuresis", Nivel.SISTEMICO, "excrecion de sodio", "mmol/dia")
    volumen = N("volumen plasmatico", Nivel.SISTEMICO, "volumen intravascular", "mL")
    eritro = N("eritropoyesis", Nivel.SISTEMICO, "hematocrito", "%")
    cetonas = N("cuerpos cetonicos circulantes", Nivel.SISTEMICO, "beta-hidroxibutirato", "mmol/L")
    N("hipoxia tubular", Nivel.TISULAR, "demanda de oxigeno tubular")

    def A(o, d, signo, mecanismo, anclas=None, conf=0.8, lat=""):
        g.agregar_arista(Arista(origen=o, destino=d, signo=signo, mecanismo=mecanismo,
                                anclas=anclas or [], confianza=conf, latencia=lat,
                                contexto="ERC con albuminuria"))

    # ---- ruta hemodinamica principal
    A(farmaco, reabs, Signo.DISMINUYE,
      "bloqueo del cotransportador sodio-glucosa tipo 2 en el tubulo contorneado proximal",
      ["SPL:dapagliflozina:clinical_pharmacology"], 0.95, "horas")
    # Signo negativo: cuanto MAS se reabsorbe proximalmente, MENOS sodio llega
    # a la macula densa. Esta arista tenia el signo invertido en la primera
    # version escrita a mano y la detecto el auditor del grafo, no una persona.
    A(reabs, na_md, Signo.DISMINUYE,
      "lo que no se reabsorbe proximalmente llega distalmente al aparato yuxtaglomerular",
      [], 0.9, "horas")
    A(na_md, tgf, Signo.AUMENTA,
      "la macula densa detecta mas cloruro de sodio y libera adenosina", [], 0.85, "horas")
    A(tgf, aferente, Signo.AUMENTA,
      "la adenosina actua sobre receptores A1 y contrae la arteriola aferente", [], 0.85, "horas")
    A(aferente, pig, Signo.DISMINUYE,
      "mayor resistencia de entrada reduce la presion transmitida al capilar glomerular",
      [], 0.9, "dias")
    A(pig, hiperf, Signo.AUMENTA,
      "la filtracion por nefrona depende de la presion hidrostatica capilar", [], 0.9, "dias")
    A(hiperf, albu, Signo.AUMENTA,
      "el estres mecanico sostenido dana la barrera de filtracion", [], 0.85, "semanas")
    A(albu, progresion, Signo.AUMENTA,
      "la albuminuria es a la vez marcador y mediador de dano tubulointersticial",
      [], 0.8, "meses")

    # ---- rutas secundarias: compiten por el mismo desenlace
    A(farmaco, glucosuria, Signo.AUMENTA, "perdida renal de glucosa", [], 0.95, "horas")
    A(farmaco, natriuresis, Signo.AUMENTA, "sodio no reabsorbido excretado", [], 0.9, "horas")
    A(natriuresis, volumen, Signo.DISMINUYE, "diuresis osmotica y natriuresis", [], 0.85, "dias")
    A(volumen, progresion, Signo.AUMENTA,
      "la sobrecarga de volumen sostiene la hipertension glomerular", [], 0.6, "meses")
    A(farmaco, eritro, Signo.AUMENTA,
      "menor consumo de oxigeno del tubulo proximal restaura la produccion de eritropoyetina",
      [], 0.7, "semanas")
    A(farmaco, cetonas, Signo.AUMENTA,
      "cambio de sustrato hacia la oxidacion de acidos grasos", [], 0.75, "dias")

    return g, farmaco, progresion


# =============================================================== 2. EL HECHO
def construir_hecho() -> Hecho:
    """El hecho atomico, con sus anclas en fuentes publicas."""
    hr = p1("HR 0.61 (95% CI 0.51-0.72)")

    ancla_registro = Ancla(
        tipo=TipoAncla.REGISTRO_ENSAYO,
        localizador="NCT03036150",
        url="https://clinicaltrials.gov/study/NCT03036150",
        magnitud=hr,
        licencia="dominio publico (obra del gobierno de EEUU)",
        verificada=False,   # <-- FALSO a proposito: la red esta bloqueada aqui
    )
    ancla_etiqueta = Ancla(
        tipo=TipoAncla.ETIQUETA_REGULADOR,
        localizador="SPL:dapagliflozina:14.CLINICAL_STUDIES",
        url="https://api.fda.gov/drug/label.json?search=openfda.generic_name:dapagliflozin",
        magnitud=hr,
        licencia="dominio publico (etiqueta FDA)",
        verificada=False,
    )

    return Hecho(
        enunciado=("En adultos con enfermedad renal cronica y albuminuria, agregar un "
                   "inhibidor de SGLT2 al tratamiento de base reduce el riesgo del "
                   "desenlace renal compuesto frente a placebo."),
        clase=ClaseHecho.EFECTO,
        poblacion=Poblacion(
            condicion="enfermedad renal cronica con albuminuria",
            edad_min=18,
            inclusion=["eGFR reducido", "cociente albumina/creatinina elevado",
                       "tratamiento de base con bloqueo del sistema renina-angiotensina"],
            exclusion=["diabetes tipo 1", "enfermedad renal poliquistica"],
            nivel_atencion="segundo nivel",
            pais_contexto="internacional",
        ),
        magnitud=None,            # la fija la atestiguacion
        intervencion="inhibicion de SGLT2",
        comparador_clinico="placebo sobre tratamiento de base",
        desenlace="progresion de la enfermedad renal cronica",
        anclas=[ancla_registro, ancla_etiqueta],
        delta_mexico=("Verificar disponibilidad y clave en el Compendio Nacional de Insumos "
                      "para la Salud antes de ensenarlo como primera linea en primer nivel. "
                      "PENDIENTE DE VERIFICAR."),
        trampa_enarm=("Se confunde la caida inicial y reversible del eGFR, que es el efecto "
                      "hemodinamico esperado, con dano renal, y se suspende el farmaco justo "
                      "cuando esta funcionando."),
        revisar_si=["aparece un ensayo de fase 3 con desenlace renal en esta poblacion",
                    "cambia la etiqueta del regulador",
                    "se publica una revision sistematica viva que incluya datos nuevos"],
    )


# =============================================================== 3. ELICITACION
def elicitaciones_simuladas() -> tuple[list[Elicitacion], list[SondaFalsa]]:
    """Lo que en produccion devuelve el modelo por cada encuadre.

    Aqui esta simulado para que la demostracion sea deterministica y ejecutable
    sin red. En produccion cada entrada es una llamada real al modelo con su
    propio prompt, y la cuarta elicitacion es la que suele traer el error.
    """
    elic = [
        Elicitacion(p1("HR 0.61 (95% CI 0.51-0.72)"), Encuadre.DESDE_ENSAYO, "modelo-a",
                    "el desenlace renal compuesto mostro HR 0.61"),
        Elicitacion(p1("hazard ratio de 0,61"), Encuadre.DIRECTO, "modelo-a"),
        Elicitacion(p1("reduccion del riesgo relativo del 39%"), Encuadre.COMPLEMENTO, "modelo-b"),
        Elicitacion(p1("HR 0.61"), Encuadre.SIN_OPCIONES, "modelo-b"),
        Elicitacion(p1("HR 0.63"), Encuadre.DESDE_FUENTE, "modelo-c",
                    "extraido del resumen recuperado"),
    ]
    sondas = [
        SondaFalsa(valor_falso=p1("HR 0.85"), acepto=False, corrigio_a=p1("HR 0.61"),
                   texto_bruto="no, ese valor no corresponde al desenlace renal primario"),
        SondaFalsa(valor_falso=p1("HR 1.20"), acepto=False, corrigio_a=p1("HR 0.61"),
                   texto_bruto="no, el efecto fue protector, no de dano"),
    ]
    return elic, sondas


# =============================================================== 4. CORRIDA
def main() -> int:
    print("=" * 78)
    print("BOVEDA ORIONS - demostracion del pipeline en un hecho real")
    print("=" * 78)

    g, n_farmaco, n_progresion = construir_grafo()
    print(f"\n[1] GRAFO DE MECANISMOS: {len(g.nodos)} nodos, {len(g.aristas)} aristas")

    rutas = g.rutas(n_farmaco, n_progresion)
    print(f"    rutas de la intervencion al desenlace: {len(rutas)}")
    for r in rutas:
        signo = "protege" if r.signo < 0 else "empeora"
        print(f"      - {len(r)} pasos, signo neto {r.signo:+d} ({signo}), "
              f"confianza {r.confianza:.2f}")

    mejor = g.mejor_ruta(n_farmaco, n_progresion)
    print("\n[2] CADENA CAUSAL DE LA MEJOR RUTA")
    print("    " + g.explicar(mejor).replace("\n", "\n    "))

    print("\n[3] AUDITORIA AUTOMATICA DEL GRAFO")
    h = construir_hecho()
    elic, sondas = elicitaciones_simuladas()
    aplicar(h, elic, sondas)
    contras = g.contradicciones([h])
    if not contras:
        print("    grafo coherente: sin contradicciones")
    for c in contras:
        print(f"    [{c.gravedad:>5}] {c.tipo.value}: {c.detalle}")

    print("\n[3b] EL AUDITOR FUNCIONA: se invierte una arista a proposito")
    # Este bloque no es decorativo. Cuando esta cadena se escribio a mano por
    # primera vez, TRES aristas tenian el signo invertido (reabsorcion a macula
    # densa, presion intraglomerular a hiperfiltracion, e hiperfiltracion a
    # albuminuria). El producto de signos daba +1, es decir que el farmaco
    # empeoraria la ERC, en contradiccion con el HR 0.61 anclado. Ninguna
    # persona lo noto: lo detecto esta funcion. Es el control que hace auditable
    # un grafo construido con ayuda de un modelo.
    arista_pig = next(a for a in g.aristas.values()
                      if a.origen == g.nodo_por_nombre("presion intraglomerular").id()
                      and a.destino == g.nodo_por_nombre("hiperfiltracion glomerular").id())
    arista_pig.signo = Signo.DISMINUYE
    for c in g.contradicciones([h]):
        print(f"    [{c.gravedad:>5}] {c.tipo.value}: {c.detalle[:150]}")
    arista_pig.signo = Signo.AUMENTA   # se restaura

    print("\n[4] ATESTIGUACION DEL HECHO")
    d = h.diagnostico
    print(f"    id del hecho:      {h.id()}")
    print(f"    veredicto:         {h.veredicto}")
    print(f"    confianza:         {h.confianza}")
    print(f"    magnitud consenso: {h.magnitud}")
    print(f"    elicitaciones:     {d['n_elicitaciones']} en {d['n_encuadres']} encuadres")
    print(f"    cuota de consenso: {d['cuota_consenso']:.0%}")
    print(f"    anclas verificadas:{d['anclas_verificadas']}  (techo: {h.techo()})")
    print(f"    mostrable:         {h.mostrable()}")
    print(f"    huella:            {h.huella()}")
    for m in d["motivos"]:
        print(f"    motivo:            {m}")
    for a in d["alertas"]:
        print(f"    ALERTA:            {a}")
    print(f"    grupos de consenso:{d['grupos']}")

    print("\n[5] QUE PASA SI SE VERIFICAN LAS ANCLAS (lo que hara el anclador real)")
    for a in h.anclas:
        a.verificada = True
    aplicar(h, elic, sondas)
    print(f"    veredicto: {h.veredicto}   confianza: {h.confianza}   "
          f"mostrable: {h.mostrable()}")
    print(f"    motivo:    {h.diagnostico['motivos'][0]}")

    print("\n[6] PREGUNTA GENERADA DESDE EL GRAFO")
    for pos in (2, 4):
        q = g.pregunta_de_ruta(mejor, posicion=pos)
        if not q:
            continue
        print(f"\n    (dificultad {q['dificultad']}/5) {q['enunciado']}")
        for i, op in enumerate(q["opciones"]):
            marca = " <- correcta" if op == q["correcta"] else ""
            print(f"       {chr(97 + i)}) {op}{marca}")

    print("\n[7] COLA DE REVISION HUMANA")
    h2 = construir_hecho()
    h2.enunciado = "Dosis diaria de dapagliflozina para nefroproteccion en la ERC."
    h2.desenlace = "dosis diaria"
    aplicar(h2, [
        Elicitacion(p1("10 mg al dia"), Encuadre.DIRECTO),
        Elicitacion(p1("10 mg una vez al dia"), Encuadre.DESDE_FUENTE),
        Elicitacion(p1("100 mg al dia"), Encuadre.DESDE_ENSAYO),
        Elicitacion(p1("10 mg diarios"), Encuadre.SIN_OPCIONES),
    ])
    h2.clase = ClaseHecho.DOSIS
    cola = cola_de_revision([h, h2])
    print(f"    hechos que requieren ojo humano: {len(cola)}")
    for x in cola:
        print(f"      [{x.veredicto}] {x.enunciado[:62]}...")
        for al in x.diagnostico.get("alertas", []):
            print(f"              alerta: {al}")

    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "isglt2_nefroproteccion.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({
            "hecho": h.dict(),
            "grafo": g.dict(),
            "ruta_principal": {
                "nodos": [g.nodos[n].nombre for n in mejor.nodos],
                "signo_neto": mejor.signo,
                "confianza": mejor.confianza,
                "explicacion": g.explicar(mejor),
            },
            "contradicciones": [c.dict() for c in contras],
            "aviso": ("cifras e identificadores NO verificados contra la fuente primaria: "
                      "demostracion del pipeline, no contenido de produccion"),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[8] ESCRITO: {salida}")
    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
