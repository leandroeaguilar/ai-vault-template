#!/usr/bin/env python3
"""
crear-tarea.py - Generador determinista de tarjetas para el tablero Headless Kanban de AI Vault Template.
Crea ficheros .md con frontmatter canónico en '03 Proyectos/Kanban/Pendientes/' sin abrir Obsidian.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

# Soporte de codificación UTF-8 en consola
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VAULT_ROOT = Path(__file__).resolve().parent.parent.parent
KANBAN_PENDIENTES = VAULT_ROOT / "03 Proyectos" / "Kanban" / "Pendientes"

def slugify(texto: str) -> str:
    s = texto.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:60].strip("-")

def crear_tarjeta(
    titulo: str,
    agent: str = "general",
    skill: str = "",
    prioridad: str = "🟡 Media",
    pipeline: list[str] | None = None,
    origen: str = "",
    objetivo: str = "",
    recibo: bool = False,
    entradas: list[str] | None = None,
    salidas: list[str] | None = None,
) -> Path:
    KANBAN_PENDIENTES.mkdir(parents=True, exist_ok=True)
    hoy = datetime.date.today().isoformat()
    slug = slugify(titulo)
    
    base_name = f"{hoy} - {slug}.md"
    file_path = KANBAN_PENDIENTES / base_name
    counter = 1
    while file_path.exists():
        file_path = KANBAN_PENDIENTES / f"{hoy} - {slug}-{counter}.md"
        counter += 1

    tags = ["tarea", "kanban", "headless"]
    if recibo:
        tags.extend(["validacion-humana", "recibo"])

    pipeline_block = ""
    if pipeline:
        pipeline_block = "pipeline:\n" + "\n".join(f"  - skill: {p.strip()}" for p in pipeline if p.strip()) + "\n"

    frontmatter = [
        "---",
        "type: Tarea",
        f'title: "{titulo}"',
        f"agent: {agent}",
    ]
    if skill:
        frontmatter.append(f"skill: {skill}")
    if pipeline_block:
        frontmatter.append(pipeline_block.strip())
    frontmatter.extend([
        f"prioridad: {prioridad}",
        "estado: 📥 Pendiente",
        f"fecha_creacion: {hoy}",
        "fecha_finalizacion:",
        f'responsable: "agente:{agent}"',
        f"tags: [{', '.join(tags)}]",
    ])
    if origen:
        frontmatter.append(f'resource: "{origen}"')
    else:
        frontmatter.append("resource:")
    frontmatter.append("---\n")

    cuerpo = [
        f"# {titulo}\n",
        "## 🎯 Objetivo",
        f"- {objetivo or 'Ejecutar la tarea encomendada bajo los contratos de las skills asignadas.'}\n",
    ]

    if pipeline:
        cuerpo.extend([
            "## ⛓️ Pipeline Multi-Paso",
            "```yaml",
            "pipeline:",
        ])
        for p in pipeline:
            cuerpo.append(f"  - skill: {p.strip()}")
        cuerpo.extend([
            "```",
            "El despachador ejecutará cada paso en orden; si alguno falla, detiene el flujo y reporta el error.\n",
        ])

    cuerpo.append("## 📥 Entradas (Inputs)")
    if entradas:
        for e in entradas:
            cuerpo.append(f"- {e}")
    elif origen:
        cuerpo.append(f"- Origen: `{origen}`")
    else:
        cuerpo.append("- A determinar por el agente asignado.")
    cuerpo.append("")

    cuerpo.append("## 📤 Salidas esperadas (Outputs)")
    if salidas:
        for s in salidas:
            cuerpo.append(f"- {s}")
    else:
        cuerpo.append("- Informe de ejecución y artefactos generados en la ruta correspondiente.")
    cuerpo.append("")

    cuerpo.extend([
        "## 📋 Criterios de aceptación",
        "- [ ] Ejecución completa de la skill/pipeline sin errores.",
        "- [ ] Generación de artefactos en las rutas esperadas.",
        "- [ ] Registro de informe de ejecución.",
        "",
        "## 📝 Registro de ejecución",
        "*(El despachador o el agente completará esta sección al finalizar)*\n",
    ])

    contenido_final = "\n".join(frontmatter) + "\n" + "\n".join(cuerpo)
    file_path.write_text(contenido_final, encoding="utf-8")
    return file_path

def main():
    parser = argparse.ArgumentParser(description="Crear una tarjeta en el tablero Headless Kanban de AI Vault Template")
    parser.add_argument("--titulo", required=True, help="Título de la tarjeta")
    parser.add_argument("--agent", default="general", help="Agente responsable (mantenedor, verifier, general)")
    parser.add_argument("--skill", default="", help="Skill principal a ejecutar")
    parser.add_argument("--prioridad", default="🟡 Media", choices=["🔥 Alta", "🟡 Media", "🟢 Baja"], help="Nivel de prioridad")
    parser.add_argument("--pipeline", default="", help="Secuencia de skills separadas por coma")
    parser.add_argument("--origen", default="", help="Ruta o URL del insumo de origen")
    parser.add_argument("--objetivo", default="", help="Descripción del objetivo de la tarjeta")
    parser.add_argument("--recibo", action="store_true", help="Marca la tarjeta como recibo para validación humana")
    parser.add_argument("--entradas", nargs="*", help="Lista de rutas o descripciones de entrada")
    parser.add_argument("--salidas", nargs="*", help="Lista de rutas esperadas de salida")

    args = parser.parse_args()
    pipeline_list = [p.strip() for p in args.pipeline.split(",") if p.strip()] if args.pipeline else None

    ruta_creada = crear_tarjeta(
        titulo=args.titulo,
        agent=args.agent,
        skill=args.skill,
        prioridad=args.prioridad,
        pipeline=pipeline_list,
        origen=args.origen,
        objetivo=args.objetivo,
        recibo=args.recibo,
        entradas=args.entradas,
        salidas=args.salidas,
    )

    rel_path = ruta_creada.relative_to(VAULT_ROOT).as_posix()
    print(f"OK: Tarjeta creada en [{args.titulo}](<{rel_path}>)")

if __name__ == "__main__":
    main()
