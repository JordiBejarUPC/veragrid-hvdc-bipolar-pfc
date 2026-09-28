# Análisis de las diferencias entre `power_factory.py` y PowerFactory 2024

## Resumen ejecutivo

Las diferencias no proceden de un error en la reducción de Kron ni en la transformación de Fortescue. Tienen dos orígenes independientes:

1. **La impedancia serie del script es una aproximación de baja frecuencia.** La expresión de las líneas 90–95 no evalúa la «serie infinita de Carson»: conserva esencialmente su término principal y representa los conductores mediante GMR y resistencia DC. PowerFactory 2024 calcula, en cambio, la impedancia interna de las capas con funciones de Bessel —incluido el efecto pelicular— y el retorno por tierra con la formulación completa indicada en su referencia técnica.
2. **La admitancia difiere casi exclusivamente por el valor truncado de** `epsilon_0`. PowerFactory 2024 usa numéricamente `8.854187817e-12 F/m`; el script usa `8.854e-12 F/m`. Sustituir únicamente esta constante elimina más del 99.7 % de la diferencia visible en `B`.

Por tanto:

- **Sí merece la pena corregir ya** `epsilon_0`, el comentario sobre Carson, los nombres de las matrices de Fortescue y la inversión explícita de Kron.
- **Si el objetivo es reproducir PowerFactory y soportar barridos de frecuencia/armónicos**, merece la pena reemplazar el cálculo de `Z` por la formulación de capas de Ametani/Bessel más Carson completo.
- **No conviene ajustar empíricamente** `658.87165`, los GMR o las resistividades para forzar este caso: degradaría otros cables, frecuencias, profundidades y resistividades de terreno.

El script original no se ha modificado durante este análisis.

## Alcance y datos contrastados

La comparación se hizo con los valores de precisión completa obtenidos en modo de solo lectura mediante la API Python de PowerFactory 2024 SP8:

- Proyecto: `UnbalancedNetworkModel_Cables`
- Tipo de sistema: `606.TypCabsys`
- Tipo de cable: `250 AA CN.TypCab`
- Frecuencia: `60 Hz`
- Conductividad del terreno: `100 µS/cm = 0.01 S/m`
- Centros de los cables: `x = [-0.1524, 0, 0.1524] m`, `y = 0.609599980492801 m`
- Radio del núcleo: `6.358089923858643 mm`
- Espesor del aislamiento principal: `7.103906154632568 mm`
- Espesor de la pantalla: `0.15925799310207367 mm`
- Espesor de la cubierta exterior: `1.6510000228881836 mm`
- Permitividad relativa: `2.299999952316284` y `2.5`
- Factor de relleno: `100 %` para el núcleo y `99.44011688232422 %` para la pantalla

Estos valores también muestran que el pequeño redondeo de los literales escritos a mano existe, pero es varios órdenes de magnitud menor que las dos causas principales.

La referencia técnica oficial describe el modelo como

\[
[Z] = [Z_I] + [Z_P] + [Z_C] + [Z_0], \qquad [Y] = s[P]^{-1}.
\]

Para cables unipolares directamente enterrados, los términos de tubo común desaparecen; quedan la impedancia interna de cada cable y la contribución común del retorno por tierra. El modelo se basa en la formulación general de Ametani para cables coaxiales ([artículo original, DOI 10.1109/TPAS.1980.319718](https://doi.org/10.1109/TPAS.1980.319718)). DIgSILENT confirma además que `TypCab/TypCabsys` recalcula la dependencia frecuencial de impedancias y admitancias en los estudios armónicos ([documentación oficial](https://www.digsilent.de/en/faq-reader-powerfactory/how-do-you-model-cable-systems-in-detail-for-the-harmonic-analysis.html)).

## Comparación numérica de la matriz primitiva `Z`

Valores representativos en `Ω/km`; la columna `Δ` es `PowerFactory - script`:

| Elemento | Script | PowerFactory API | ΔR | ΔX |
|---|---:|---:|---:|---:|
| Núcleo, propio | `0.281769067 + j0.908847838` | `0.282207397 + j0.908925474` | `+0.000438330` | `+0.000077636` |
| Pantalla, propio | `1.338743002 + j0.832845967` | `1.338651047 + j0.832946089` | `-0.000091955` | `+0.000100121` |
| Mutuo, separación `0.1524 m` | `0.059217626 + j0.650474666` | `0.059124716 + j0.650568874` | `-0.000092911` | `+0.000094209` |
| Mutuo, separación `0.3048 m` | `0.059217626 + j0.598212599` | `0.059124687 + j0.598306811` | `-0.000092939` | `+0.000094211` |
| Núcleo–pantalla coaxiales | `0.059217626 + j0.832994189` | `0.059124762 + j0.833093879` | `-0.000092864` | `+0.000099690` |

Dos huellas numéricas identifican inmediatamente el origen:

- El script produce exactamente `0.0592176264065 Ω/km` para **todas** las resistencias mutuas, porque el término real usado es constante:

  \[
  4\pi f\,10^{-4}\frac{\pi}{4} = \pi^2 f\,10^{-4}.
  \]

- PowerFactory produce valores mutuos ligeramente distintos según distancia y profundidad (`0.059124687` a `0.059124762 Ω/km`). Esa dependencia es propia de los términos superiores de Carson y de la formulación de retorno por tierra; no puede obtenerse con el único término constante del script.

### 1. Retorno por tierra: aproximación frente a serie completa

Las líneas 90–95 denominan el cálculo «Carson infinite series», pero la fórmula usada es la aproximación cerrada habitual de primer orden. PowerFactory documenta para cables directamente enterrados una combinación de funciones modificadas `K0`, conductor imagen y los términos de la serie de Carson; su referencia de constantes de línea desarrolla explícitamente `P` y `Q` en potencias del parámetro de Carson.

Para el acoplamiento entre cables separados `0.1524 m`, el efecto de usar el modelo de PowerFactory en vez del término principal es:

\[
\Delta Z_{tierra} \simeq -92.911 + j94.209\;\mu\Omega/\text{km}.
\]

El signo y la magnitud se repiten en todos los términos mutuos. No es ruido de coma flotante: es el primer término omitido del desarrollo y su dependencia geométrica.

La referencia original para el retorno de una línea enterrada también señala que la impedancia debe obtenerse de la solución electromagnética del terreno, no de una única profundidad ficticia ([Carson, 1929](https://doi.org/10.1002/j.1538-7305.1929.tb02307.x)).

### 2. Impedancia interna: DC/GMR frente a funciones de Bessel

El valor de resistencia DC está bien calculado:

| Magnitud | Script | PowerFactory API | Diferencia |
|---|---:|---:|---:|
| `Rdc` del núcleo | `0.222551440384 Ω/km` | `0.222551435232 Ω/km` | `-5.15e-9 Ω/km` |

Por tanto, la diferencia de la resistencia propia no viene de la conversión de unidades, el área, el material ni el factor de relleno.

PowerFactory usa funciones modificadas de Bessel `I0`, `I1`, `K0` y `K1` para las impedancias interior, exterior y mutua de las capas conductoras. Para el núcleo compacto de este cable (`Ks = 1`), la reproducción independiente da:

| Modelo del núcleo | R (`Ω/km`) | X interna (`Ω/km`) |
|---|---:|---:|
| Script: DC + límite GMR | `0.222551435` | `0.018849556` |
| Bessel a `60 Hz` | `0.223082603` | `0.018827066` |
| Diferencia | `+0.000531168` | `-0.000022490` |

El efecto pelicular eleva la resistencia efectiva del núcleo en aproximadamente **0.2387 %** a 60 Hz. Aunque sea pequeño, es mayor que la corrección de Carson y explica que la resistencia propia del núcleo de PowerFactory resulte finalmente superior.

Puede aislarse la impedancia interna sin asumir ningún modelo de tierra formando el lazo núcleo–pantalla:

\[
Z_{lazo}=Z_{cc}-2Z_{cs}+Z_{ss}.
\]

La contribución común de tierra se cancela exactamente:

| Resultado del lazo | Valor (`Ω/km`) |
|---|---:|
| Script | `1.502076816 + j0.075705426` |
| PowerFactory | `1.502608920 + j0.075683804` |
| PowerFactory − script | `+0.000532104 - j0.000021622` |

Este resultado coincide con la corrección Bessel calculada de forma independiente. La pantalla, por ser delgada, apenas añade efecto pelicular resistivo a 60 Hz; su diferencia propia está dominada por la corrección del retorno por tierra.

### 3. Acoplamiento núcleo–pantalla

`d_cs = (ri_s + ro_s) / 2` no es realmente una «distancia entre conductor y pantalla» aplicable a dos hilos paralelos. En un sistema coaxial el acoplamiento debe construirse con:

- la impedancia superficial exterior del núcleo;
- las impedancias interior, exterior y mutua de la pantalla tubular;
- el flujo longitudinal en el aislamiento, proporcional a `ln(r_outer / r_inner)`;
- la contribución común de tierra.

El GMR tubular usado por el script es una aproximación de baja frecuencia razonable, pero no reproduce exactamente esa descomposición ni su dependencia con la frecuencia.

## Efecto después de Kron y Fortescue

La reducción aplicada en las líneas 103–109 es algebraicamente correcta. Con las matrices primitivas exactas de PowerFactory:

- el mayor error absoluto de la matriz `Z_abc` reducida es `0.00056338 Ω/km`;
- el mayor error relativo por elemento es aproximadamente `0.0852 %`;
- en la diagonal de secuencia positiva, el script da aproximadamente `0.253908288 + j0.270512014 Ω/km`, frente a `0.254441115 + j0.270495022 Ω/km` de PowerFactory.

Para un flujo de carga a 60 Hz la diferencia es pequeña. Para construir un modelo general de VeraGrid, especialmente si se desea compatibilidad con armónicos o EMT, no conviene conservar la aproximación como único método. DIgSILENT distingue precisamente el modelo geométrico `TypCab/TypCabsys` por su dependencia frecuencial automática ([documentación oficial](https://www.digsilent.de/en/faq-reader-powerfactory/how-do-you-model-overhead-lines-and-cables-in-powerfactory.html)).

## Comparación numérica de `Y`

La estructura de la matriz de potencial de las líneas 139–150 es correcta para este caso. Para cables directamente enterrados, PowerFactory considera el terreno circundante equipotencial y no introduce acoplamiento capacitivo entre cables distintos. Cada bloque núcleo–pantalla se obtiene de los dos condensadores coaxiales:

\[
C_i=\frac{2\pi\epsilon_0\epsilon_r}{\ln(r/q)},\qquad
Y=G+j\omega C.
\]

La diferencia está en la constante:

- Script: `8.854e-12 F/m`
- PowerFactory 2024, inferida exactamente de `B` y de los campos API: `8.854187817e-12 F/m`
- CODATA 2022: `8.8541878188(14)e-12 F/m` ([NIST](https://www.physics.nist.gov/cgi-bin/cuu/Value?eqep0=))

PowerFactory conserva el valor convencional anterior a la redefinición del SI, redondeado a los dígitos mostrados. Para paridad bit a bit con PF 2024 debe usarse su valor; para una constante física actual podría usarse CODATA, cuya diferencia respecto a PF es completamente despreciable para este cálculo.

| Susceptancia (`µS/km`) | Script actual | Solo corrigiendo `epsilon_0` | PowerFactory API |
|---|---:|---:|---:|
| Núcleo, diagonal | `64.30348625` | `64.30485030` | `64.30484744` |
| Núcleo–pantalla | `-64.30348625` | `-64.30485030` | `-64.30484744` |
| Pantalla, diagonal | `522.59348443` | `522.60457004` | `522.60456013` |
| Núcleo tras Kron | `56.39114431` | `56.39234052` | `56.39233821` |

La corrección de `epsilon_0` deja residuos de solo `2.9e-6` a `9.9e-6 µS/km`, explicados por los literales redondeados a mano frente a los valores binarios de precisión completa almacenados por PowerFactory. Usando `epsilon_0 = 8.854187817e-12` y los campos API exactos, la susceptancia principal reproduce exactamente `64.3048474379772 µS/km`.

Las conductancias de la captura son cero porque las capas aislantes activas de este tipo tienen `tanδ = 0`. El modelo general futuro sí debe implementar `G_i = ω C_i tanδ`.

## Cambios recomendados

### Prioridad inmediata: correcciones pequeñas y seguras

1. Cambiar `epsilon_0` a `8.854187817e-12` si el criterio es paridad con PowerFactory 2024.
2. Cambiar el comentario «Carson infinite series» por «aproximación de primer término de Carson» mientras se conserve la fórmula actual.
3. Renombrar las matrices de Fortescue: los nombres actuales están intercambiados. El producto efectuado es correcto, pero la matriz sin `1/3` transforma de secuencias a fases y la matriz con `1/3` transforma de fases a secuencias.
4. Sustituir la inversión explícita de Kron por `np.linalg.solve(Z_ww, Z_wc)`:

   ```python
   Z_abc = Z_cc - Z_cw @ np.linalg.solve(Z_ww, Z_wc)
   ```

5. No llamar `R_ac` a un vector que contiene `R_DC`; el nombre actual oculta precisamente la aproximación que causa la diferencia.
6. Corregir comentarios de unidades: por ejemplo, `gmr` está en metros, no en `Ω/km`.

### Prioridad para la implementación real en VeraGrid

Implementar el modelo geométrico por capas, manteniendo la reducción de Kron posterior:

1. Calcular resistividad efectiva, temperatura, factor de relleno, permeabilidad y factor `Ks`.
2. Calcular impedancia superficial del núcleo sólido y las tres impedancias de cada tubo mediante `scipy.special.iv` y `scipy.special.kv`. SciPy ya es una dependencia de VeraGrid; no hace falta añadir otra.
3. Añadir la impedancia del campo magnético en cada aislamiento coaxial.
4. Construir la matriz interna `[Z_I]` según las ecuaciones de la referencia de PowerFactory/Ametani.
5. Implementar el retorno por tierra de PowerFactory: funciones `K0`, conductores imagen y serie completa de Carson, con ramas numéricas adecuadas para argumentos pequeños y grandes.
6. Sumar los bloques por cable y entre cables, y solo después aplicar reducción de Kron y transformación de secuencias.
7. Construir `[P]`, `C`, `G` e `Y` incluyendo `tanδ` y, cuando corresponda, capas semiconductoras.

No es recomendable introducir todavía armadura, tubo común, proximidad avanzada o terreno multicapa dentro del mismo cambio. El caso `TypCab` coaxial directamente enterrado ya permite validar la arquitectura mínima y cubre el ejemplo actual.

## Pruebas de regresión propuestas

El caso `606 / 250 AA CN` debería convertirse en una prueba dorada con los valores de la API, no con los redondeados de la GUI. Como mínimo:

- matrices primitivas `R_c`, `X_c`, `G_c` y `B_c` simétricas;
- elementos representativos de las tablas anteriores;
- matriz reducida `Z_abc` y `Y_abc`;
- secuencias y términos de acoplamiento en geometría no perfectamente transpuesta;
- prueba a otra frecuencia para detectar que no se ha vuelto accidentalmente al modelo DC/GMR;
- prueba con `tanδ != 0` para la conductancia;
- prueba con temperatura distinta de `20 °C`.

Una tolerancia inicial razonable para este caso es `1e-7 Ω/km` en `Z` y `1e-5 µS/km` en `B`, siempre que se alimenten los valores binarios completos de la API. Con datos introducidos manualmente y redondeados, la tolerancia debe reflejar explícitamente ese redondeo.

## Conclusión

El cálculo actual es una buena aproximación de comprobación a 60 Hz, y las operaciones matriciales posteriores están bien. Sin embargo, no está ejecutando el mismo modelo electromagnético que PowerFactory:

- `Y`: corrección trivial y recomendable de `epsilon_0`;
- `Z`: diferencia física de modelo —Bessel/efecto pelicular y Carson completo—, no un problema de decimales;
- Kron y Fortescue: resultado correcto, con mejoras de nomenclatura y estabilidad numérica.

La decisión práctica depende del objetivo. Para un flujo de carga aislado a 60 Hz, el error reducido máximo de aproximadamente `0.085 %` puede ser aceptable. Para importar `TypCab/TypCabsys` y prometer resultados comparables con PowerFactory en distintas frecuencias, hay que implementar la formulación completa y conservar la versión actual, como mucho, como modo aproximado explícito.

## Fuentes

- DIgSILENT GmbH, `Technical Reference: Cable System (ElmCabsys, TypCabsys)`, PowerFactory 2024 SP8, secciones 3.1–3.4, instalación local: `C:/Program Files/DIgSILENT/PowerFactory 2024 SP8/Help/TechRef/TechRef_CableSystem.pdf`.
- DIgSILENT GmbH, `Technical Reference: Overhead Line Constants`, PowerFactory 2024 SP8, sección 4.1.3, instalación local: `C:/Program Files/DIgSILENT/PowerFactory 2024 SP8/Help/TechRef/TechRef_OverheadLineConstants.pdf`.
- A. Ametani, “A General Formulation of Impedance and Admittance of Cables”, IEEE Transactions on Power Apparatus and Systems, 1980, [DOI 10.1109/TPAS.1980.319718](https://doi.org/10.1109/TPAS.1980.319718).
- J. R. Carson, “Ground Return Impedance: Underground Wire with Earth Return”, Bell System Technical Journal, 1929, [DOI 10.1002/j.1538-7305.1929.tb02307.x](https://doi.org/10.1002/j.1538-7305.1929.tb02307.x).
- DIgSILENT, [modelado de líneas y cables en PowerFactory](https://www.digsilent.de/en/faq-reader-powerfactory/how-do-you-model-overhead-lines-and-cables-in-powerfactory.html) y [modelos geométricos de cable para armónicos](https://www.digsilent.de/en/faq-reader-powerfactory/how-do-you-model-cable-systems-in-detail-for-the-harmonic-analysis.html).
- NIST, [CODATA value: vacuum electric permittivity](https://www.physics.nist.gov/cgi-bin/cuu/Value?eqep0=), ajuste 2022.
