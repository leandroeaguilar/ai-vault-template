---
type: Tarea
title: "Título de la tarea"
agent: general # mantenedor | verifier | general
skill: check-links # skill a invocar si aplica
prioridad: 🟡 Media # 🔥 Alta | 🟡 Media | 🟢 Baja
estado: 📥 Pendiente # 📥 Pendiente | ⚙️ En Progreso | ✅ Hecho | ⚠️ Error
fecha_creacion: <% tp.date.now("YYYY-MM-DD") %>
fecha_finalizacion:
responsable: "agente"
tags: [tarea, kanban, headless]
resource:
---

# <% tp.file.title %>

## 🎯 Objetivo
- Descripción clara y concisa de lo que debe realizarse.

## 📥 Entradas (Inputs)
- Archivos o notas de insumo:
  - `00 Sistema/...` o `04 Knowledge/...`

## 📤 Salidas esperadas (Outputs)
- Archivos generados o actualizados.

## 📋 Criterios de aceptación
- [ ] Criterio 1
- [ ] Criterio 2

## 📝 Registro de ejecución
*(El agente completará esta sección al finalizar o dejar su recibo)*
