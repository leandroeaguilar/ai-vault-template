# Referencia técnica

Lo que hace falta para **modificar** la plantilla o adaptarla a otra estructura de carpetas. Para
instalarla y usarla alcanza con el [README](README.md); para el porqué de cada decisión,
[DECISIONES.md](DECISIONES.md).

---

## 1. Comandos que se corren a mano

Ninguno está cableado a un evento. Se invocan cuando los necesitás.

| Comando | Para qué |
|---|---|
| `bash .claude/hooks/security-audit.sh` | Auditoría completa: secretos committeados, integridad del `.gitignore`, inventario de hooks y de plugins, sanidad del wiring de `settings.json` |
| `bash .claude/hooks/check-links.sh` | Enlaces rotos, resolviendo alias, secciones (`#`) y bloques (`#^`) antes de acusar |
| `python3 .claude/hooks/harden-links.py [--dry]` | Convierte nombres pelados a rutas relativas y re-apunta enlaces cuyo destino se mudó. Kill-switch propio: `.vault-meta/harden.disabled` |
| `python3 .claude/hooks/heal-links.py` | Reparación de enlaces rotos |
| `python3 .claude/hooks/search-sessions.py` | Busca en transcripts de sesiones viejas |
| `bash .claude/hooks/wiki-lock.sh acquire\|release\|peek <ruta>` | Lock advisory por archivo para escritura multi-agente |
| `bash .claude/hooks/check-diary-size.sh` | Estado del tope de la bitácora del mes |

## 2. Qué carpeta nombra en duro cada hook

Nueve archivos del toolkit hardcodean rutas de carpeta: ocho hooks en `.claude/hooks/` más
`.githooks/pre-commit`. Esta es la lista completa, y es por dónde hay que empezar si querés los
hooks sobre otra estructura.

| Carpeta | Quién la nombra en duro |
|---|---|
| `00 Sistema` | `check-links.sh`, `sentinels-verify.py`, `verify-commit.sh`, `pre-commit` |
| `01 Index` | `session-context.sh`, `verify-commit.sh` |
| `02 MOCs` | `verify-commit.sh` |
| `04 Knowledge` | `verify-commit.sh`, `sentinels-verify.py`, `generate-index.py`, `check-routines.sh` |
| `05 Diario` | `agent-diary.sh`, `check-diary-size.sh`, `session-context.sh`, `check-routines.sh` |
| `03 Proyectos`, `06 Raw`, `99 Archivo` | **ningún hook** — viajan por la estructura PARA, no porque el código las necesite |

Orden sugerido para reescribirlas: `verify-commit.sh` (define las zonas donde el frontmatter es
obligatorio, y sus exenciones), después `agent-diary.sh` y `session-context.sh` (la ruta de la
bitácora), y al final `generate-index.py` y `sentinels-verify.py`.

## 3. Qué asume cada hook

| Hook | Asume |
|---|---|
| `agent-diary.sh`, `check-diary-size.sh`, `session-context.sh` | Bitácora en `05 Diario/Bitácora Agentes/AAAA-MM.md` |
| `verify-commit.sh` | Frontmatter obligatorio en `00 Sistema`, `01 Index`, `02 MOCs` y `04 Knowledge`, con exenciones declaradas en el propio script |
| `check-links.sh`, `generate-index.py` | Sintaxis de wikilinks de Obsidian |
| `pr-notice.sh`, `check-routines.sh`, `auto-commit.sh` | `vault.conf` con `VAULT_MODE` |
| `pr-notice.sh`, `/revisar-pr` | `gh` instalado y autenticado |
| Los 9 hooks de `.claude/` | Claude Code. En otro harness quedan inertes |

## 4. Qué viaja además de las carpetas

Lo mínimo para que el verifier tenga sentido:

| Qué | Por qué está |
|---|---|
| [`SOP Documentación`](<00 Sistema/SOP Documentación.md>) | El contrato que aplican `verify-commit.sh`, `harden-links.py` y `generate-index.py`: frontmatter canónico, naming, esquema de `id`, regla de enlaces |
| [`Centinelas de Edición`](<00 Sistema/Centinelas de Edición.md>) | La spec de `sentinels-guard.*` y `sentinels-verify.py` |
| [`SOP Hooks y Automatización`](<00 Sistema/SOP Hooks y Automatización.md>) | Cómo se escribe, se cablea y se apaga un hook; los locks advisory |
| [`Cómo funciona este vault`](<00 Sistema/Cómo funciona este vault.md>) | El porqué de las ocho carpetas: el pipeline `06 Raw` → `04 Knowledge` → `02 MOCs` → `01 Index`, LLM Wiki y OKF |
| 3 plantillas | El frontmatter que el verifier exige, en un archivo que se puede copiar |
| [`AGENTS.md`](AGENTS.md) | El contrato que lee cualquier agente antes de escribir |
| 3 stubs en `01 Index/` | La capa de orientación: `Vision`, `Objetivos`, `Mapa Personal`. Son `scaffold`: los llenás una vez y `update.sh` no vuelve a tocarlos |

## 5. Las dos whitelists

`update.sh` (array `FRAMEWORK_PATHS`) y `vault-manifest.json` (clave `infrastructure`) **tienen que
decir lo mismo, y toda ruta que nombran tiene que existir**. Es fácil que se desincronicen —agregás
un archivo al manifest y te olvidás del script— y el modo de falla es silencioso: el updater
simplemente no copia ese archivo, sin decir nada.

`vault.conf`, `FIRST_RUN.md` y los tres stubs de `01 Index/` están fuera de `infrastructure` a
propósito: son `scaffold`. Si `vault.conf` entrara en la whitelist, cada actualización pisaría el
`VAULT_MODE=equipo` de un vault de organización con el `personal` del template, apagando el gate de
rama sin que nadie lo hubiera pedido.

## 6. Cabos sueltos

Referencias que el repositorio arrastra y que **no existen** en esta versión. Se declaran en vez de
esconderse.

| Referencia | Quién la nombra | Efecto real |
|---|---|---|
| `.github/CODEOWNERS` | `aviso-de-pr.yml` | Ninguno: es una de tres fuentes de menciones, y la ausencia queda declarada en el log del workflow. No se publica un archivo de ejemplo porque los handles son de cada instancia |

El historial de los que ya se cerraron está en el [CHANGELOG](CHANGELOG.md).
