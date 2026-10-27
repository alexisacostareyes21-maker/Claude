"""Grafo de mecanismos: la fisiologia causal cuantificada.

Las guias publican la conclusion con una etiqueta de clase y nivel. Lo que no
publica nadie, en forma computable, es la CADENA CAUSAL que lleva de la
intervencion al desenlace:

    inhibicion de SGLT2
      -> (menos) reabsorcion proximal de sodio
      -> (mas) sodio en la macula densa
      -> (restaura) retroalimentacion tubuloglomerular
      -> (mas) vasoconstriccion de la arteriola aferente
      -> (menos) presion intraglomerular
      -> (menos) hiperfiltracion
      -> (menos) progresion de la ERC

Guardar esto como grafo, y no como parrafo, da cuatro cosas que un texto no da:

1. VERIFICABILIDAD. El producto de los signos de una ruta predice la direccion
   del efecto. Si un Hecho dice que la intervencion empeora el desenlace y la
   ruta predice que lo mejora, hay una contradiccion detectable por codigo. Eso
   atrapa a la vez hechos mal extraidos y mecanismos mal escritos.

2. EXPLICACION. ORIONS puede responder "por que" recorriendo la ruta, en vez de
   generar una justificacion plausible y no auditada.

3. DISTRACTORES DURISIMOS. Las opciones falsas de una pregunta salen de la
   topologia del grafo: nodos del mismo nivel de organizacion y a la misma
   distancia del origen, pero fuera de la ruta. Son plausibles porque son
   fisiologicamente vecinos, no porque un modelo los haya inventado.

4. TRANSFERENCIA. Un mecanismo aprendido en un dominio aparece en otro. El grafo
   lo hace explicito: la misma arista de vasoconstriccion aferente sirve para
   iSGLT2, para AINE y para estenosis de la arteria renal.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Iterable, Optional

from .numeros import Magnitud


class Nivel(str, Enum):
    """Nivel de organizacion biologica. Ordena el grafo y acota los distractores."""

    MOLECULAR = "molecular"
    CELULAR = "celular"
    TISULAR = "tisular"
    ORGANO = "organo"
    SISTEMICO = "sistemico"
    CLINICO = "clinico"          # desenlace que le pasa al paciente
    FARMACO = "farmaco"          # la intervencion


class Signo(int, Enum):
    AUMENTA = 1
    DISMINUYE = -1


@dataclass
class Nodo:
    """Una variable fisiologica que puede subir o bajar."""

    nombre: str
    nivel: Nivel
    variable: str = ""           # que se mide exactamente
    unidad: str = ""
    sinonimos: list[str] = field(default_factory=list)

    def id(self) -> str:
        return "N" + hashlib.sha256(self.nombre.lower().strip().encode()).hexdigest()[:12]

    def dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id()
        d["nivel"] = self.nivel.value
        return d


@dataclass
class Arista:
    """Una relacion causal dirigida y con signo entre dos variables.

    `magnitud_relativa` es opcional a proposito: la mayoria de las aristas
    fisiologicas se conocen en direccion pero no en tamano. Pedir un numero
    donde no existe obliga a inventarlo, y el grafo prefiere un hueco honesto.
    """

    origen: str                  # id de Nodo
    destino: str                 # id de Nodo
    signo: Signo
    mecanismo: str = ""          # como ocurre, en una linea
    magnitud_relativa: Optional[Magnitud] = None
    latencia: str = ""           # minutos, dias, meses
    contexto: str = ""           # poblacion o condicion donde aplica
    anclas: list[str] = field(default_factory=list)   # localizadores
    confianza: float = 0.5       # 0 a 1
    hechos: list[str] = field(default_factory=list)   # ids de Hecho que la sostienen

    def id(self) -> str:
        semilla = f"{self.origen}>{self.destino}>{self.signo.value}>{self.contexto.lower()}"
        return "A" + hashlib.sha256(semilla.encode()).hexdigest()[:12]

    def dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id()
        d["signo"] = self.signo.value
        d["magnitud_relativa"] = self.magnitud_relativa.dict() if self.magnitud_relativa else None
        return d


@dataclass
class Ruta:
    nodos: list[str]
    aristas: list[Arista]

    @property
    def signo(self) -> int:
        """Producto de los signos: la direccion neta del efecto.

        Dos "disminuye" seguidos dan un "aumenta". Es la regla que permite
        auditar una cadena de mecanismos sin leerla.
        """
        s = 1
        for a in self.aristas:
            s *= a.signo.value
        return s

    @property
    def confianza(self) -> float:
        """La ruta no es mas fuerte que su arista mas debil."""
        return min((a.confianza for a in self.aristas), default=0.0)

    def __len__(self) -> int:
        return len(self.aristas)


class TipoContradiccion(str, Enum):
    ARISTAS_OPUESTAS = "aristas_opuestas"       # dos aristas contrarias en el mismo contexto
    RUTAS_OPUESTAS = "rutas_opuestas"           # dos rutas con signo neto contrario
    HECHO_CONTRA_RUTA = "hecho_contra_ruta"     # un hecho observado contradice la prediccion
    CICLO_POSITIVO = "ciclo_positivo"           # retroalimentacion amplificadora


@dataclass
class Contradiccion:
    tipo: TipoContradiccion
    detalle: str
    implicados: list[str] = field(default_factory=list)
    gravedad: str = "media"      # baja, media, alta

    def dict(self) -> dict:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d


class Grafo:
    """El grafo de mecanismos de la Boveda."""

    def __init__(self) -> None:
        self.nodos: dict[str, Nodo] = {}
        self.aristas: dict[str, Arista] = {}
        self._salientes: dict[str, list[str]] = {}
        self._entrantes: dict[str, list[str]] = {}

    # ---------------------------------------------------------------- construccion
    def agregar_nodo(self, n: Nodo) -> str:
        self.nodos[n.id()] = n
        self._salientes.setdefault(n.id(), [])
        self._entrantes.setdefault(n.id(), [])
        return n.id()

    def agregar_arista(self, a: Arista) -> str:
        if a.origen not in self.nodos or a.destino not in self.nodos:
            raise KeyError("la arista referencia un nodo que no esta en el grafo")
        aid = a.id()
        self.aristas[aid] = a
        self._salientes[a.origen].append(aid)
        self._entrantes[a.destino].append(aid)
        return aid

    def nodo_por_nombre(self, nombre: str) -> Optional[Nodo]:
        clave = nombre.lower().strip()
        for n in self.nodos.values():
            if n.nombre.lower().strip() == clave or clave in [s.lower().strip() for s in n.sinonimos]:
                return n
        return None

    # ---------------------------------------------------------------- recorrido
    def rutas(self, origen: str, destino: str, max_largo: int = 8) -> list[Ruta]:
        """Todas las rutas simples de origen a destino, de la mas corta a la mas larga.

        Rutas simples: no revisita nodos. Los ciclos existen en fisiologia y se
        analizan aparte, en `ciclos()`, no se mezclan con las rutas causales.
        """
        encontradas: list[Ruta] = []

        def dfs(actual: str, camino_n: list[str], camino_a: list[Arista]) -> None:
            if len(camino_a) > max_largo:
                return
            if actual == destino and camino_a:
                encontradas.append(Ruta(list(camino_n), list(camino_a)))
                return
            for aid in self._salientes.get(actual, []):
                a = self.aristas[aid]
                # No se revisita un nodo, con una excepcion: el nodo destino.
                # Sin ella, una busqueda de origen a si mismo nunca podria
                # cerrar el ciclo, porque la arista de retorno apunta a un nodo
                # que ya esta en el camino.
                if a.destino in camino_n and a.destino != destino:
                    continue
                camino_n.append(a.destino)
                camino_a.append(a)
                dfs(a.destino, camino_n, camino_a)
                camino_n.pop()
                camino_a.pop()

        dfs(origen, [origen], [])
        encontradas.sort(key=lambda r: (len(r), -r.confianza))
        return encontradas

    def mejor_ruta(self, origen: str, destino: str, max_largo: int = 8) -> Optional[Ruta]:
        """La ruta mas confiable; a igual confianza, la mas corta."""
        rs = self.rutas(origen, destino, max_largo)
        if not rs:
            return None
        return max(rs, key=lambda r: (round(r.confianza, 3), -len(r)))

    def ciclos(self, max_largo: int = 8) -> list[Ruta]:
        """Bucles de retroalimentacion.

        No son errores: el eje renina-angiotensina-aldosterona y el barorreflejo
        son ciclos. Lo que importa es su signo. Producto negativo es
        retroalimentacion estabilizadora; producto positivo es amplificadora y
        merece revision, porque en fisiologia casi siempre indica una arista
        con el signo invertido.
        """
        vistos: set[tuple] = set()
        out: list[Ruta] = []
        for nid in self.nodos:
            for r in self.rutas(nid, nid, max_largo):
                clave = tuple(sorted(a.id() for a in r.aristas))
                if clave in vistos:
                    continue
                vistos.add(clave)
                out.append(r)
        return out

    # ---------------------------------------------------------------- auditoria
    def contradicciones(self, hechos: Iterable = ()) -> list[Contradiccion]:
        """Encuentra inconsistencias por codigo, sin leer el texto.

        Este es el control que hace auditable un grafo construido con ayuda de
        un modelo: no se confia en que la cadena este bien escrita, se verifica
        que sea coherente consigo misma y con los hechos anclados.
        """
        out: list[Contradiccion] = []

        # 1. Aristas paralelas con signo opuesto en el mismo contexto.
        por_par: dict[tuple, list[Arista]] = {}
        for a in self.aristas.values():
            por_par.setdefault((a.origen, a.destino, a.contexto.lower().strip()), []).append(a)
        for (o, d, ctx), lista in por_par.items():
            signos = {a.signo.value for a in lista}
            if len(signos) > 1:
                out.append(Contradiccion(
                    tipo=TipoContradiccion.ARISTAS_OPUESTAS,
                    detalle=(f"{self._nombre(o)} -> {self._nombre(d)} tiene aristas con signo "
                             f"opuesto en el contexto '{ctx or 'general'}'"),
                    implicados=[a.id() for a in lista],
                    gravedad="alta",
                ))

        # 2. Ciclos de retroalimentacion positiva.
        for c in self.ciclos():
            if c.signo > 0:
                out.append(Contradiccion(
                    tipo=TipoContradiccion.CICLO_POSITIVO,
                    detalle=("ciclo con retroalimentacion amplificadora: "
                             + " -> ".join(self._nombre(n) for n in c.nodos)),
                    implicados=[a.id() for a in c.aristas],
                    gravedad="media",
                ))

        # 3. Rutas con signo neto opuesto entre el mismo par de nodos.
        # Solo se evaluan los pares clinicamente interesantes (de una
        # intervencion a un desenlace): recorrer todos los pares seria O(n^2)
        # busquedas en profundidad y no aporta nada.
        origenes = [nid for nid, nd in self.nodos.items()
                    if nd.nivel in (Nivel.FARMACO, Nivel.MOLECULAR)]
        destinos = [nid for nid, nd in self.nodos.items() if nd.nivel is Nivel.CLINICO]
        for o in origenes:
            for d in destinos:
                if o == d:
                    continue
                rs = self.rutas(o, d, max_largo=6)
                if len(rs) < 2:
                    continue
                if len({r.signo for r in rs}) > 1:
                    out.append(Contradiccion(
                        tipo=TipoContradiccion.RUTAS_OPUESTAS,
                        detalle=(f"hay rutas de signo opuesto entre {self._nombre(o)} y "
                                 f"{self._nombre(d)}: el efecto neto depende de cual domine, "
                                 f"y el grafo no lo dice"),
                        implicados=[o, d],
                        gravedad="baja",
                    ))

        # 4. Un hecho observado que contradice la prediccion de la ruta.
        for h in hechos:
            signo_obs = _signo_observado(h)
            if signo_obs == 0:
                continue
            no = self.nodo_por_nombre(getattr(h, "intervencion", "") or "")
            nd = self.nodo_por_nombre(getattr(h, "desenlace", "") or "")
            if not no or not nd:
                continue
            r = self.mejor_ruta(no.id(), nd.id())
            if r is None:
                continue
            if r.signo != signo_obs:
                out.append(Contradiccion(
                    tipo=TipoContradiccion.HECHO_CONTRA_RUTA,
                    detalle=(f"el hecho observado apunta a signo {signo_obs:+d} pero la ruta "
                             f"de mecanismos predice {r.signo:+d}: "
                             + " -> ".join(self._nombre(n) for n in r.nodos)),
                    implicados=[h.id()] + [a.id() for a in r.aristas],
                    gravedad="alta",
                ))
        return out

    def _nombre(self, nid: str) -> str:
        n = self.nodos.get(nid)
        return n.nombre if n else nid

    # ---------------------------------------------------------------- explicacion
    def explicar(self, ruta: Ruta) -> str:
        """Convierte una ruta en prosa auditable.

        Lo que ORIONS muestra como "por que" sale de aqui, no de una generacion
        libre: cada paso corresponde a una arista con su ancla.
        """
        verbos = {1: "aumenta", -1: "disminuye"}
        lineas = []
        for i, a in enumerate(ruta.aristas, 1):
            mec = f" ({a.mecanismo})" if a.mecanismo else ""
            lat = f" [{a.latencia}]" if a.latencia else ""
            lineas.append(
                f"{i}. {self._nombre(a.origen)} {verbos[a.signo.value]} "
                f"{self._nombre(a.destino)}{mec}{lat}"
            )
        neto = "aumenta" if ruta.signo > 0 else "disminuye"
        lineas.append(
            f"Efecto neto: {self._nombre(ruta.nodos[0])} {neto} "
            f"{self._nombre(ruta.nodos[-1])} (confianza de la ruta {ruta.confianza:.2f})"
        )
        return "\n".join(lineas)

    # ---------------------------------------------------------------- pedagogia
    def distractores(self, nodo_correcto: str, ruta: Ruta, n: int = 3) -> list[str]:
        """Opciones falsas plausibles tomadas de la topologia del grafo.

        Un distractor es bueno cuando el estudiante tiene que razonar para
        descartarlo. Los mejores candidatos son nodos del MISMO nivel de
        organizacion, conectados al grafo, pero fuera de la ruta correcta: son
        vecinos fisiologicos, no ruido.
        """
        correcto = self.nodos.get(nodo_correcto)
        if not correcto:
            return []
        en_ruta = set(ruta.nodos)
        mismo_nivel = [
            nid for nid, nd in self.nodos.items()
            if nd.nivel is correcto.nivel and nid not in en_ruta
        ]
        # prefiere los que tienen grado alto: estan mas integrados y enganan mejor
        mismo_nivel.sort(key=lambda nid: -(len(self._salientes.get(nid, []))
                                           + len(self._entrantes.get(nid, []))))
        if len(mismo_nivel) < n:
            otros = [nid for nid in self.nodos
                     if nid not in en_ruta and nid not in mismo_nivel]
            otros.sort(key=lambda nid: -(len(self._salientes.get(nid, []))
                                         + len(self._entrantes.get(nid, []))))
            mismo_nivel += otros
        return [self.nodos[nid].nombre for nid in mismo_nivel[:n]]

    def pregunta_de_ruta(self, ruta: Ruta, posicion: int = 1,
                         n_distractores: int = 3) -> Optional[dict]:
        """Genera un item de razonamiento ocultando un paso intermedio de la ruta.

        La dificultad no se declara a mano: sale de la longitud de la ruta, del
        nivel de organizacion del paso oculto y de la confianza de la arista.
        """
        if posicion < 1 or posicion >= len(ruta.nodos) - 1:
            return None
        oculto = ruta.nodos[posicion]
        nodo = self.nodos.get(oculto)
        if not nodo:
            return None
        antes = self._nombre(ruta.nodos[posicion - 1])
        despues = self._nombre(ruta.nodos[posicion + 1])
        a_in = ruta.aristas[posicion - 1]
        a_out = ruta.aristas[posicion]
        verbos = {1: "aumenta", -1: "disminuye"}
        opciones = [nodo.nombre] + self.distractores(oculto, ruta, n_distractores)
        peso_nivel = {
            Nivel.MOLECULAR: 3, Nivel.CELULAR: 3, Nivel.TISULAR: 2,
            Nivel.ORGANO: 2, Nivel.SISTEMICO: 1, Nivel.CLINICO: 1, Nivel.FARMACO: 1,
        }
        dificultad = min(5, max(1, round(
            1 + 0.4 * len(ruta) + peso_nivel.get(nodo.nivel, 2) * 0.6
            - 1.5 * ruta.confianza
        )))
        return {
            "enunciado": (f"{antes} {verbos[a_in.signo.value]} un paso intermedio que, a su vez, "
                          f"{verbos[a_out.signo.value]} {despues}. Cual es ese paso?"),
            "correcta": nodo.nombre,
            "opciones": opciones,
            "dificultad": dificultad,
            "explicacion": self.explicar(ruta),
            "aristas": [a_in.id(), a_out.id()],
            "anclas": sorted(set(a_in.anclas) | set(a_out.anclas)),
            "nivel_cognitivo": "razonamiento_mecanistico",
        }

    # ---------------------------------------------------------------- io
    def dict(self) -> dict:
        return {
            "nodos": [n.dict() for n in self.nodos.values()],
            "aristas": [a.dict() for a in self.aristas.values()],
        }


def _signo_observado(h) -> int:
    """Deduce la direccion del efecto que afirma un Hecho.

    Para razones de riesgo: menor que 1 significa que la intervencion reduce el
    desenlace. Si el desenlace es malo (progresion, muerte), reducirlo es el
    beneficio esperado, y el signo del efecto sobre ESA variable es negativo.
    """
    m = getattr(h, "magnitud", None)
    if m is None:
        return 0
    clase = m.clase.value if hasattr(m.clase, "value") else str(m.clase)
    if clase == "razon_riesgo":
        if m.valor < 0.97:
            return -1
        if m.valor > 1.03:
            return 1
        return 0
    if clase in ("reduccion_relativa", "reduccion_absoluta"):
        return -1 if m.valor > 0 else 0
    return 0


__all__ = [
    "Grafo", "Nodo", "Arista", "Ruta", "Nivel", "Signo",
    "Contradiccion", "TipoContradiccion",
]
