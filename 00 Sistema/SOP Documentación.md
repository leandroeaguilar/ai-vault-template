---
type: SOP
title: "SOP - Documentación"
tags: [SOP, documentacion, sistema, estandar]
estado: 🟢 Activo
prioridad: 🔥 Alta
responsable: "{{OWNER}}"
id: "SOP-002"
generated:
  by: human:{{OWNER}}
  at: 2026-07-09T00:00:00Z
fecha_creacion: 2026-06-28
resource:
---

> **ID:** SOP-002
> **Fecha:** 2026-06-28
> **Estado:** 🟢 Activo
> **Responsable:** {{OWNER}}

---

# SOP - Documentación

## 1. Objetivo
Definir **el estándar único de cómo se documenta** en este vault: frontmatter, naming, `id`, estilo y ciclo de vida. Resuelve el problema de que hoy esas reglas están dispersas e inconsistentes entre documentos.

Este SOP responde a la pregunta operativa: *"voy a crear o tocar un documento — ¿qué frontmatter le pongo, cómo lo nombro, qué estilo sigo, cuándo lo reviso?"*.

> **Qué NO cubre este SOP:** *qué tipo* de documento crear (eso lo decide el catálogo de tipos de documento del vault) ni *qué capas* construir (eso lo decide el blueprint de arquitectura). Este SOP cubre el *cómo escribir* cualquier documento, sea del tipo que sea.

## 2. Requisitos previos
- [ ] Saber qué **tipo** de documento vas a crear → consultá el catálogo de tipos de documento del vault (§3 guía de decisión).
- [ ] Verificar que el documento **no exista ya** (no duplicar; si existe, enlazar o extender).
- [ ] Tener clara la **intención del lector** (aprender / hacer / consultar / entender / decidir / rastrear).

---

## 3. Flujo de trabajo

### Paso 1 — Decidir tipo y ubicación
1. Elegí el **tipo** (el catálogo de tipos de documento del vault) → determina el prefijo de `id` y la plantilla.
2. Elegí la **carpeta** según la arquitectura de 8 capas (la arquitectura de 8 capas).

### Paso 2 — Crear desde la plantilla
Partí siempre de `00 Sistema/001_plantillas/`. No escribas el andamio a mano.

### Paso 3 — Completar el frontmatter canónico
Ver §4. Cuatro campos son **obligatorios** en todo documento.

### Paso 4 — Nombrar el archivo
Ver §5 (convención de naming por tipo).

### Paso 5 — Escribir el cuerpo con el estilo del sistema
Ver §6 (callout de relacionadas, secciones, "Cómo leer", Referencias).

### Paso 6 — Conectar
Enlazá `[[...]]` con su MOC, documentos relacionados y, si aplica, su proyecto o fuente. **Conectar antes que clasificar.**

### Paso 7 — Cerrar
Pasá la **checklist de cierre** (§8) antes de dar el documento por hecho.

---

## 4. Frontmatter canónico

### 4.1 Campos OBLIGATORIOS (todo documento)

```yaml
---
type: SOP                        # clave OKF; uno de la enum (ver 4.3)
title: "SOP - Documentación"     # OKF; = el H1 del cuerpo (ver §5)
estado: 🟢 Activo                # estado de vida (ver 4.4)
generated:                       # OKF v0.2; quién generó/editó y cuándo (ver contrato de fechas)
  by: human:{{OWNER}}            # actor (ver 4.7); un agente pone process:<id>
  at: 2026-06-28T00:00:00Z       # datetime ISO 8601 — última edición de fondo
id: "SOP-002"                    # prefijo por tipo + número (ver §7)
---
```

> **Vocabulario OKF:** `type`, `generated` (v0.2, `{by, at}`), `title` (= H1) y `description`/`resource` (§4.2) son las claves del estándar [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog). El enforcement duro es sobre `type`/`estado`/`generated`/`id`; `title` es **warn-only** (como `description`). `generated.at` es la fecha de última edición; `generated.by` el actor (§4.7).

### 4.2 Campos OPCIONALES (según el tipo y el contexto)

```yaml
description: "Resumen de UNA oración del propósito de la nota."  # OKF; fuente de los index.md y la búsqueda
resource: https://...           # OKF; URI del asset externo que la nota documenta (solo si existe: workspace, video, dashboard). Al tocar.
tags: [sop, documentacion]      # minúsculas, SIN #, formato lista [a, b]
prioridad: 🔥 Alta              # 🔥 Alta / ⏳ Media / 💤 Baja
responsable: "{{OWNER}}"
fecha_creacion: 2026-07-03      # YYYY-MM-DD — el día que nació la nota (no cambia)
ultima_auditoria_ia: 2026-06-25 # YYYY-MM-DD — solo en MOCs, cuándo la IA los auditó
# Campos transversales (notas de Knowledge):
life_areas: [profesional]
domains: [comunicacion]
goals: []
habits: []
projects: []
sources: []
```

> **Regla de `tags`:** siempre lista en línea `[a, b, c]`, en **minúsculas y SIN `#`**. El `#` dentro del YAML sin comillas rompe el parseo. (Hoy hay 3 formatos distintos en el vault — este es el único válido de ahora en más.)

> **Contrato de fechas:** una nota lleva **`fecha_creacion`** (día de nacimiento, fijo, `YYYY-MM-DD`) + **`generated.at`** (OKF v0.2; datetime ISO 8601 `YYYY-MM-DDT00:00:00Z`, cambia con cada edición de fondo, §9), acompañada de **`generated.by`** (el actor que la generó/editó, §4.7). `ultima_auditoria_ia` es un campo **opcional** exclusivo de MOCs (marca la última auditoría de IA, evento distinto de una edición). Solo `generated` es obligatorio/enforced (§4.1); `fecha_creacion` se agrega **al tocar**. Las daily notes conservan `fecha` (= el día que cubren, no "creación").

> **§4.7 · Convención de actor (OKF v0.2):** el `by` (en `generated` y `verified`) identifica **quién** con uno de tres formatos: **`human:<id>`** (una persona, ej. `human:{{OWNER}}`), **`process:<id>`** (un agente/automatización, ej. `process:claude-code`, `process:verifier`), o **`<producer>/<version>`** (una herramienta versionada). Una nota escrita a mano por el dueño lleva `by: human:{{OWNER}}`; una escrita por un agente refleja su generador real.

> **Campos opt-in de OKF v0.2:** `verified` (lista de eventos `{by, at}` de verificación) y `stale_after` (`YYYY-MM-DD`, fecha absoluta de caducidad). Ambos opcionales — se agregan al verificar / al definir una caducidad.

### 4.6 Orden canónico de las claves (secuencia)
Aunque cada tipo tiene campos propios, las claves del frontmatter van **siempre en esta secuencia** (las que existan; las ausentes se saltan):

```
type · title · tags · description · estado · prioridad · responsable · id
· fecha_creacion · generated · ultima_auditoria_ia · verified · stale_after · resource
· <campos propios del tipo, en su orden>
· life_areas · domains · goals · habits · projects · sources
```

> Las plantillas de `001_plantillas/` ya emiten este orden. Al crear o tocar un doc, mantené la secuencia — da consistencia visual y hace el frontmatter predecible entre tipos distintos.

### 4.3 Valores válidos de `type`
Usá el valor **más específico** disponible:

`Tutorial · How-to · SOP · Runbook · Reference · Explanation · ADR · Changelog · Postmortem · Checklist · Indice · Plantilla · Policy · Attested Computation`

> **`Attested Computation` (OKF v0.2):** tipo para una nota que *es* una computación versionada y verificable (una query, un script, un cálculo). Suma campos propios: `runtime`, `parameters`, `computation` (path al archivo ejecutable), `executor` y `attester`, más un heading de cuerpo `# Computation`. Opt-in.

> Un SOP usa `type: SOP` (no `How-to`); un how-to que no es un SOP formal usa `How-to`. Un runbook usa `Runbook`, no `SOP`.

### 4.4 Valores válidos de `estado`
`🟢 Activo · 🧭 Planificación · 🚧 En progreso · ✅ Completado · 📦 Archivado`

### 4.5 Qué NO lleva frontmatter (por regla)
Igual que el catálogo de tipos de documento del vault §6: apuntes de curso, proyectos, entradas de diario, `CLAUDE.md`, `AGENTS.md`, `llms.txt` y `.claude/commands/` **no** llevan `type` ni este frontmatter; se rigen por su propia convención. Los **`index.md`** de carpeta tampoco: son artefactos generados de listado puro (sin frontmatter, salvo `okf_version: "0.1"` en el raíz); el verifier los exime.

---

## 5. Naming de archivos

| Tipo | Patrón | Ejemplo |
|---|---|---|
| SOP | `SOP <Nombre>` | `SOP Documentación` |
| Runbook | `Runbook - <Fallo>` | `Runbook - Git push falla SSL` |
| Reference | `<Nombre>` o `<Tema> - <Subtema>` | `Glosario de términos` |
| Explanation | `<Concepto>` | `Filosofía del Sistema` |
| MOC / Índice | `MOC - <Tema>` | `MOC - Carrera` |
| ADR / Decisión | `Decisión - <Tema>` | `Decisión - Vault a disco local` |
| Changelog / Bitácora | `CHANGELOG ...` / `<Proceso> (bitácora)` | `CHANGELOG del Sistema` |
| Postmortem | `Postmortem - <Incidente> (YYYY-MM-DD)` | `Postmortem - Pérdida de sync (2026-06-28)` |
| Checklist | `Checklist - <Proceso>` | `Checklist - Cierre semanal` |
| Plantilla | `Plantilla <Tipo>` | `Plantilla Runbook` |

**Reglas generales:** título descriptivo en español, sin guiones bajos, sin fechas salvo en bitácoras/postmortems, sin números de versión en el nombre (la versión va en el frontmatter o changelog).

---

## 6. Estilo del cuerpo

Todo documento (salvo los excluidos en §4.5) sigue esta estructura mínima:

1. **Callout de relacionadas** (primero, tras el frontmatter):
   ```markdown
   >[!info] Documentación relacionada
   >[Doc A](<Doc A.md>) | [Doc B](<Doc B.md>) | [[Promesa aún no escrita]]
   ```
2. **Título H1** = el tipo + nombre cuando aplica (`# SOP - Documentación`).
3. **Cuerpo** según el tipo (la plantilla ya trae las secciones correctas).
4. **`## Referencias`** al final: links markdown a notas existentes, wikilink a promesas, y enlaces externos.
5. **`## Cómo leer este documento`**: una o dos líneas que orientan al lector (cada plantilla ya lo incluye).

### 6.1 Convención de enlaces

Regla del vault (endurecida por el hook `harden-links`):

- **Conocimiento existente** (la nota ya existe) → **link markdown** `[Título](<ruta relativa.md>)`.
- **Conocimiento aún no escrito** (promesa) → **wikilink** `[[Nombre]]` (resuelve por nombre; se convierte a markdown cuando la nota nace).
- **Frontmatter YAML** (`moc_principal`, etc.) → **siempre wikilink** — ni Obsidian ni Dataview reconocen links markdown dentro del YAML.
- **Índices `index.md`** → siempre markdown (artefacto generado).
- **Embeds** `![[...]]` → intactos (no se convierten).

### 6.2 Escribir *sobre* los placeholders del template (regla contraintuitiva)

> ⚠️ **En esta sección todos los tokens se muestran escapados** (`{{ OWNER }}`, con espacios). El token real va **sin** los espacios. Tuvo que ser así: esta sección es un `.md` y `personalize.sh` la recorre igual que a cualquier otra.

`personalize.sh` sustituye los tokens de identidad —`{{ OWNER }}`, `{{ OWNER_EMAIL }}`, `{{ OWNER_GITHUB }}`— con **`sed` literal, sobre todos los `.md` y `.txt` del vault**: no solo el frontmatter, no solo las notas. Es ciego, y no distingue un placeholder que hay que resolver de una frase que *habla* del placeholder.

Consecuencia real, ya materializada en una instancia: la frase *"placeholders `{{ OWNER }}` sin resolver"* quedó como *"placeholders `Ana Pérez` sin resolver"* — el nombre del dueño incrustado donde iba el nombre del token, o sea una frase que no significa nada. Y como `update.sh` re-corre `personalize.sh` en cada actualización, el daño se repite solo.

**La regla, entonces:**

| Dónde aparece el token | Cómo se escribe | Por qué |
|---|---|---|
| Frontmatter, plantillas, prosa que **debe** decir el nombre del dueño | **sin espacios** internos | Es un placeholder de verdad: se quiere sustituir |
| Prosa que **habla del token** (docs, CHANGELOG, bitácoras, este SOP) | **con un espacio interno** a cada lado | El matcher es literal, sin tolerancia a whitespace: el espacio alcanza para que no matchee, y el texto se lee igual |

> 🔴 **Ese espacio es funcional, no un typo.** Un agente o una persona que lo "corrija" por prolijidad rompe la frase en la próxima corrida de `personalize.sh` — y el síntoma aparece después, en otro archivo, sin relación aparente con el "arreglo". Si ves el token con espacios internos en prosa, **dejalo así**.

**Antes de correr `personalize.sh` a mano:** `grep -rn "{{" --include="*.md" --include="*.txt" .` y escapá lo que sea prosa. Y ojo con el alcance: el `find` del script recorre `.md` **y `.txt`** (o sea que `llms.txt` entra), pero **no** los `.py` ni los `.sh` — un placeholder hardcodeado en un hook **no se resuelve nunca** por esta vía.

Placeholders que **no** corren riesgo, porque el script no los conoce: `{{date}}` y `{{title}}` de Templater, `${{ }}` de GitHub Actions, y cualquier `{{TOKEN}}` de un JSON de ejemplo.

---

## 7. Esquema de `id`

**Formato:** `PREFIJO-NNN` (número de 3 dígitos, secuencial por prefijo).

| Tipo | Prefijo | | Tipo | Prefijo |
|---|---|---|---|---|
| Tutorial | `TUT` | | ADR / Decisión | `ADR` |
| How-to | `HOW` | | Changelog / Bitácora | `LOG` |
| SOP | `SOP` | | MOC / Índice | `MOC` |
| Runbook | `RUN` | | Postmortem | `PM` |
| Reference | `REF` | | Checklist | `CHK` |
| Explanation | `EXP` | | Plantilla | `TPL` |
| Policy | `POL` | | | |

**Reglas:**
- El `id` es **estable**: no cambia aunque renombres el archivo. Por eso permite referenciar de forma confiable.
- **No es retroactivo.** Los documentos viejos reciben `id` cuando se crean o se tocan (igual criterio que `type` en el catálogo de tipos de documento del vault §4).
- La numeración se lleva en el **Registro de IDs** (§7.1).

### 7.1 Registro de IDs (fuente de verdad)

La numeración se lleva en **un registro dentro del propio vault**: una tabla `id → documento`
que se actualiza al asignar un `id` nuevo. Ese registro es contenido del vault, no de este
repositorio, así que acá no viaja.

Lo que importa del mecanismo, y que sí es reproducible:

- **Un puntero explícito al próximo `id` libre por prefijo.** Sin eso, cada asignación obliga a
  releer la tabla entera.
- **Verificar antes de asignar.** El puntero puede quedar viejo si una rutina automática consume
  números sin actualizarlo. Un `grep -rn 'id: "SOP-' .` sobre el vault cuesta un segundo y evita
  una colisión silenciosa de IDs, que es cara de deshacer.
- **El `id` no se recicla.** Un documento archivado se lleva su número; el contador nunca baja.

## 8. Checklist de cierre
Antes de dar un documento por terminado:

- [ ] Frontmatter con los 4 campos obligatorios (`type`, `estado`, `generated`, `id`).
- [ ] `tags` en formato `[a, b]`, minúsculas, sin `#`.
- [ ] `id` registrado en §7.1 con número libre.
- [ ] Nombre de archivo según §5.
- [ ] Callout de relacionadas al inicio.
- [ ] Sección `## Referencias` y `## Cómo leer este documento`.
- [ ] Al menos un enlace `[[...]]` entrante o saliente (no queda huérfano).
- [ ] No duplica un documento existente.

---

## 9. Ciclo de vida
- **`generated.at`** se actualiza cada vez que tocás el contenido de fondo (no por cambios menores de formato); **`generated.by`** refleja quién lo hizo (§4.7).
- Un documento sin tocar durante el ciclo de revisión que le corresponde se marca para revisión.
- Cuando un documento deja de ser válido: `estado: 📦 Archivado` y se mueve a `99 Archivo`. **Nunca se borra** sin propuesta previa (regla del vault).
- Los tipos nuevos definidos por este SOP tienen plantilla: `Plantilla Runbook`, `Plantilla Postmortem` y `Plantilla Checklist` (no incluidas en este repositorio).

---

## 10. Troubleshooting
- **El frontmatter no se parsea / Obsidian lo ignora:** revisá que `tags` no tenga `#` sin comillas. Usá `[a, b]`.
- **Dos documentos con el mismo `id`:** el Registro (§7.1) es la fuente de verdad; renombrá el más nuevo al siguiente número libre.
- **No sé si es SOP o Runbook:** ¿describe la operación normal? → SOP. ¿describe qué hacer cuando algo falla? → Runbook.
- **No sé si es Reference o Explanation:** ¿se consulta un dato puntual? → Reference. ¿se lee para entender el porqué? → Explanation.

## Cómo leer este documento
Es el estándar normativo de documentación. Cuando vayas a crear o tocar un documento, seguí el flujo (§3) y cerrá con la checklist (§8). El resto de secciones se consultan puntualmente.
