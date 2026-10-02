---
name: verifier
description: Revisa el diff staged antes de un commit y juzga calidad de conocimiento sin modificar archivos.
tipo: meta
version: "1.0"
---

# Verifier

Ejecutá esta skill después de `git add` y antes de `git commit`.

## Cuándo usar
- Activación previa a commit: después de `git add` para juzgar la calidad de metadatos y contenido del diff staged.
- Despachada para autorevisión o por petición del usuario antes de confirmar un commit.

## Entradas
- Lee `git diff --cached` (el staged diff).
- Lee `00 Sistema/SOP Documentación.md` y notas relacionadas.

## Salidas
- Emite un veredicto estructurado por consola (`LISTO / ARREGLAR-PRIMERO / REELABORAR`). Solo lectura: no modifica archivos.

## Criterios de Evaluación
1. Revisá `git diff --cached --stat` y `git diff --cached`.
2. Evaluá frontmatter canónico, enlaces existentes en markdown y nuevos en wikilinks, y ausencia de duplicados.
3. No repitas validaciones mecánicas que ya ejecuta el pre-commit hook.
4. No modifiques archivos: devolvé hallazgos advisory claros y accionables.

Formato del veredicto:
```text
VEREDICTO: LISTO / ARREGLAR-PRIMERO / REELABORAR
BLOQUEANTE: [detalles si aplican]
ALTO: [detalles]
MEDIO: [detalles]
BAJO: [detalles]
NOTAS: [recomendaciones]
```
