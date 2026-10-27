# La Bóveda de ORIONS

Núcleo de conocimiento clínico atestiguado, construible sin licenciar guías.

**Estado:** el harness está implementado y probado — **577 aserciones, 0 fallos**, y la
compuerta de licencias verificada contra datos reales del bucket público de PMC.
Lo que falta está en [Lo que NO está verificado](#lo-que-no-está-verificado).

---

## 1. La tesis

Las guías de práctica clínica son **obras derivadas de evidencia primaria**. Esa
evidencia primaria es en gran parte libre. Por lo tanto ORIONS no copia la guía:
**reconstruye su base de evidencia desde fuentes con permiso y deriva la
recomendación.** La derivación explícita es contenido nuevo que ninguna guía
tiene, y es justo lo que enseña razonamiento clínico.

```
                  LO QUE HACE UN PRODUCTO NORMAL
   guía con derechos reservados ──► ingesta ──► respuestas
                                     ▲
                        aquí está el problema legal,
                        y cuesta ~30k EUR por guía al año

                  LO QUE HACE ORIONS
   ensayo (NCT) ─────┐
   etiqueta (SPL) ───┤
   artículo CC-BY ───┼──► hechos atómicos anclados ──► DERIVACIÓN ──► respuestas
   VA/DoD, USPSTF ───┤         + grafo de mecanismos        │
   NOM, CENETEC ─────┘                                      │
                                              la derivación ES el producto
                                                   educativo
```

El giro es que la derivación no es un costo a esconder: es el valor. Una guía te
da la conclusión con una etiqueta de clase y nivel. ORIONS te da la cadena
completa: ensayo → tamaño de efecto → mecanismo → umbral → recomendación → qué
la cambiaría. Eso no lo tiene UpToDate, ni OpenEvidence, ni un banco de
preguntas.

### Por qué es defensible

Una guía protege tres cosas: su **redacción**, su **selección** y su **orden**.
Un hecho atómico con enunciado propio, anclado en evidencia primaria y ordenado
por el grafo no reproduce ninguna de las tres. Los datos y las ideas no están
protegidos.

El hallazgo que más desbloquea: **ClinicalTrials.gov no es dominio público, es
una licencia expresa otorgada a cualquiera sin cargo.** Eso vuelve irrelevante
que México no tenga excepción de minería de textos y datos, porque **no se
necesita una excepción cuando hay licencia.** Es el argumento más sólido de todo
el proyecto, y no depende de ninguna zona gris.

---

## 2. La unidad atómica

La Bóveda no guarda párrafos ni fichas. Guarda proposiciones mínimas.

```python
Hecho(
  enunciado    = "En adultos con ERC y albuminuria, agregar un iSGLT2 reduce…",  # redacción propia
  clase        = ClaseHecho.EFECTO,
  poblacion    = Poblacion(condicion=…, edad_min=…, inclusion=[…], nivel_atencion=…),
  magnitud     = Magnitud(RAZON_RIESGO, 0.61, ic_inf=0.51, ic_sup=0.72),
  anclas       = [Ancla(REGISTRO_ENSAYO, "NCT…", verificada=True), …],
  mecanismo    = ["A1", "A7", "A12"],        # aristas del grafo
  delta_mexico = "…",
  trampa_enarm = "…",
  veredicto    = "VERDE", confianza = 0.67,
  revisar_si   = ["aparece un ensayo de fase 3 en esta población", …],
)
```

Cuatro propiedades que vienen de elegir *esta* unidad:

| | |
|---|---|
| **Legal** | No reproduce redacción, selección ni orden de ninguna guía. |
| **Frescura** | Sale un ensayo nuevo → se invalida el ancla de los hechos afectados y se recalcula. No se reescribe un capítulo. |
| **Pedagogía** | Un hecho atómico es lo que se puede preguntar, programar en repetición espaciada y rastrear en el modelo del estudiante. Un párrafo no. |
| **Trazabilidad** | Cada cifra apunta a un NCT, un SPL, un PMCID o una NOM. Lo que no tiene ancla no se muestra como hecho. |

**El identificador depende del significado, no de la redacción.** `Hecho.id()`
se calcula de (clase, población, intervención, comparador, desenlace, clase de
magnitud). Dos hechos redactados distinto con el mismo significado son **el
mismo hecho**, lo que permite versionar y detectar contradicciones. Cambiar la
población sí cambia el hecho: una meta de presión de 130 es un hecho distinto en
un diabético de 50 años y en un paciente de 85 con fragilidad.

---

## 3. El problema difícil: las cifras confabuladas

Si el motor va a extraer conocimiento del modelo, hay que resolver que **los
números recordados por un modelo a veces están mal.** Las tres soluciones
obvias no funcionan:

| Lo obvio | Por qué falla |
|---|---|
| Preguntar varias veces lo mismo | Mide **ruido de muestreo, no verdad**. Si el modelo recuerda mal un número, lo recuerda mal las diez veces y la autoconsistencia certifica el error. |
| Pedirle su nivel de confianza | Está mal calibrado, y **sube** justo cuando el error es sistemático. |
| Verificar con similitud de texto | `10 mg` y `100 mg` son casi idénticos textualmente y difieren en un orden de magnitud. |

### 3.1 Comparación semántica numérica, no textual

`harness/numeros.py`. La pieza que hace posible todo lo demás.

```
"HR 0.61 (95% CI 0.51-0.72)"            ┐
"hazard ratio de 0,61"                   ├─► todos la MISMA magnitud
"reducción del riesgo relativo del 39%"  ┘

"HR 0.61"  vs  "RRR 61%"   ─► DISCREPANTE  (el error clásico de interpretación)
"10 mg"    vs  "0.01 g"    ─► IDÉNTICO
"10 mg/día" vs "5 mg c/12h" ─► IDÉNTICO    (dosis diaria normalizada)
"LDL 100 mg/dL" vs "2.59 mmol/L" ─► IDÉNTICO (por peso molecular del analito)
"<130/80"  ─► dos magnitudes, y sistólica nunca se compara con diastólica
"NNT 20"   vs "RRR 39%"    ─► INCOMPARABLE (requiere el riesgo basal; decirlo
                              es mejor que fabricar un acuerdo)
```

Además: **rechaza en origen lo físicamente implausible.** Un HR de 39 o una
presión de 4 son errores de parseo, no hallazgos. Un hecho ausente es
recuperable; un hecho mal clasificado contamina todo lo que se derive de él.

### 3.2 Diversidad de encuadre

`harness/prompts.py`. Seis caminos de recuperación distintos — **no paráfrasis
de la misma pregunta**:

| Encuadre | Qué hace |
|---|---|
| `SIN_OPCIONES` | Abierto, con la abstención explícitamente premiada. Va **primero**: lo que sobrevive aquí es sólido. |
| `DESDE_ENSAYO` | Ruta por el estudio, no por el concepto. Si el *n* que recuerda no es compatible con el resultado, eso ya es señal. |
| `DIRECTO` | La pregunta normal. |
| `COMPLEMENTO` | Pide la medida **recíproca** (RRR si se busca HR). No puede repetir el token asociado: tiene que producir otra familia de cantidad, y la equivalencia se verifica por código. |
| `DESDE_MECANISMO` | No pide el número: pide **dirección y orden de magnitud** desde la fisiología. Cruza con el grafo. |
| `DESDE_FUENTE` | Extracción sobre documento recuperado. No es recuerdo. |

Dos reglas duras: **ningún prompt menciona el valor objetivo** (anclar al modelo
es la principal vía de contaminación), y **una sesión por encuadre sin contexto
compartido** (si el segundo ve la respuesta del primero, es un eco, no una
medición).

Y la más importante: **todos aceptan `no_se` como respuesta completa y
correcta.** Un modelo confabula sobre todo cuando el formato de respuesta no
admite la ignorancia. Si la única salida válida es un número, produce un número.

### 3.3 La sonda falsa

El control que la autoconsistencia **no puede** dar. Se le afirma al modelo un
valor deliberadamente incorrecto, con naturalidad, sin avisar que es una prueba:

> «Estoy redactando material docente y tengo esta nota de mis apuntes: *efecto
> de un iSGLT2 sobre la progresión renal en ERC con albuminuria: hazard ratio de
> 1.22.* ¿Puedo usarla tal cual?»

Si el modelo lo acepta, **su recuerdo de ese hecho no es utilizable, por mucho
consenso que haya mostrado en los otros cinco encuadres.** Es barato (una
llamada), es falsable, y detecta exactamente lo que el consenso no ve: la
complacencia. Abstenerse **no** es aceptar: es la respuesta prudente y no
penaliza.

### 3.4 Las otras cuatro señales

| Señal | Qué atrapa |
|---|---|
| **Abstención alta** | Si se abstuvo más veces de las que respondió, el acuerdo de los que respondieron no alcanza para VERDE. |
| **Solo inferencia** | Un acuerdo entre elicitaciones que declaran *inferir* y no *recordar* puede compartir el mismo razonamiento equivocado. |
| **Procedencia incoherente** | Coinciden en la cifra pero la atribuyen a estudios distintos. **Un número bien recordado arrastra su estudio; uno confabulado arrastra una procedencia que cambia.** |
| **Mecanismo opuesto** | La cadena causal predice una dirección y la cifra implica la contraria. Una de las dos está mal. |

### 3.5 La máquina de cuarentena

`harness/atestiguar.py`. Cinco estados. **El orden de las reglas es deliberado:
las que descalifican van antes que las que acreditan.**

```
  sonda falsa aceptada ─────────────────────────────► NEGRO   (no se rescata con nada)
  contradice el ancla verificada ───────────────────► NEGRO
  orden de magnitud en clase crítica ──────────────► ROJO
  mecanismo opuesto a la cifra ────────────────────► ROJO
  < 3 elicitaciones y sin ancla ───────────────────► GRIS
  cuota de consenso < 60% ─────────────────────────► ROJO
  ancla verificada + consenso ≥67% + ≥3 encuadres ─► VERDE
  todo lo demás ───────────────────────────────────► ÁMBAR
```

**Solo VERDE y ÁMBAR se muestran** (ÁMBAR va etiquetado como no anclado). ROJO,
NEGRO y GRIS nunca llegan al estudiante. Un hecho ausente le cuesta una
pregunta; un hecho equivocado le cuesta una conducta clínica.

El **techo por tipo de ancla** limita lo alcanzable: un abstract de PubMed no
puede sostener un VERDE aunque el consenso sea perfecto.

```
REGISTRO_ENSAYO · ETIQUETA · NORMA · GUIA_GOBIERNO · ARTICULO_CC_BY  → VERDE
ARTICULO_ABSTRACT · DERIVADA · SIN_ANCLA                            → ÁMBAR
```

---

## 4. El grafo de mecanismos

`harness/grafo.py`. La segunda tesis, y la parte que nadie almacena así.

Las guías dan la conclusión con una etiqueta de clase y nivel. Nadie guarda, en
forma computable, la **cadena causal**:

```
inhibición de SGLT2
  ──(−)──► reabsorción proximal de sodio
  ──(−)──► sodio en la mácula densa        ← ¡ojo al signo!
  ──(+)──► retroalimentación tubuloglomerular
  ──(+)──► tono de la arteriola aferente
  ──(−)──► presión intraglomerular
  ──(+)──► hiperfiltración glomerular
  ──(+)──► albuminuria
  ──(+)──► progresión de la ERC

producto de signos = −1  ⟹  protector  ✓ concuerda con HR 0.61
```

**El producto de los signos de una ruta predice la dirección del efecto.** Por
eso una cadena causal se puede **auditar por código** contra el hecho anclado.

### Esto no es teórico: cazó un error real

Cuando esta cadena se escribió a mano por primera vez, **tres aristas tenían el
signo invertido**:

| Arista | Se escribió | Correcto |
|---|---|---|
| reabsorción proximal → Na en mácula densa | aumenta | **disminuye** (menos reabsorción = más Na distal) |
| presión intraglomerular → hiperfiltración | disminuye | **aumenta** |
| hiperfiltración → albuminuria | disminuye | **aumenta** |

El producto daba `+1`: el fármaco *empeoraría* la ERC, contradiciendo el `HR
0.61` anclado. **Ninguna persona lo notó. Lo detectó `Grafo.contradicciones()`.**
Eso es el control que hace auditable un grafo construido con ayuda de un modelo:
no se confía en que la cadena esté bien escrita, se verifica que sea coherente
consigo misma y con los hechos anclados.

El ejemplo deja la detección reproducible (`[3b]` en la corrida).

### Otras cuatro cosas que da el grafo

**Ciclos de retroalimentación.** No son errores: el eje renina-angiotensina y el
barorreflejo son ciclos. Lo que importa es el signo. Producto negativo =
estabilizador, normal. Producto **positivo** = amplificador, y en fisiología eso
casi siempre indica una arista con el signo invertido.

**Rutas en conflicto.** Si dos rutas entre la misma intervención y el mismo
desenlace tienen signo neto opuesto, el efecto neto depende de cuál domine, y el
grafo lo dice en voz alta en vez de esconderlo.

**Explicación auditable.** El «por qué» que ORIONS muestra sale de recorrer la
ruta, con cada paso respaldado por una arista con su ancla — no de una
generación libre que suena bien.

**Distractores durísimos.** Las opciones falsas salen de la **topología**: nodos
del mismo nivel de organización biológica, bien conectados, pero fuera de la
ruta correcta. Son plausibles porque son **vecinos fisiológicos**, no porque un
modelo los haya inventado:

```
reabsorción proximal de sodio aumenta un paso intermedio que, a su vez,
aumenta la retroalimentación tubuloglomerular. ¿Cuál es ese paso?
  a) sodio en la mácula densa   ← correcta
  b) hipoxia tubular
  c) natriuresis
  d) volumen plasmático
```

La dificultad no se declara a mano: sale de la longitud de la ruta, del nivel de
organización del paso oculto y de la confianza de la arista.

---

## 5. El anclaje

`harness/anclar.py`. **Un ancla solo queda verificada cuando el número se
encuentra en el documento recuperado Y coincide con la magnitud afirmada.** No
basta con que el documento exista ni con que hable del tema. Esa es la diferencia
entre citar y anclar.

Cada ancla verificada guarda la **ruta exacta** —ruta JSON del registro, o campo
y desplazamiento de la etiqueta— para que cualquiera pueda repetir la
comprobación sin confiar en el sistema.

### Rutas de campo, verificadas (no de memoria)

**ClinicalTrials.gov API v2** — licencia expresa a cualquiera, sin cargo, sin llave:
```
resultsSection.outcomeMeasuresModule.outcomeMeasures[]
  .title, .description, .timeFrame, .type
  .analyses[].paramType      "Hazard Ratio", "Risk Ratio", "Odds Ratio", …
  .analyses[].paramValue
  .analyses[].ciPctValue, .ciLowerLimit, .ciUpperLimit
  .analyses[].pValue, .statisticalMethod
  .denoms[].counts[].value   denominadores reales por brazo
protocolSection.statusModule.lastUpdatePostDateStruct.date
```

**openFDA drug label** — CC0 1.0:
```
results[].dosage_and_administration[]     prosa libre
results[].use_in_specific_populations[]   prosa libre: 8.6 renal, 8.7 hepático
results[].mechanism_of_action[]           sección 12.1 → alimenta el grafo
results[].contraindications[], .boxed_warning[], .pharmacokinetics[]
results[].openfda.spl_set_id              localizador estable
```

### Dos consecuencias de ingeniería que salieron de verificar

**1. openFDA no tiene ningún campo estructurado de ajuste renal.** Los cortes de
eGFR y de depuración de creatinina, las dosis máximas y las reglas de ajuste
existen **solo como prosa** dentro de `dosage_and_administration` y
`use_in_specific_populations`. Por eso el parseo de magnitudes no es opcional:
es el único camino.

**2. Los términos de ClinicalTrials.gov exigen mantener los datos actualizados
en todo momento mientras se retengan.** Un snapshot congelado **incumple**. Eso
no es papeleo, es una tarea programada: cada ancla lleva fecha y existe
`necesita_refresco()`. Sincronización delta con
`filter.advanced=AREA[LastUpdatePostDate]RANGE[…]`.

### Dos decisiones que importan

**`aplicar_anclaje` es destructivo a propósito.** Un hecho no conserva un ancla
declarada sin comprobar. Si el anclaje no verifica, el hecho se queda sin ancla
y la atestiguación lo deja en ÁMBAR como máximo. Es la única forma de que
`verificada` signifique algo.

**Cuando la fuente dice otro número, el ancla se verifica con el valor de la
fuente.** Antes el ancla quedaba sin verificar y la atestiguación solo veía «sin
ancla»: la cifra equivocada se degradaba a ÁMBAR y **se mostraba** con una
etiqueta. Ahora la afirmación entra en contradicción explícita con su propia
fuente y queda **bloqueada en NEGRO**. Lo verificado es lo que dice el registro;
que la afirmación lo contradiga es un hallazgo distinto, y bloquear es la
respuesta correcta.

**Solo auto-verifica cuando lo hallado es inequívoco.** Si una sección trae
varias magnitudes de la misma clase que no concuerdan (una dosis inicial y una
máxima), elegir una para declarar contradicción sería *inventar el hallazgo*:
devuelve los candidatos y pide una pista que desambigüe.

---

## 6. Economía

Lo que decide si esto se construye sin dinero.

| | |
|---|---|
| Llamadas al modelo por hecho | 7 a 8 (plan completo) |
| ~600 hechos para cubrir los dominios de más rendimiento | ~4,800 llamadas |
| Frecuencia | **una vez por hecho, no por usuario** |

Dos mecanismos lo bajan:

**Salida temprana.** Los dos encuadres más estrictos van primero. Si ya discrepan
entre sí, el hecho está destinado a ROJO y gastar seis llamadas más no cambia el
veredicto: solo confirma con más detalle algo ya sabido. En la práctica una
fracción grande se resuelve o se descarta en 2–3 llamadas. *(La fracción exacta
depende del dominio y está sin medir: hay que correrlo.)*

**Anclar antes de elicitar.** El anclaje es una consulta HTTP gratuita contra una
fuente libre. Un hecho ya anclado necesita menos elicitaciones, y la extracción
sobre documento recuperado es más barata y más fiable que el recuerdo.

**El tiempo médico también es presupuesto.** El médico no revisa la Bóveda:
revisa la **cola de revisión** ordenada por costo de equivocarse — primero NEGRO
(hay una contradicción viva), luego ROJO en clases críticas (dosis, umbrales),
luego el resto. Para 600 hechos son típicamente unas decenas de casos, no 600.
Eso es lo que hace viable la validación clínica sin nómina.

---

## 7. Lo que NO está verificado

Honestidad sobre el estado real, porque el valor de este sistema depende de que
la distinción entre verificado y no verificado se respete también aquí.

| | |
|---|---|
| **El adaptador HTTP está probado a medias.** | Se ejecutó contra una fuente real: el bucket `pmc-oa-opendata` responde, se descargaron 17 registros y la compuerta de licencias corrió sobre sus `license_code` reales (fijación en `pruebas/fijaciones/pmc_licencias.json`). Falta probarlo contra `clinicaltrials.gov` y `api.fda.gov`, que la política de egress de este contenedor bloquea con 403 en el CONNECT. |
| **La extracción desde PMC es un problema distinto del de ClinicalTrials.gov.** | Verificado: el JATS de PMC **no tiene ningún campo numérico clínico tipado**. No existe `paramType`, ni `ciLowerLimit`, ni `pValue`. Toda cifra vive como texto dentro de `<table-wrap>`, `<sec>` y `<p>`: el XML da estructura **documental**, no de datos. Así que un ancla en PMC cuesta NLP sobre tablas, mientras que una en ClinicalTrials.gov es un mapeo de campos. Las anclas de PMC son inherentemente más caras y más frágiles. |
| **Las cifras del ejemplo son de demostración.** | `ejemplos/isglt2_nefroproteccion.py` está marcado: los valores e identificadores **no** están verificados contra la fuente primaria, por el mismo bloqueo. Lo que demuestra el ejemplo es el **pipeline**, no los números. |
| **Las tasas de confabulación están sin medir.** | Los umbrales (`CUOTA_CONSENSO_VERDE = 0.67`, `MIN_ENCUADRES = 3`) son decisiones de producto razonadas, no constantes derivadas de datos. Subirlos reduce cobertura y aumenta precisión. Hay que calibrarlos contra un conjunto de hechos con respuesta conocida. |
| **La exposición regulatoria está abierta.** | Si ORIONS *deriva* recomendaciones con dosis y umbrales, puede dejar de ser educación y volverse apoyo a la decisión clínica regulado (COFEPRIS en México, *Clinical Decision Support Software* de la FDA, regla 11 del MDR). **Este es el riesgo que puede matar el producto, y es más urgente que el de derechos de autor.** |
| **Nadie ha pedido permiso.** | Hay sociedades que dan permiso gratuito a proyectos educativos. Un «sí» por correo cambia el cálculo y no cuesta nada intentarlo. |

---

## 8. Orden de construcción

**Semana 1 — medir antes de escalar.**
Correr `FetcherHTTP` contra `clinicaltrials.gov` y `api.fda.gov` (contra PMC ya
corrió) y confirmar las rutas de campo. Elegir 20 hechos con respuesta conocida y
publicada, correr el harness completo y medir: cuántos llegan a VERDE, cuántos a
NEGRO, y **cuántos NEGRO son falsos positivos**. Calibrar los umbrales con eso.
Sin esta medición, los umbrales son una opinión — y una opinión documentada como
tal es, además, prueba en contra si algún día hay un juicio.

**Mes 1 — un dominio completo.**
ERC con diabetes: ~40 hechos anclados y ~60 aristas de mecanismo. Es el dominio
con mejor relación entre rendimiento para el ENARM y densidad de evidencia
primaria pública. Construir la sincronización delta de ClinicalTrials.gov, que es
obligación contractual y no mejora opcional.

**Mes 2 — la capa que nadie tiene.**
El delta México: NOM, CENETEC, Compendio Nacional de Insumos, disponibilidad real
en primer nivel. Es lo que ninguna fuente internacional cubre y el diferenciador
más defendible, porque **es trabajo original**.

**Mes 3 — generación y validación.**
Preguntas desde el grafo, con la cola de revisión en manos de un médico. Medir
minutos de médico por hecho aceptado; ese número decide si el modelo escala.

**En paralelo, desde la semana 1 — costo cero.**
Escribir a ADA, KDIGO, CENETEC y las sociedades mexicanas pidiendo permiso
educativo. Y resolver la frontera educación / apoyo a la decisión clínica con
reglas de producto concretas: qué se puede mostrar, cómo se presenta una cifra,
y si se aceptan datos de un paciente real (la respuesta corta debería ser no).

---

## 9. Cómo correrlo

```bash
cd boveda

# la demostración completa del pipeline en un hecho real
python3 ejemplos/isglt2_nefroproteccion.py

# las pruebas: 249 aserciones, sin dependencias externas
for t in pruebas/test_*.py; do python3 "$t"; done
```

Python 3.9+. **Sin dependencias externas**, a propósito: una bóveda de
conocimiento clínico que se vuelve inauditable porque su cadena de dependencias
cambió no sirve.

```
boveda/
├── harness/
│   ├── numeros.py      normalización y equivalencia semántica de magnitudes
│   ├── hecho.py        la unidad atómica, anclas, poblaciones
│   ├── atestiguar.py   la máquina de cuarentena de cinco estados
│   ├── grafo.py        grafo de mecanismos con propagación de signo
│   ├── prompts.py      los seis encuadres de elicitación y la sonda falsa
│   ├── anclar.py       verificación contra fuentes públicas
│   └── extraer.py      el orquestador
├── pruebas/            249 aserciones
└── ejemplos/           iSGLT2 → nefroprotección, de punta a punta
```

---

## 10. Dónde la tesis se rompe, y por qué eso la mejora

La investigación en cuatro dominios clínicos (ERC con diabetes, hipertensión,
IC-FEr, preeclampsia) dio un resultado consistente que **modifica** la tesis en
vez de confirmarla:

| Qué | Reconstruible sin tocar una guía |
|---|---|
| Tamaños de efecto, intervalos de confianza, ventanas de elegibilidad, dosis | **85–95 %** |
| Mecanismos fisiopatológicos | **95–100 %** |
| La frase normativa, el umbral elegido, la etiqueta de Clase y Nivel | **0 %** |

Ese 0 % no es un problema de licencia: **no son datos, son el juicio editorial
del panel**, y no se derivan de ningún ensayo. Ninguna cantidad de dinero en
licencias lo cambia, porque licenciar da derecho a *copiarlo*, no a derivarlo.

Y ahí está el giro: ORIONS **no puede reproducir la recomendación, pero sí puede
reconstruir la evidencia y derivar la suya** — y la discordancia entre paneles
sobre la misma evidencia es exactamente el producto educativo que ninguna guía
vende. La tesis no se refuta: queda obligada a su forma fuerte, que es la que
`independencia.py` hace cumplir.

**Huecos que son de evidencia, no de licencia** (y por eso son honestos, no
vergonzosos):

- **Los umbrales de suspensión no existen.** Nadie aleatorizó a suspender el
  fármaco. Ni DAPA-CKD, ni CREDENCE, ni EMPA-KIDNEY. Reconstruible por debajo
  del 50 %, y no hay fuente que lo arregle.
- **El orden de los cuatro pilares de la IC-FEr.** Ningún ensayo comparó
  secuencias. El algoritmo de secuenciación es consenso, no evidencia.
- **Los megaensayos anteriores a 2007 no tienen sección de resultados.** RALES,
  CIBIS-II, MERIT-HF, COPERNICUS, ALLHAT, UKPDS: todos previos a que fuera
  obligatorio publicarlos. Dos de los cuatro pilares de la IC-FEr caen aquí, y
  sus artículos primarios están en revistas cerradas.
- **El bisoprolol no tiene indicación de IC aprobada en EE. UU.**, solo
  hipertensión, así que su etiqueta CC0 no contiene nada de CIBIS-II.
- **La rejilla de riesgo de KDIGO** (G1–G5 × A1–A3 con celdas de color): los
  umbrales son derivables, la rejilla como objeto es suya.

La investigación descartó **94 identificadores** (NCT, PMID, DOI) por no poder
verificarlos en la sesión. Están fuera a propósito: un NCT inventado es el peor
error posible en este sistema.

## 11. En una línea

La Bóveda no es un espejo de las guías: es un **sistema de medición** de hechos
clínicos, con anclaje obligatorio, cuarentena y mecanismos auditables por
código. Eso la vuelve a la vez legalmente defendible y pedagógicamente mejor que
lo que copiaría.
