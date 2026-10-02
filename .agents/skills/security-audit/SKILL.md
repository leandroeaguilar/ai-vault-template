---
name: security-audit
description: Audita la superficie de seguridad del vault (secretos committeados, integridad del .gitignore, hooks y permisos).
tipo: meta
version: "1.0"
---

# Security Audit (Auditor de Seguridad)

Ejecutá esta skill para realizar una auditoría detective de seguridad en el vault.

## Cuándo usar
- Activación manual: cuando el usuario dice "auditoría de seguridad", "revisar secretos", "revisar permisos" o `/revisar-seguridad`.
- Activación periódica: durante revisiones de seguridad e higiene del repositorio.

## Entradas
- Lee el repositorio Git (`git log`), `.gitignore`, `.claude/hooks/` y permisos de archivos.

## Salidas
- Emite reporte de hallazgos por consola.
- Genera informe de auditoría si se detectan vulnerabilidades.

## Pasos

1. **Ejecutar el script de auditoría:**
   ```bash
   bash .claude/hooks/security-audit.sh
   ```
2. **Qué audita:**
   - Secretos o credenciales committeadas en el historial de Git.
   - Integridad del `.gitignore` (para asegurar que credenciales y archivos locales estén ignorados).
   - Configuración de Git Hooks (`core.hooksPath`).
   - Permisos y superficie expuesta.
3. Reportá los hallazgos al usuario con sus correspondientes recomendaciones de remediación.
