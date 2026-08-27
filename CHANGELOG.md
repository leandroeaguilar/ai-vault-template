# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) · versionado
[SemVer](https://semver.org/lang/es/).

Cada versión tiene un tag anotado en el repositorio. `update.sh` compara el archivo `VERSION`
contra el del upstream para decidir si una instancia está atrasada — por eso `VERSION`, el campo
`version` de `vault-manifest.json` y el tag tienen que decir lo mismo.

---

## [0.4.0] — 2026-08-27

### Agregado
- **`00 Sistema/Cómo funciona este vault.md`** — el porqué de la arquitectura: las ocho carpetas
  numeradas como pipeline (`06 Raw` → `04 Knowledge` → `02 MOCs` → `01 Index`), el patrón
  [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) y el estándar
  [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog).
- **Dos skills:** `/revisar-seguridad` (auditoría a demanda antes de instalar o abrir algo; es la
  capa 5, la única falible) y `/revisar-pr` (traduce un PR de Markdown a lenguaje de vault).
- **Subagente `verifier`** — tier-2 LLM sobre el diff *staged*, complemento del `verify-commit.sh`
  determinista.

## [0.3.0] — 2026-08-27

### Cambiado
- **Renombrado a `ai-vault-template`** (antes `sistema-maestro-toolkit`). El nombre viejo reclamaba
  el nombre del sistema entero para lo que empezó siendo un accesorio.

### Arreglado
- El guard de `pre-push` que impide pushear un vault personalizado al repositorio de la plantilla
  matcheaba nombres de repo hardcodeados, y **ninguno era ya el de este repo**: era código muerto
  desde la primera publicación. Ahora matchea toda la familia, nombres viejos incluidos, porque un
  clon viejo conserva el remoto sin actualizar.

## [0.2.1] — 2026-08-27

### Arreglado
- Faltaba `05 Diario/index.md` y el índice raíz lo enlazaba. `generate-index.py --staged` —que es
  como lo llama el `pre-commit`— solo regenera directorios con un `.md` staged, y `05 Diario` no
  tenía ninguno propio, solo su subcarpeta.
- `VERSION` y `vault-manifest.json` decían `0.2.0` con el tag en `v0.2.1`. Con el archivo una
  versión atrás, el parche existía como tag pero era invisible para `update.sh`.

## [0.2.0] — 2026-08-27

### Agregado
- **Las 8 capas del vault**, `05 Diario/Bitácora Agentes/`, tres SOPs de contrato
  (`SOP Documentación`, `Centinelas de Edición`, `SOP Hooks y Automatización`), tres plantillas y
  un `AGENTS.md` recortado.
- **`LICENSE-CONTENT`** — al entrar contenido, MIT pura dejó de alcanzar: MIT para código,
  CC BY-NC-SA 4.0 para los `.md`.

### Arreglado
- `vault-manifest.json` listaba 46 rutas inexistentes (29 de 41 en `infrastructure`, 17 de 17 en
  `scaffold`) y ocho hooks hardcodeaban carpetas que el repositorio no traía. Se publicaba el motor
  de verificación sin el contrato que verifica.

## [0.1.0] — 2026-08-26

### Agregado
- Publicación inicial: 22 hooks, `.githooks/` (`pre-commit`, `pre-push`), dos workflows de CI,
  la Baseline de Seguridad portable, el actualizador por whitelist (`update.sh` +
  `vault-manifest.json`) y `personalize.sh`.
