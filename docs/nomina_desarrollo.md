# Manual de Nómina — TUC TUC
## Documento de Desarrollo

**Estado:** En construcción (inicio: 2026-03-24)
**Autor técnico:** Rafael Olivares Giraldo — Contador Público

---

## Propósito

Este manual documenta los fundamentos legales y de cálculo sobre los que se construirá el módulo de nómina de TUC TUC. Aplica tanto para la nómina interna (conductores, empleados) como para eventuales herramientas de nómina que se ofrezcan a negocios clientes.

> El caso de estudio inicial fue la asesoría para una empleada doméstica con jornada de 2 días/semana — el escenario más simple y más común, que obliga a resolver bien los fundamentos antes de escalar a casos más complejos.

---

## Capítulo 1 — Fundamentos Legales (Colombia 2026)

### 1.1 Valores de referencia vigentes

| Concepto | Valor | Norma |
|---|---|---|
| Salario Mínimo Legal Mensual (SMLMV) | **$1.750.905** | Decreto 1469, 29-dic-2025 |
| Auxilio de Transporte mensual | **$249.095** | Decreto 1469, 29-dic-2025 |
| Jornada máxima semanal | **42 horas** | Ley 2101/2021 (vig. jul-2025) |
| Semanas por mes (factor) | **4.3** | Convención de cálculo |
| Horas máximas mensuales | **180.6 h** | 42 × 4.3 |
| **Valor hora ordinaria** | **$9.695** | $1.750.905 ÷ 180.6 |

### 1.2 Normas marco

| Norma | Contenido relevante |
|---|---|
| CST Arts. 23, 37–38 | Contrato verbal = escrito, a término indefinido desde el 1er día |
| CST Art. 128 | Auxilio de transporte NO es base para prestaciones ni SS |
| CST Art. 186 | Vacaciones: 15 días hábiles por año de servicio |
| CST Art. 249 | Cesantías: 1 mes de salario por año |
| CST Art. 306 | Prima de servicios: 15 días en jun y 15 días en dic |
| Ley 100/1993 Art. 204 | Trabajador OBLIGADO a pagar su parte de SS (8%) |
| Ley 1788/2016 | Empleados domésticos: prestaciones plenas = régimen general |
| Decreto 721/2013 | Domésticos: afiliación SS obligatoria desde día 1 |
| Ley 50/1990 Art. 99 | Intereses sobre cesantías: 12% anual (≈ 1% mensual) |

---

## Capítulo 2 — Unidad de Cálculo

### 2.1 La hora como unidad base

El salario mínimo está fijado para quien trabaja el máximo legal. La unidad correcta de cálculo es la **hora**, no el día calendario.

```
Valor hora = SMLMV ÷ horas_máximas_mensuales
           = $1.750.905 ÷ (42 × 4.3)
           = $1.750.905 ÷ 180.6
           = $9.695/hora
```

**Errores comunes a evitar:**
- ❌ `SMLMV ÷ 30` → da el valor del día *calendario*, no del día *trabajado*
- ❌ `salario_día ÷ 9` → incorrecto; la hora vale $9.695 independientemente de cuántas horas tenga el día
- ✅ `horas_trabajadas × $9.695` → siempre correcto

### 2.2 Salario por día pactado

```
Salario/día = horas_acordadas_por_día × $9.695
```

Límite diario ordinario: **9 horas**. Las horas que superen ese límite son **horas extraordinarias** con recargo mínimo del 25% (diurnas) o 75% (nocturnas).

---

## Capítulo 3 — Auxilio de Transporte Proporcional

### 3.1 Fórmula

El auxilio mensual ($249.095) está pensado para el trabajador de tiempo completo. Para jornadas parciales:

```
Días/mes_referencia = (42 ÷ horas_día) × 4.3
Aux_transporte/día  = $249.095 ÷ días/mes_referencia
Aux_transporte/mes  = Aux/día × días_trabajados_al_mes
```

### 3.2 Tabla de referencia — Aux. transporte por día según jornada

| Horas/día | Días/mes ref. | Aux/día | Aux/mes (8.6d) |
|---|---|---|---|
| 6h | 30.1 | $8.275 | $71.165 |
| 7h | 25.8 | $9.655 | $83.033 |
| 8h | 22.575 | $11.034 | $94.892 |
| 9h | 20.067 | $12.413 | $106.752 |

### 3.3 Condiciones de aplicación

- Solo aplica si salario ≤ 2 SMLMV ($3.501.810)
- Solo aplica si el trabajador **no vive** en el lugar de trabajo
- Un día extra esporádico no genera nuevo cálculo de auxilio — las horas sí se liquidan como extraordinarias
- **NO entra** en la base para calcular prestaciones ni seguridad social

---

## Capítulo 4 — Prestaciones Sociales

Base de cálculo: **salario devengado** (sin auxilio de transporte).

| Prestación | % | Base legal | Fecha de pago |
|---|---|---|---|
| Prima de servicios | 8.33% | CST Art. 306 | Jun 30 y Dic 20 |
| Cesantías | 8.33% | CST Art. 249 | Feb 14 (consignación al fondo) |
| Intereses s/cesantías | 1.00% | Ley 50/1990 Art. 99 | Ene 31 |
| Vacaciones | 4.17% | CST Art. 186 | Al momento de tomar las vacaciones |
| **Total provisión** | **21.83%** | | |

**Nota:** Aunque las prestaciones se pagan en fechas específicas, la práctica correcta es provisionarlas mensualmente (reservar el 21.83% del salario cada mes).

---

## Capítulo 5 — Seguridad Social

Base de cálculo: **salario devengado** (sin auxilio de transporte).
Mecanismo de pago: **PILA** (Planilla Integrada de Liquidación de Aportes).

### 5.1 Aporte del empleador (encima del salario)

| Concepto | % |
|---|---|
| Salud | 8.500% |
| Pensión | 12.000% |
| ARL — Clase I (riesgo mínimo) | 0.522% |
| **Total empleador** | **21.022%** |

> La ARL varía según la clase de riesgo del cargo. Clase I (oficina/doméstico): 0.522%. Clase V (minería, explosivos): 6.960%.

### 5.2 Aporte del trabajador (obligatorio por ley — se descuenta del salario)

| Concepto | % |
|---|---|
| Salud | 4.00% |
| Pensión | 4.00% |
| **Total trabajador** | **8.00%** |

**Principio legal:** Art. 204 Ley 100/1993 — el trabajador está **obligado** a cubrir su parte. No es una decisión del empleador absorberla o no. El empleador recauda ese 8% descontándolo del salario y lo incluye en la planilla.

---

## Capítulo 6 — Cuadro Consolidado de Costos

### 6.1 Fórmulas resumen

```
Costo total empleador/mes = Salario × 143.05% + Aux.transporte
                          = Salario × (1 + 21.83% + 21.022%) + Aux.transporte

Salario neto trabajador/mes = Salario × 92% + Aux.transporte
                            = Salario × (1 - 8%) + Aux.transporte
```

### 6.2 Tabla completa — 2 días/semana (8.6 días/mes)

| H/día | Salario/mes | Aux.transp. | Prestaciones | SS empleador | **Costo total** | **Neto empleado** |
|---|---|---|---|---|---|---|
| 6h | $500.262 | $71.165 | $109.207 | $105.105 | $785.739 | $534.280 |
| 7h | $583.639 | $83.033 | $127.408 | $122.623 | $916.703 | $623.327 |
| 8h | $667.016 | $94.892 | $145.615 | $140.220 | $1.047.743 | $708.547 |
| 9h | $750.393 | $106.752 | $163.811 | $157.758 | $1.178.714 | $793.612 |

### 6.3 Liquidación completa por día — ejemplo 8 horas

| Concepto | Valor/día |
|---|---|
| Salario (8h × $9.695) | $77.560 |
| Aux. transporte | $11.034 |
| Prima (8.33%) | $6.461 |
| Cesantías (8.33%) | $6.461 |
| Int. cesantías (1%) | $776 |
| Vacaciones (4.17%) | $3.234 |
| Salud empleador (8.5%) | $6.593 |
| Pensión empleador (12%) | $9.307 |
| ARL clase I (0.522%) | $405 |
| **Costo total/día (empleador)** | **$121.831** |
| SS trabajador (−8%) | −$6.205 |
| **Neto recibido/día** | **$82.389** |

---

## Capítulo 7 — Advertencias para Implementación

### 7.1 Pago informal sin afiliación

Es frecuente en servicio doméstico acordar un "valor por día todo incluido" sin PILA. **Riesgos:**

1. Sin ARL: accidente laboral → empleador responde patrimonialmente sin límite
2. Sin salud: incapacidades sin cobertura → responsabilidad solidaria del empleador
3. Sin pensión: deuda acumulada retroactiva + intereses + sanciones
4. El contrato existe igual desde el día 1 — la omisión no elimina las obligaciones

### 7.2 Horas extras

- Hora extra diurna (6am–9pm): recargo 25% → $9.695 × 1.25 = **$12.119/hora extra**
- Hora extra nocturna (9pm–6am): recargo 75% → $9.695 × 1.75 = **$16.966/hora extra**
- Hora dominical/festivo ordinaria: recargo 75%
- Hora extra dominical/festivo: recargo 100%

---

## Próximos capítulos a desarrollar

- [ ] Cap. 8 — Nómina de conductores TUC TUC (por viaje vs. por hora vs. fijo)
- [ ] Cap. 9 — Integración con módulo de liquidación en la app
- [ ] Cap. 10 — Generación de PILA desde TUC TUC
- [ ] Cap. 11 — Nóminas de negocios clientes (servicio adicional)

---

## Documento de referencia para usuarios

- `docs/asesoria_leticia_oviedo_2026.html` — Caso de estudio: empleada doméstica por días, Cali 2026. Documento completo con toda la lógica explicada para un usuario no técnico.
