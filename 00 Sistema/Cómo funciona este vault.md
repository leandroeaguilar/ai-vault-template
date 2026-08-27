---
type: Explanation
title: "Cómo funciona este vault"
tags: [onboarding, arquitectura, okf, llm-wiki]
estado: 🟢 Activo
prioridad: 🔥 Alta
responsable: "{{OWNER}}"
id: "EXP-001"
generated:
  by: human:{{OWNER}}
  at: 2026-08-27T00:00:00Z
fecha_creacion: 2026-08-27
description: "Por qué las ocho carpetas, por qué LLM Wiki y por qué OKF: las tres decisiones de arquitectura que explican la estructura que trae esta plantilla."
resource:
---

# Cómo funciona este vault

Clonaste una plantilla que trae ocho carpetas vacías, un contrato de documentación y veintidós
hooks. Este documento explica **por qué** están, en ese orden y no en otro. Son tres decisiones,
y las tres son anteriores al código.

---

## 1. Por qué ocho carpetas numeradas

La numeración no es decorativa: **el número es la posición en un pipeline**, y la carpeta dice en
qué estado de maduración está lo que guardás.

```
06 Raw  →  04 Knowledge  →  02 MOCs  →  01 Index
crudo      reutilizable     conectado    navegable
```

| Capa | Qué vive acá | Qué la distingue |
|---|---|---|
| `00 Sistema` | Reglas, SOPs, plantillas | Cómo se opera el vault. Cambia poco y a propósito. |
| `01 Index` | Navegación global | Orienta; no guarda conocimiento profundo. |
| `02 MOCs` | Mapas de contenido | Puertas de entrada temáticas. **No** son carpetas. |
| `03 Proyectos` | Iniciativas con inicio y fin | Si no termina, no es un proyecto. |
| `04 Knowledge` | Conocimiento reutilizable | Sirve en más de un contexto y sobrevive al proyecto. |
| `05 Diario` | Registro operativo y de sesiones | Fechado. Se consolida, no crece para siempre. |
| `06 Raw` | Fuentes sin procesar | Todavía **no** es conocimiento. |
| `99 Archivo` | Terminado o retirado | Sale del paso sin perder la historia. |

**El corte que hace el trabajo es `06 Raw` ↔ `04 Knowledge`.** Guardar un artículo no es saberlo.
Mientras esa frontera exista físicamente, el sistema no puede mentirte sobre cuánto procesaste: la
diferencia entre las dos carpetas es la deuda pendiente, y se ve de un vistazo.

**El segundo corte es `02 MOCs` ↔ carpetas.** Un MOC es una nota que enlaza otras notas. Una
carpeta obliga a elegir *un* lugar; un MOC deja que una nota pertenezca a varios mapas sin
duplicarse. Por eso la regla del `AGENTS.md`: ante la duda entre más estructura o más conexiones,
más conexiones.

Nada de esto obliga a llenar las ocho desde el día uno. `03 Proyectos` y `99 Archivo` pueden pasar
meses vacías; existen para que cuando las necesites no tengas que inventar dónde va la cosa.

---

## 2. Por qué LLM Wiki

El patrón viene de un [gist de Andrej
Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): organizar el
conocimiento propio como una wiki pensada para que **la mantenga y la consuma un modelo**, no solo
un humano. Cinco piezas:

```
Raw Sources  →  Wiki  →  Schema  →  Index  →  Agents
06 Raw          04 Kn.   frontmatter  01/02   .claude/
```

Lo que cambia respecto de "tomar notas en Markdown" es el **destinatario**. Un agente que entra a
tu vault no tiene tu contexto, no recuerda la sesión anterior y no puede preguntarte a mitad de un
commit. Entonces:

- **La estructura tiene que ser deducible del árbol de archivos**, no de tu cabeza.
- **Cada nota tiene que decir qué es** en un campo, no en el tono del texto.
- **Las leyes tienen que estar en un archivo que el agente lea**, no en una costumbre.

De ahí salen `AGENTS.md` (la ley), el frontmatter obligatorio (el esquema) y los `index.md`
generados (la navegación). Y de ahí sale la consecuencia incómoda: si esto depende de que alguien
se acuerde de cumplirlo, no se cumple. Por eso el vault trae hooks, y no una guía de estilo.

---

## 3. Por qué OKF

[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog) es un estándar
abierto publicado por Google Cloud (junio 2026) para representar conocimiento curado de forma
portable entre sistemas y agentes. **Es la formalización vendor-neutral del patrón LLM Wiki** — el
blog de lanzamiento lo cita de forma explícita.

Lo que aporta acá es concreto y chico:

- **Un bundle es un directorio de Markdown.** Cada `.md` no reservado es un concepto; `index.md` y
  `log.md` son nombres reservados. La identidad de un concepto es su ruta. Nada de base de datos.
- **Un mínimo de campos obligatorios** en el frontmatter, en vez de que cada nota invente los
  suyos. Acá son `type`, `title`, `description`, `generated` (`{by, at}`) y `resource`; el detalle
  está en [SOP Documentación](<SOP Documentación.md>) §4.
- **`generated.by` distingue quién escribió qué** — `human:<nombre>` o `process:<agente>`. En un
  vault editado por varias IAs, esa sola clave es la diferencia entre saber y suponer de dónde
  salió una línea.

Y lo que OKF deliberadamente **no** hace importa igual: no impone taxonomía de tipos, no prescribe
almacenamiento, no reemplaza esquemas de dominio. Es un formato, no una plataforma. Por eso se
puede adoptar sin casarse con nadie: si mañana lo abandonás, te quedan archivos Markdown con
frontmatter, que es exactamente lo que tenías antes.

---

## 4. Qué de todo esto lo hace cumplir el código

Las tres decisiones de arriba serían buenas intenciones sin la capa que las verifica. El mapeo es
uno a uno:

| Decisión | Quién la hace cumplir |
|---|---|
| Frontmatter OKF obligatorio | `verify-commit.sh` en `pre-commit` |
| Reglas de enlaces | `harden-links.py`, `check-links.sh` |
| Navegación al día | `generate-index.py` (regenera los `index.md`) |
| Lo que escribiste vos no se pisa | centinelas `@user` / `@generated` |
| Nada de secretos en la historia | `secret-scan.sh` |

El detalle de cada una está en el [README](<../README.md>).

---

## 5. Primeros pasos

1. `./install.sh` — cablea `core.hooksPath` y crea `.vault-meta/`.
2. Copiá `owner.env.example`, completalo y corré `./personalize.sh`.
3. Abrí la carpeta con Obsidian (opcional, pero las plantillas usan Templater).
4. Escribí tu primera nota desde `001_plantillas/Plantilla Nota.md` e intentá commitearla con el
   frontmatter incompleto. **Que el verifier te frene es la señal de que está andando.**

Lo que este repositorio **no** trae es el método: cómo estudiar, cómo decidir, cómo revisar, cómo
construir carrera encima de esto. Eso es contenido de cada quien, y la plantilla está hecha para no
opinar al respecto.
