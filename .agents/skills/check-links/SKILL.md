---
name: check-links
description: Detecta y propone corrección de enlaces rotos, wikilinks desalineados o notas huérfanas en el vault.
tipo: meta
version: "1.0"
---

# Check Links (Chequeador y Sanador de Enlaces)

Ejecutá esta skill para auditar la integridad de los enlaces del vault.

## Cuándo usar
- Activación manual: cuando el usuario dice "revisá enlaces", "hay links rotos", "sanar enlaces" o tras renombrar o mover notas.
- Activación de mantenimiento: durante revisiones periódicas de integridad del vault.

## Entradas
- Lee todos los archivos Markdown en `00 Sistema/`, `01 Index/`, `02 MOCs/`, `03 Proyectos/`, `04 Knowledge/`, `05 Diario/` y `06 Raw/`.

## Salidas
- Emite reporte de enlaces rotos por consola.
- Genera propuesta de saneamiento o actualiza enlaces con `python .claude/hooks/heal-links.py`.
- Con `heal-links.py`, corrige los enlaces dentro de las notas de `00 Sistema/` a `06 Raw/` (en el mismo archivo).

## Herramientas Disponibles

1. **Detección de Enlaces Rotos:**
   ```bash
   bash .claude/hooks/check-links.sh --quiet
   ```
   Reporta todos los enlaces `[[wikilink]]` o markdown cuyo destino no exista.

2. **Propuesta de Sanado (Auto-heal):**
   ```bash
   python .claude/hooks/heal-links.py
   ```
   Analiza las notas rotas por similitud de nombres y propone correcciones seguras sin modificar el vault salvo que se especifique explícitamente.
