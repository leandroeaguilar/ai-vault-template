#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Mapa de mis agentes · dibuja en un HTML lo que tienes: skills, agentes, quién llama a
quién, lo que corre solo (cron, launchd, tareas programadas) y lo que te falta para
que todo eso sea un sistema. Solo LEE. No usa internet, no pide claves, no cambia nada.

  uv run mapa_agentes.py                      # rastrea LA CARPETA DESDE LA QUE LO EJECUTAS (y los sitios habituales
                                              # de Claude Code, Codex, Gemini CLI…) y deja el HTML en esa misma carpeta
  uv run mapa_agentes.py --raiz /ruta         # rastrea otra carpeta en vez de la actual (p. ej. tu vault de Obsidian)
  uv run mapa_agentes.py --salida mapa.html   # dónde dejar el HTML (por defecto, en la carpeta actual)
  uv run mapa_agentes.py --json               # además, un JSON con todo lo encontrado
"""
import argparse
import datetime as dt
import http.server
import json
import os
import re
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

# Windows: la consola clásica (cp1252/cp850) no sabe pintar «✓» ni «·» y el
# print final tumbaría el programa con el HTML ya escrito. Se fuerza UTF-8 y,
# si no se puede, se sustituye lo que no quepa. En Mac y Linux no cambia nada.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
HOY = dt.date.today()
# Versión pública del mapa: va bajo el título y en el nombre del fichero. Solo
# cambia cuando el autor lo diga (Marcos, 17-sep-2026).
VERSION = "0.1"
CASA = Path.home()
# Dónde suelen vivir las skills y los agentes de cada herramienta (solo lectura)
RAICES = {
    "Claude Code": [CASA / ".claude" / "skills", CASA / ".claude" / "agents", CASA / ".claude" / "commands", Path.cwd() / ".claude" / "skills", Path.cwd() / ".claude" / "agents", Path.cwd() / ".claude" / "commands"],
    "Codex": [CASA / ".codex" / "skills", CASA / ".codex" / "prompts", Path.cwd() / ".codex" / "skills"],
    "Gemini / Antigravity": [CASA / ".gemini" / "skills", CASA / ".gemini" / "commands", Path.cwd() / ".gemini" / "skills", Path.cwd() / ".gemini" / "commands", CASA / ".agents" / "skills", Path.cwd() / ".agents" / "skills"],
    "Cursor / otros": [Path.cwd() / ".cursor" / "rules", Path.cwd() / "04 Knowledge" / "Skills"],
}
FICHEROS_MEMORIA = [CASA / ".claude" / "CLAUDE.md", Path.cwd() / "CLAUDE.md", Path.cwd() / "AGENTS.md", Path.cwd() / "GEMINI.md"]
SALTAR = {"node_modules", ".git", ".venv", "venv", "__pycache__", "Library", ".Trash", "902 ARCHIVO", "_jubiladas", "_jubilados", "mapa-de-mis-agentes", "ENTREGABLES", "06 Raw", "99 Archivo", ".obsidian-RESPALDO-20260915"}


def frontmatter(texto):
    if not texto.startswith("---"):
        return {}, texto
    partes = texto.split("---", 2)
    if len(partes) < 3:
        return {}, texto
    fm = {}
    for ln in partes[1].splitlines():
        m = re.match(r"^([A-Za-z_áéíóúñ][\w áéíóúñ-]*):\s*(.*)$", ln)
        if m:
            fm[m.group(1).strip().lower()] = m.group(2).strip().strip('"').strip("'")
    return fm, partes[2]


def slug(p: Path):
    return p.parent.name if p.name.lower() == "skill.md" else p.stem


def leer_skill(p: Path, herramienta: str):
    try:
        t = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    fm, cuerpo = frontmatter(t)
    nombre = fm.get("name") or fm.get("nombre") or slug(p)
    desc = fm.get("description") or fm.get("descripción") or fm.get("descripcion") or ""
    if not desc:
        m = re.search(r"(?m)^(?!#)(?!\s*$)(.{20,})$", cuerpo)
        desc = m.group(1).strip() if m else ""
    st = p.stat()
    try:
        es_local = str(Path.cwd().resolve()) in str(p.resolve())
    except Exception:
        es_local = False
    return {"nombre": nombre, "ruta": str(p), "herramienta": herramienta, "descripcion": desc[:220],
            "palabras": len(t.split()), "kb": round(st.st_size / 1024, 1), "modificado": dt.date.fromtimestamp(st.st_mtime).isoformat(),
            "dias": (HOY - dt.date.fromtimestamp(st.st_mtime)).days, "texto": t.lower(), "texto_orig": t,
            "es_agente": ("agents" in p.parts) or bool(fm.get("perfil")) or p.name.upper() == "PERFIL.MD",
            "tiene_ejemplos": bool(re.search(r"(?i)ejemplo|example|```", t)), "tiene_cuando": bool(re.search(r"(?i)cu[aá]ndo usar|when to use|activaci[oó]n|triggers?", t)),
            "privado": (fm.get("visibilidad") or fm.get("visibility") or fm.get("private") or "").lower() in ("privado", "private", "true", "si", "sí", "yes"),
            "ejemplo": (fm.get("visibilidad") or "").lower() == "ejemplo",
            "es_local": es_local}


def rastrear(raices, herramienta, encontrados):
    for raiz in raices:
        if not raiz.exists():
            continue
        for p in raiz.rglob("*.md"):
            # Se salta por lo que hay DEBAJO de la raíz, no por el nombre de la propia
            # raíz (si la carpeta que se pasa se llama, p. ej., ENTREGABLES/…, cuenta).
            if any(s in SALTAR or s.upper().startswith("ENTREGABLE") for s in p.parts):
                continue
            if p.name.lower() in ("skill.md", "perfil.md") or ("agents" in p.parts and p.suffix == ".md") or ("commands" in p.parts) or ("prompts" in p.parts):
                if p.name.lower() in ("readme.md", "index.md"):
                    continue
                s = leer_skill(p, herramienta)
                if s and s["ruta"] not in encontrados:
                    encontrados[s["ruta"]] = s


EJEMPLOS_CRON = []   # Sin crones ficticios: el calendario muestra únicamente las tareas reales programadas en la máquina
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def regla_cron(expr):
    """De un cron de 5 campos a (cada, dia, hora) para pintarlo; lo raro se deja como «otro»."""
    try:
        mi, ho, dom, mon, dow = expr.split()[:5]
    except ValueError:
        return "otro", "", ""
    hora = f"{int(ho):02d}:{int(mi):02d}" if ho.isdigit() and mi.isdigit() else ""
    if dom == "*" and dow == "*":
        return ("dia" if hora else "otro"), "", hora
    if dom == "*" and dow.isdigit():
        return "semana", DIAS_ES[(int(dow) + 6) % 7], hora
    if dom.isdigit() and dow == "*":
        return "mes", dom, hora
    return "otro", "", hora


def salud_windows(item):
    """Semáforo de una tarea de Windows: ok · falla · nunca · corriendo · pausada (por LastTaskResult y estado)."""
    if str(item.get("State", "")).lower() == "disabled":
        return "pausada"
    res = item.get("LastResult")
    if res is None or not item.get("LastRun"):
        return "nunca"
    if res == 0:
        return "ok"
    if res == 0x41301:
        return "corriendo"
    if res == 0x41303:
        return "nunca"
    return "falla"


def _dias_cron(dow):
    """Campo día-de-semana de cron («*», «1-5», «0,3», «MON-FRI») a conjunto 0..6 (domingo = 0), o None si es «*»."""
    if dow in ("*", "?"):
        return None
    nombres = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
    num = lambda x: nombres.get(x.lower()[:3], None) if not x.isdigit() else int(x) % 7
    out = set()
    for parte in dow.split(","):
        if "-" in parte:
            a, b = (num(x) for x in parte.split("-", 1))
            if a is None or b is None:
                return None
            out.update(range(a, (b if b >= a else b + 7) + 1))
        else:
            n = num(parte)
            if n is None:
                return None
            out.add(n)
    return {d % 7 for d in out}


def _rutina(fuente, nombre, cada, dias, dia_mes, hora, que, salud, cuando, **extra):
    """Normaliza una rutina (local o de la nube) al formato de `tareas` que pinta el calendario."""
    NOM = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]
    t = {"fuente": fuente, "nombre": nombre[:60], "que": que[:200], "hora": hora, "salud": salud, "cuando": cuando, "dia": ""}
    if cada == "mes":
        t.update(cada="mes", dia=str(dia_mes))
    elif dias and len(dias) == 1:
        t.update(cada="semana", dia=NOM[next(iter(dias))])
    elif dias and len(dias) < 7:
        orden = sorted(dias, key=lambda d: (d + 6) % 7)
        t.update(cada="dia", dias=orden, dias_txt=("lun–vie" if set(dias) == {1, 2, 3, 4, 5} else ", ".join(NOM[d][:3] for d in orden)))
    else:
        t.update(cada="dia")
    t.update({k: v for k, v in extra.items() if v})
    return t


def rutinas_claude_nube(raiz):
    """Rutinas de Claude en la nube (claude.ai/code → /schedule). El script no puede llamar a esa API (el token OAuth
    vive dentro de Claude Code), así que lee el snapshot `.vault-meta/rutinas-cloud.json` que refresca la skill /mapa
    con RemoteTrigger. El cron viene en UTC: se pasa a la hora local de esta máquina."""
    p = Path(raiz) / ".vault-meta" / "rutinas-cloud.json"
    try:
        snap = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    off = dt.datetime.now().astimezone().utcoffset() or dt.timedelta(0)
    off_min = int(off.total_seconds() // 60)
    salud_de = {"ROUTINE_RUN_STATUS_SUCCEEDED": "ok", "ROUTINE_RUN_STATUS_FAILED": "falla", "ROUTINE_RUN_STATUS_RUNNING": "corriendo"}
    out = []
    for r in snap.get("rutinas", []):
        try:
            mi, ho, dom, _mon, dow = r.get("cron", "").split()[:5]
        except ValueError:
            continue
        hora, corrimiento = "", 0
        if mi.isdigit() and ho.isdigit():
            total = int(ho) * 60 + int(mi) + off_min
            corrimiento, resto = divmod(total, 24 * 60)
            hora = f"{resto // 60:02d}:{resto % 60:02d}"
        dias = _dias_cron(dow)
        if dias is not None:
            dias = {(d + corrimiento) % 7 for d in dias}
        salud = "pausada" if not r.get("habilitada", True) else salud_de.get(r.get("estado_ultima", ""), "nunca")
        es_mes = dom.isdigit() and dow in ("*", "?")
        cuando = f"cron {r.get('cron')} UTC"
        out.append(_rutina("Claude (nube)", r.get("nombre", "rutina"), "mes" if es_mes else "dia", dias, (int(dom) + corrimiento) if es_mes else "", hora,
                           r.get("que", ""), salud, cuando, ultima=_local(r.get("ultima")), proxima=_local(r.get("proxima")), url=r.get("url", "")))
    return out


def _local(iso):
    """ISO UTC («2026-10-05T12:09:32.65Z») a «2026-10-05T09:09» en hora local; vacío si no se entiende."""
    if not iso:
        return ""
    try:
        return dt.datetime.fromisoformat(iso[:19] + "+00:00").astimezone().strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return ""


def rutinas_externas(raiz):
    """Rutinas de otras plataformas sin API para listarlas (Gemini «acciones programadas», ChatGPT «tareas»):
    se cargan a mano en la tabla de `01 Index/Registro de Rutinas Externas.md`.
    Columnas: Plataforma | Rutina | Cadencia (diaria · lun-vie · semanal · mensual) | Día | Hora | Qué hace | Activa.
    Vive en 01 Index y no en 00 Sistema: 00 Sistema es framework y update.sh lo pisaría con la tabla vacía."""
    texto = None
    for capa in ("01 Index", "00 Sistema"):
        try:
            texto = (Path(raiz) / capa / "Registro de Rutinas Externas.md").read_text(encoding="utf-8")
            break
        except OSError:
            pass
    if texto is None:
        return []
    NOM = {"domingo": 0, "lunes": 1, "martes": 2, "miercoles": 3, "miércoles": 3, "jueves": 4, "viernes": 5, "sabado": 6, "sábado": 6}
    out = []
    for ln in texto.splitlines():
        celdas = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(celdas) < 7 or not ln.lstrip().startswith("|") or celdas[0].lower() in ("plataforma", "") or set(celdas[0]) <= set("-: "):
            continue
        plat, nombre, cad, dia, hora, que, activa = celdas[:7]
        cad = cad.lower()
        dias, cada, dia_mes = None, "dia", ""
        if cad.startswith("lun"):
            dias = {1, 2, 3, 4, 5}
        elif cad.startswith("seman"):
            n = NOM.get(dia.lower())
            if n is None:
                continue
            dias = {n}
        elif cad.startswith("mens"):
            cada, dia_mes = "mes", dia
        salud = "pausada" if activa.lower() in ("no", "❌", "pausada") else "externa"
        out.append(_rutina(plat, nombre, cada, dias, dia_mes, hora.zfill(5) if re.fullmatch(r"\d{1,2}:\d{2}", hora) else "", que, salud, f"{cad} {dia} {hora}".strip()))
    return out


def cron_y_launchd():
    tareas = []
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        for ln in r.stdout.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and len(ln.split()) >= 6:
                partes = ln.split(None, 5)
                cada, dia, hora = regla_cron(" ".join(partes[:5]))
                tareas.append({"fuente": "cron", "cuando": " ".join(partes[:5]), "que": partes[5][:160], "cada": cada, "dia": dia, "hora": hora, "nombre": partes[5].split("/")[-1][:40]})
    except Exception:  # noqa: BLE001
        pass
    for carpeta in (CASA / "Library" / "LaunchAgents",):
        if carpeta.exists():
            for p in carpeta.glob("*.plist"):
                try:
                    t = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if not re.search(r"(?i)claude|agent|nexus|skill|gemini|codex|hermes|openclaw|obsidian|python|uv ", t):
                    continue
                hora = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", t); minu = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", t)
                inter = re.search(r"<key>StartInterval</key>\s*<integer>(\d+)</integer>", t)
                cuando = f"{int(hora.group(1)):02d}:{int(minu.group(1)) if minu else 0:02d}" if hora else (f"cada {int(inter.group(1)) // 60} min" if inter else "al arrancar")
                wd = re.search(r"<key>Weekday</key>\s*<integer>(\d+)</integer>", t)
                prog = re.findall(r"<string>([^<]{3,})</string>", t)
                tareas.append({"fuente": "launchd", "cuando": cuando, "que": (p.stem + " · " + " ".join(x for x in prog if "/" in x or x.endswith(".py") or x.endswith(".sh"))[:120]).strip(),
                               "cada": ("semana" if (hora and wd) else "dia" if hora else "otro"), "dia": (DIAS_ES[(int(wd.group(1)) + 6) % 7] if wd else ""), "hora": (cuando if hora else ""), "nombre": p.stem.split(".")[-1][:40]})
    if sys.platform.startswith("win"):
        try:
            ps_script = """
            $tasks = Get-ScheduledTask -TaskName 'SistemaMaestro-*' -ErrorAction SilentlyContinue
            $list = @()
            foreach ($t in $tasks) {
                $tr = $t.Triggers[0]
                $action = $t.Actions[0]
                $execStr = if ($action) { "$($action.Execute) $($action.Arguments)" } else { "" }
                $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -ErrorAction SilentlyContinue
                $list += [PSCustomObject]@{
                    Name = $t.TaskName
                    State = [string]$t.State
                    Start = $tr.StartBoundary
                    Interval = $tr.Repetition.Interval
                    DaysOfWeek = [string]$tr.DaysOfWeek
                    Trigger = $tr.CimClass.CimClassName
                    Exec = $execStr
                    LastRun = if ($info -and $info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString('yyyy-MM-ddTHH:mm') } else { '' }
                    NextRun = if ($info -and $info.NextRunTime) { $info.NextRunTime.ToString('yyyy-MM-ddTHH:mm') } else { '' }
                    LastResult = if ($info) { [int64]$info.LastTaskResult } else { $null }
                }
            }
            $list | ConvertTo-Json -Compress
            """
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=12)
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]
                    dow_map = {"1": "domingo", "2": "lunes", "4": "martes", "8": "miércoles", "16": "jueves", "32": "viernes", "64": "sábado"}
                    for item in data:
                        nom = item.get("Name", "")
                        start = item.get("Start") or ""
                        hora = ""
                        if "T" in start:
                            hora = start.split("T")[1][:5]
                        tr_type = item.get("Trigger", "")
                        interval = item.get("Interval") or ""
                        dow = str(item.get("DaysOfWeek") or "")

                        cada = "dia"
                        dia = ""
                        desc_amigable = nom
                        if "Cerrador" in nom:
                            desc_amigable = "Cerrador de Jornada · Resumen diario de git, notas y bitácora"
                        elif "Mantenedor" in nom:
                            desc_amigable = "Mantenimiento Nocturno · Auditoría de scratch, enlaces y mapa"
                        elif "ProcesadorRaw" in nom:
                            desc_amigable = "Procesador de Capturas Raw · Escaneo e ingesta de material pendiente"
                        elif "RunnerKanban" in nom:
                            desc_amigable = "Runner Kanban Autónomo · Despacho de tareas desatendidas y Toasts"
                        elif "Vigilante" in nom:
                            desc_amigable = "Vigilante del Sistema · Watchdog de salud de tareas y alertas"
                        elif "ResumenAgentes" in nom:
                            desc_amigable = "Resumen Semanal de Agentes · Balance de rendimiento del enjambre y Kanban"

                        if "MSFT_TaskDailyTrigger" in tr_type:
                            cada = "dia"
                        elif "MSFT_TaskWeeklyTrigger" in tr_type:
                            cada = "semana"
                            dia = dow_map.get(dow, "lunes")
                        elif interval or "PT" in interval:
                            cada = "dia"
                            desc_amigable += f" (cada {interval.replace('PT','').replace('H','h').replace('M','m')})"

                        limpio_nom = nom.replace("SistemaMaestro-", "")
                        cuando_str = f"cada día a las {hora}" if cada == "dia" and not interval else (f"cada {dia} a las {hora}" if cada == "semana" else f"cada {interval.replace('PT','').replace('H','h')}")
                        tareas.append({
                            "fuente": "tareas programadas",
                            "cuando": cuando_str,
                            "que": desc_amigable,
                            "cada": cada,
                            "dia": dia,
                            "hora": hora,
                            "intervalo": interval.replace("PT", "").replace("H", "h").replace("M", "m") if interval else "",
                            "nombre": limpio_nom,
                            "estado": item.get("State", "Ready"),
                            "ultima": item.get("LastRun") or "",
                            "proxima": item.get("NextRun") or "",
                            "salud": salud_windows(item),
                        })
                except Exception:
                    pass
        except Exception:
            pass
    return tareas


def programadas_en_texto(skills):
    """Skills que declaran un horario en su propio texto, y solo si cadencia y hora van JUNTAS en la misma frase
    («cada día a las 02:30», «los lunes a las 08:00», «daily at 07:00», «programada: cada viernes 04:00»).
    La palabra «diario» suelta (un correo diario, la carpeta DIARIO) o una hora suelta (un registro) NO cuentan:
    con eso salían decenas de puntos falsos (cicatriz 2026-09-16)."""
    DIAS = "lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo"
    RX = re.compile(r"(?i)(?P<cad>cada d[ií]a|todos los d[ií]as|diariamente|cada noche|cada madrugada|cada semana|semanalmente|cada (?:" + DIAS + r")|los (?:" + DIAS + r")s?|daily|weekly|every day|every (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))"
                    r"[^\n.;]{0,40}?(?:a las|at|,|:|\s)\s*(?P<h>[01]?\d|2[0-3])[:.h](?P<m>[0-5]\d)")
    out = []
    for s in skills:
        t = s.get("texto_orig") or s["texto"]
        for ln in t.splitlines():
            if re.search(r"(?i)^\s*-\s*\*\*v\d|registro|cicatriz|estreno", ln):
                continue   # líneas de historial: horas de cierres, no programaciones
            m = RX.search(ln)
            if not m:
                continue
            cad = m.group("cad").lower()
            md = re.search(DIAS, cad)
            dia = md.group(0).replace("miercoles", "miércoles").replace("sabado", "sábado") if md else ""
            cada = "semana" if (dia or "semana" in cad or "weekly" in cad) else "dia"
            out.append({"skill": s["nombre"], "dice": m.group(0).strip(), "cada": cada, "dia": dia, "hora": f"{int(m.group('h')):02d}:{m.group('m')}", "que": s["descripcion"]})
            break
    return out


# Verbos que convierten un nombre en una LLAMADA de verdad (una instrucción de usar la otra skill).
# Sin uno de estos delante o detrás, es solo una MENCIÓN (una lista, un «no confundir con», una explicación).
VERBOS_LLAMADA = r"(monta(r)?|montando|ejecuta(r)?|ejecutando|usa(r)?|usando|lanza(r)?|invoca(r)?|llama(r)? a|carga(r)?|aplica(r)?|run|use|invoke|call|load|apply|delega(r)? en|pasa(r)? a)"


def relaciones(skills):
    """(origen, destino, fuerza): fuerza «llama» si hay verbo de ejecución, ruta a su carpeta o enlace a su SKILL.md
    a menos de 80 caracteres del nombre; «menciona» si solo aparece el nombre."""
    nombres = {s["nombre"].lower(): s for s in skills if len(s["nombre"]) >= 4}
    aristas = []
    for s in skills:
        t = s["texto"]
        for n, o in nombres.items():
            if o is s:
                continue
            ok = False; fuerte = False
            for m in re.finditer(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", t):
                ok = True
                ctx = t[max(0, m.start() - 80):m.end() + 80]
                if re.search(VERBOS_LLAMADA + r"\s+(la\s+|el\s+|the\s+)?(skill|habilidad|herramienta)?\s*[`«\"']?" + re.escape(n), ctx) \
                   or re.search(re.escape(n) + r"/(skill\.md|[\w.-]+\.py)", ctx) or re.search(r"uv run[^\n]*" + re.escape(n), ctx) \
                   or re.search(r"\[\[[^\]]*" + re.escape(n) + r"[^\]]*skill", ctx) or re.search(r"skills:\s*\n(\s*-\s*[\w-]+\n)*\s*-\s*" + re.escape(n), t):
                    fuerte = True; break
            if ok:
                # lo que se nombra para decir que NO es lo mismo o que está jubilado no cuenta como llamada
                if fuerte and re.search(r"(no confundir|no es lo mismo|jubilad|eclipsad|sustituye a|antes se llamaba|en vez de)[^\n]{0,60}" + re.escape(n), t):
                    fuerte = False
                aristas.append((s["nombre"], o["nombre"], "llama" if fuerte else "menciona"))
    return aristas


# ─── entradas y salidas inferidas del texto de cada skill ───
EXT = r"(?:md|json|csv|yml|yaml|txt|html|pdf|png|jpg|log|jsonl|base|xlsx|docx)"
# Rutas que parecen rutas de verdad: absolutas o con ~ o ./; carpetas numeradas de un vault (001 CAPTURA/…);
# ficheros relativos con extensión de datos. Nada de fracciones (4/10) ni de «a/b» sueltos en prosa.
RE_RUTA = re.compile(r"(?<![\w/])((?:~|\.{1,2})?/(?:[\w .áéíóúñÁÉÍÓÚÑ()-]+/)*[\w .áéíóúñÁÉÍÓÚÑ()*-]*"
                     r"|\d{2,4} [A-ZÁÉÍÓÚÑa-záéíóúñ][\w .áéíóúñÁÉÍÓÚÑ()-]*(?:/[\w .áéíóúñÁÉÍÓÚÑ()*<>-]*)*"
                     r"|(?:[\w.-]+/)+[\w .<>*-]+\." + EXT + r"\b"
                     r"|[\w<>*.-]+\." + EXT + r"\b)")
OCULTAR = ("_privada", "/tmp/", "/.cache/", ".env")   # nunca se enseñan rutas de credenciales ni temporales
RE_URL = re.compile(r"https?://[\w.-]+(?:/[\w./?=&%-]*)?")
V_LEE = r"(lee|leer|leyendo|consulta|consultar|carga|cargar|abre|abrir|recibe|recibir|toma|tomar|busca|buscar|rastrea|barre|importa|descarga|extrae|read|reads|load|loads|open|opens|fetch|parse|input|entrada|entradas|fuente|desde)"
V_ESC = r"(escribe|escribir|guarda|guardar|crea|crear|genera|generar|produce|deja|dejar|actualiza|añade|anexa|exporta|publica|envía|mueve|renombra|write|writes|save|saves|create|creates|generate|output|salida|salidas|resultado|destino|hacia|en)"
HERRAMIENTAS = [("uv run", "uv (script Python)"), ("python", "Python"), ("curl", "curl (HTTP)"), ("yt-dlp", "yt-dlp"), ("ffmpeg", "ffmpeg"), ("obsidian ", "CLI de Obsidian"), ("git ", "git"), ("api", "una API externa"), ("telegram", "Telegram"), ("notion", "Notion"), ("kit.com", "Kit"), ("youtube", "YouTube"), ("gmail", "Gmail"), ("google", "Google"), ("openrouter", "OpenRouter"), ("supabase", "Supabase"), ("n8n", "n8n"), ("sqlite", "SQLite"), ("excel", "Excel"), ("csv", "CSV")]


def _limpia(r):
    r = r.strip().strip("`'\"()[],.;:")
    if r.startswith("/ ") or r.startswith("/\u00a0"):
        return ""
    # una ruta con espacios (carpetas de vault) termina donde empieza la prosa
    r = re.split(r"\)|\s+y\s+|\s+o\s+|\.\s|:\s|\s[—–-]\s|,\s|\s+(?:que|con|para|sin|donde|si)\s", r)[0].strip()
    r = re.sub(r"\s*\(.*$", "", r) if r.count("(") > r.count(")") else r
    if re.fullmatch(r"\d+/\d+", r) or "|" in r or len(r) < 3 or len(r) > 90 or r.lower().startswith(("http", "www")):
        return ""
    low = r.lower()
    if low.endswith((".py", ".sh", "skill.md", "perfil.md")) or any(o in low for o in OCULTAR):
        return ""
    return r.rstrip("/") if r.count("/") > 0 else r


def entradas_salidas(s):
    """Qué lee y qué produce una skill, inferido de su texto: rutas cerca de verbos de lectura o escritura,
    URLs, herramientas. Cada dato lleva su confianza: «declarado» (ruta escrita), «inferido» (verbo + tipo
    de cosa) o «supuesto» (solo por el tipo de skill). Si no hay nada, se dice."""
    t = s.get("texto_orig") or s["texto"]; lineas = [ln for ln in t.splitlines() if ln.strip() and not ln.strip().startswith(("#!", "# ///", "//"))]
    entradas, salidas = {}, {}
    def pon(dic, clave, nivel, por):
        clave = clave[:90]
        if clave and (clave not in dic or ["supuesto", "inferido", "declarado"].index(nivel) > ["supuesto", "inferido", "declarado"].index(dic[clave][0])):
            dic[clave] = (nivel, por[:80])
    seccion = None   # «in» / «out» bajo un título ## Entradas / ## Salidas (contrato Nexus): manda el título, no el verbo
    for ln in lineas:
        low = ln.lower()
        h = re.match(r"\s*#{1,6}\s+(.*)", ln)
        if h:
            th = h.group(1).lower()
            seccion = "in" if re.search(r"entradas?\b|inputs?\b", th) else "out" if re.search(r"salidas?\b|outputs?\b", th) else None
            continue
        lee = re.search(V_LEE, low); esc = re.search(V_ESC, low)
        rutas = [r for r in (_limpia(m.group(0)) for m in RE_RUTA.finditer(ln)) if r]
        for r in rutas:
            if seccion:
                pon(entradas if seccion == "in" else salidas, r, "declarado", ln.strip())
            elif esc and (not lee or esc.start() < lee.start()):
                pon(salidas, r, "declarado", ln.strip())
            elif lee:
                pon(entradas, r, "declarado", ln.strip())
            else:
                pon(entradas, r, "inferido", "ruta nombrada sin verbo: " + ln.strip())
        for u in RE_URL.findall(ln):
            dom = re.sub(r"^https?://", "", u).split("/")[0]
            if lee or "api" in low or "descarga" in low or "fetch" in low:
                pon(entradas, "web: " + dom, "inferido", ln.strip())
            elif esc:
                pon(salidas, "web: " + dom, "inferido", ln.strip())
    # frontmatter con entradas/salidas explícitas (contratos tipo Nexus u otros)
    fm = t.split("---", 2)[1] if t.startswith("---") else ""
    for m in re.finditer(r"(?m)^\s*(?:-\s*)?(?:defecto|default|entrada|input|fuente|source):\s*([^\n]+)$", fm):
        pon(entradas, _limpia(m.group(1)) or m.group(1)[:80], "declarado", "frontmatter")
    for m in re.finditer(r"(?m)^\s*(?:-\s*)?(?:salida|output|destino|target|patron_fichero):\s*([^\n]+)$", fm):
        pon(salidas, _limpia(m.group(1)) or m.group(1)[:80], "declarado", "frontmatter")
    herr = [nombre for clave, nombre in HERRAMIENTAS if clave in t]
    # supuestos por tipo de skill, cuando no hay nada declarado
    tipo = (s["descripcion"] + " " + s["nombre"]).lower()
    if not entradas:
        if re.search(r"transcri|v[ií]deo|youtube|audio", tipo): pon(entradas, "un vídeo o audio (URL o fichero)", "supuesto", "por el tipo de skill")
        elif re.search(r"resum|analiz|audit|revis|lee|libro|pdf|texto|nota", tipo): pon(entradas, "un texto o una nota (el que le pases)", "supuesto", "por el tipo de skill")
        elif re.search(r"idea|correo|gui[oó]n|art[ií]culo|escrib|redact", tipo): pon(entradas, "una idea o un tema dictado", "supuesto", "por el tipo de skill")
        else: pon(entradas, "lo que le digas en la conversación", "supuesto", "no declara nada: se le pasa por chat")
    if not salidas:
        if re.search(r"resum|informe|audit|analiz|report", tipo): pon(salidas, "una nota de informe o resumen (sitio sin declarar)", "supuesto", "por el tipo de skill")
        elif re.search(r"correo|email|mail", tipo): pon(salidas, "un correo (borrador o envío; sin declarar dónde)", "supuesto", "por el tipo de skill")
        elif re.search(r"gui[oó]n|art[ií]culo|post|escrib|redact|genera|crea", tipo): pon(salidas, "un texto nuevo (sitio sin declarar)", "supuesto", "por el tipo de skill")
        elif re.search(r"tarea|kanban|tablero", tipo): pon(salidas, "una tarea o tarjeta (sitio sin declarar)", "supuesto", "por el tipo de skill")
        else: pon(salidas, "solo una respuesta en el chat: no deja nada escrito", "supuesto", "no declara ninguna salida")
    def lista(d): return [{"que": k, "nivel": v[0], "por": v[1]} for k, v in sorted(d.items(), key=lambda kv: ["declarado", "inferido", "supuesto"].index(kv[1][0]))][:8]
    return {"entradas": lista(entradas), "salidas": lista(salidas), "herramientas": herr[:6],
            "opaca": all(v[0] == "supuesto" for v in entradas.values()) and all(v[0] == "supuesto" for v in salidas.values())}


def semaforo(skills, aristas):
    citadas = {b for _, b, fz in aristas if fz == "llama"}
    avisos = {}
    nombres = [s["nombre"].lower() for s in skills]
    for s in skills:
        a = []
        if not s["descripcion"]:
            a.append("sin descripción: tu agente no sabe cuándo usarla")
        if not s["tiene_cuando"]:
            a.append("no dice cuándo se activa")
        if s["dias"] > 90:
            a.append(f"sin tocar desde hace {s['dias']} días")
        if s["palabras"] > 3000:
            a.append(f"muy larga ({s['palabras']} palabras): cuesta contexto cada vez que se carga")
        if s["palabras"] < 60:
            a.append("casi vacía")
        base = re.sub(r"[-_ ]?(v?\d+|old|copy|copia|nuevo|new|2)$", "", s["nombre"].lower())
        gem = [n for n in nombres if n != s["nombre"].lower() and (n.startswith(base) or base.startswith(n)) and len(base) >= 5]
        if gem:
            a.append("parece duplicada de: " + ", ".join(sorted(set(gem))[:3]))
        if s["nombre"] not in citadas and not s["es_agente"]:
            a.append("nadie la llama: huérfana (solo la usas tú a mano, si te acuerdas)")
        avisos[s["ruta"]] = a
    return avisos


# Flujos de ejemplo (del sistema del autor, con nombres genéricos): lo que ve en gris quien no tiene ninguno.
def leer_agentes(raiz: Path) -> list:
    """Lee las fichas de agentes reales de Sistema Maestro en .claude/agents/*.md."""
    agents_dir = raiz / ".claude" / "agents"
    if not agents_dir.exists():
        return []
    
    agentes = []
    cadencias = {
        "cerrador": "Diaria 23:59 (Task Scheduler)",
        "mantenedor": "Diaria 02:30 (Task Scheduler)",
        "procesador-raw": "Semanal Lunes 08:00 (Task Scheduler)",
        "vigilante": "Diaria 09:00 (Task Scheduler)",
        "redactor": "Bajo demanda (/redactar o Kanban)",
        "verifier": "Pre-commit advisory (Git gate)",
        "bibliotecario": "Bajo demanda (Query documental)"
    }
    roles = {
        "cerrador": "Cierre nocturno de jornada y síntesis en nota diaria",
        "mantenedor": "Integridad del vault, auditoría de scratch y mapa",
        "procesador-raw": "Curaduría e ingesta de capturas sin procesar",
        "vigilante": "Watchdog de salud de tareas y alertas del sistema",
        "redactor": "Redacción multicanal desde notas permanentes",
        "verifier": "Juez de calidad pre-commit de conocimiento (Tier 2)",
        "bibliotecario": "Consultor documental con citación de notas reales"
    }
    
    for f in sorted(agents_dir.glob("*.md")):
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        fm, cuerpo = frontmatter(txt)
        name = fm.get("name", f.stem)
        desc = fm.get("description", roles.get(name, ""))
        model = fm.get("model", "haiku")
        tools = fm.get("tools", "")
        if isinstance(tools, str):
            tools_list = [t.strip() for t in tools.split(",") if t.strip()]
        else:
            tools_list = tools or []
        color = fm.get("color", "blue")
        
        agentes.append({
            "name": name,
            "filename": f.name,
            "description": desc.strip().replace("\n", " "),
            "model": model,
            "tools": tools_list,
            "color": color,
            "cadencia": cadencias.get(name, "Bajo demanda"),
            "rol": roles.get(name, desc[:120]),
            "cuerpo": cuerpo[:800].strip()
        })
    return agentes


def leer_pipelines_kanban(raiz: Path) -> list:
    """Extrae pipelines declarados en tarjetas Kanban (pipeline: [...])."""
    kanban_dir = raiz / "03 Proyectos" / "Kanban"
    pipelines = []
    if not kanban_dir.exists():
        return pipelines
    for folder in ("Pendientes", "En_Progreso", "Hecho"):
        d = kanban_dir / folder
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "pipeline:" in txt:
                fm, _ = frontmatter(txt)
                title = fm.get("title", f.stem)
                steps = []
                in_p = False
                for line in txt.splitlines():
                    ls = line.strip()
                    if ls.startswith("pipeline:"):
                        in_p = True
                        continue
                    if in_p:
                        if ls.startswith("-") or ls.startswith("  -"):
                            val = ls.lstrip("- ").strip()
                            if ":" in val:
                                k, v = val.split(":", 1)
                                # Sin f-string: comillas escapadas dentro de {} exigen Python 3.12 (el script declara >=3.10).
                                steps.append(k.strip() + ": " + v.strip().strip(chr(34) + chr(39)))
                            else:
                                steps.append(val)
                        elif ls and not ls.startswith("#") and ":" in ls:
                            in_p = False
                if steps:
                    pipelines.append({
                        "card": f.name,
                        "title": title,
                        "col": folder,
                        "steps": steps,
                        "prioridad": fm.get("prioridad", "Media"),
                        "estado": fm.get("estado", folder)
                    })
    return pipelines


def leer_flujos_yml(raiz):
    """Lee `flujos.yml` si existe (el formato del mapa de agentes atómicos) sin librería YAML:
    solo nombre, resumen, estado, director, sirve_a, programada y pasos[perfil, nota, falta]."""
    rutas = list(raiz.glob("**/flujos.yml")) if raiz and raiz.exists() else []
    if not rutas:
        return []
    flujos, f, paso = [], None, None
    for ln in rutas[0].read_text(encoding="utf-8", errors="ignore").splitlines():
        if ln.strip().startswith("#"):
            continue
        m = re.match(r"^  - nombre:\s*(.+)$", ln)
        if m:
            f = {"nombre": m.group(1).strip().strip('"'), "resumen": "", "estado": "", "director": None, "sirve_a": "", "programada": None, "pasos": []}; flujos.append(f); paso = None; continue
        if f is None:
            continue
        m = re.match(r"^    (resumen|estado|director|sirve_a|programada):\s*(.*)$", ln)
        if m:
            v = m.group(2).strip().strip('"'); f[m.group(1)] = None if v in ("null", "") else v; continue
        m = re.match(r"^      - perfil:\s*(.+)$", ln)
        if m:
            paso = {"perfil": m.group(1).strip(), "nota": "", "falta": False}; f["pasos"].append(paso); continue
        m = re.match(r"^        (nota|falta):\s*(.*)$", ln)
        if m and paso is not None:
            v = m.group(2).strip().strip('"')
            if m.group(1) == "falta":
                paso["falta"] = v.lower() in ("si", "sí", "true", "yes")
            else:
                paso["nota"] = v[:120]
    return flujos


def _clave_ruta(q):
    """Normaliza una entrada/salida para compararlas: minúsculas, sin plantillas (AAAA-MM-DD, <título>), sin extensión final."""
    q = q.lower().strip()
    q = re.sub(r"<[^>]*>|aaaa-mm-dd|yyyy-mm-dd|\d{4}-\d{2}-\d{2}|\*", "", q)
    return q.strip(" /_-")


def encaja(salida, entrada):
    """¿Lo que deja una skill es lo que lee otra? Misma ruta, o una carpeta que contiene a la otra, o el mismo fichero."""
    a, b = _clave_ruta(salida), _clave_ruta(entrada)
    if not a or not b or len(a) < 4 or len(b) < 4:
        return False
    # carpetas de primer nivel («050 activos») enlazarían con todo: hace falta al menos una subcarpeta o un fichero
    if a == b and (a.count("/") >= 1 or "." in a):
        return True
    if (a.startswith(b + "/") or b.startswith(a + "/")) and min(a.count("/"), b.count("/")) >= 1:
        return True
    fa, fb = a.rsplit("/", 1)[-1], b.rsplit("/", 1)[-1]
    return "." in fa and fa == fb and len(fa) > 6


def inferir_flujos(skills, aristas):
    """Flujos POSIBLES sin contratos: se encadenan skills cuando la salida de una es la entrada de otra
    (rutas declaradas o inferidas) o cuando una llama a la otra de verdad. Cadenas de 2 a 5 pasos."""
    sk = [x for x in skills if not x["es_agente"]]
    por_nombre = {x["nombre"]: x for x in sk}
    sig = {x["nombre"]: {} for x in sk}   # origen → {destino: motivo}
    for a in sk:
        for b in sk:
            if a is b:
                continue
            for sa in a["es"]["salidas"]:
                if sa["nivel"] == "supuesto":
                    continue
                for eb in b["es"]["entradas"]:
                    if eb["nivel"] != "supuesto" and encaja(sa["que"], eb["que"]):
                        sig[a["nombre"]].setdefault(b["nombre"], f"{a['nombre']} deja «{sa['que']}» y {b['nombre']} lo lee")
    for a, b, fz in aristas:
        if fz == "llama" and a in sig and b in por_nombre:
            sig[a].setdefault(b, f"{a} llama a {b}")
    entrantes = {n: 0 for n in sig}
    for a, d in sig.items():
        for b in d:
            entrantes[b] += 1
    cadenas = []
    def anda(camino):
        ult = camino[-1]
        salidas = [b for b in sig[ult] if b not in camino]
        if not salidas or len(camino) >= 5:
            if len(camino) >= 2:
                cadenas.append(list(camino))
            return
        for b in sorted(salidas):
            anda(camino + [b])
    for n in sorted(sig):
        if entrantes[n] == 0 and sig[n]:
            cadenas_n = []
            def anda_n(camino):
                ult = camino[-1]; salidas = [b for b in sig[ult] if b not in camino]
                if not salidas or len(camino) >= 5:
                    if len(camino) >= 2: cadenas_n.append(list(camino))
                    return
                for b in sorted(salidas): anda_n(camino + [b])
            anda_n([n])
            if cadenas_n:
                cadenas.append(max(cadenas_n, key=len))   # una cadena por origen: la más larga
    # sin cadenas contenidas en otras; las 12 más largas
    cadenas.sort(key=len, reverse=True)
    unicas = []
    for c in cadenas:
        if not any(set(c) <= set(u) for u in unicas):
            unicas.append(c)
    flujos = []
    for c in unicas[:12]:
        pasos = []
        for i, n in enumerate(c):
            motivo = sig[c[i - 1]][n] if i else ""
            pasos.append({"perfil": n, "nota": (motivo if i else (por_nombre[n]["descripcion"] or ""))[:120], "falta": False})
        primero, ultimo = por_nombre[c[0]], por_nombre[c[-1]]
        entrega = next((x["que"] for x in ultimo["es"]["salidas"] if x["nivel"] != "supuesto"), "")
        flujos.append({"nombre": f"{c[0]} → {c[-1]}", "resumen": f"Cadena posible de {len(c)} skills: empieza leyendo " + (next((x["que"] for x in primero["es"]["entradas"] if x["nivel"] != "supuesto"), "lo que le pases")) + " y termina dejando " + (entrega or "su resultado en un sitio sin declarar") + ". Inferida: nadie la ha declarado; es lo que las skills dicen que leen y escriben.",
                       "estado": "inferido", "director": None, "sirve_a": (re.match(r"^(\d{2,4} [^/]+)", entrega).group(1) if entrega and re.match(r"^(\d{2,4} [^/]+)", entrega) else ""), "programada": None, "pasos": pasos})
    return flujos


def detectar_sistema(raiz):
    """¿Hay ya un sistema de agentes atómicos (tablero, programadas, flujos)? Se mira sin leer contenido."""
    pistas = {"tablero": False, "programadas": False, "flujos": False, "vigilante": False}
    for base in ([raiz] if raiz else []) + [Path.cwd(), CASA]:
        if not base or not base.exists():
            continue
        if (base / "000 NEXUS" / "KANBAN").exists() or any(base.glob("**/KANBAN/pendientes")):
            pistas["tablero"] = True
        if any(base.glob("**/programadas/*.md")) or any(base.glob("**/programadas.yml")):
            pistas["programadas"] = True
        if any(base.glob("**/flujos.yml")):
            pistas["flujos"] = True
        if any(base.glob("**/vigilante*")):
            pistas["vigilante"] = True
        break
    return pistas


# ─── actores: lo que hay alrededor de tus agentes, en cualquier máquina ───
# Marcos, 17-sep-2026: «que sea capaz de identificar lo que tiene detrás quien
# se lo instale: la mayoría solo tendrá un agente continuo». Se mira qué
# herramientas hay instaladas, por dónde se les habla, qué corre solo, si hay
# candados y sobre qué carpeta trabajan. Todo por presencia de ficheros o
# binarios; nunca se lee contenido privado ni se ejecuta nada de la persona.
ARNESES = [  # (nombre, binario, carpeta de config, fichero de memoria/instrucciones)
    ("Claude Code", "claude", CASA / ".claude", "CLAUDE.md"),
    ("Codex", "codex", CASA / ".codex", "AGENTS.md"),
    ("Gemini CLI", "gemini", CASA / ".gemini", "GEMINI.md"),
    ("Hermes", "hermes", CASA / ".hermes", "SOUL.md"),
    ("OpenClaw", "openclaw", CASA / ".openclaw", ""),
    ("Aider", "aider", CASA / ".aider", ""),
    ("Cursor", "cursor", CASA / ".cursor", ".cursorrules"),
]
NOTAS_TIPO = {
    "00": "Sistema", "01": "Index", "02": "MOCs", "03": "Proyectos", "04": "Knowledge", "05": "Diario", "06": "Raw", "99": "Archivo",
    "001": "Recursos externos", "010": "Visión", "011": "Proyectos", "020": "Proyectos", "050": "Activos", "200": "Conocimiento", "400": "Sabiduría", "900": "Tiempo"
}


def _hooks_en(settings: Path):
    """Cuántos candados (hooks) declara un settings.json de Claude Code. Solo cuenta; no lee comandos."""
    try:
        d = json.loads(settings.read_text(encoding="utf-8"))
        h = d.get("hooks") or {}
        return sum(len(v) if isinstance(v, list) else 1 for v in h.values())
    except Exception:  # noqa: BLE001
        return 0


def detectar_actores(raiz, skills, tareas, sistema, solo_carpeta=False):
    import shutil
    arneses = []
    for nombre, binario, conf, memoria in ARNESES:
        ruta_bin = None if solo_carpeta else shutil.which(binario)
        tiene_conf = (not solo_carpeta) and conf.exists()
        if not ruta_bin and not tiene_conf:
            continue
        mios = [x for x in skills if (x.get("herramienta") == nombre or nombre in x.get("herramientas", [])) and not x.get("ejemplo")]
        mem = [str(m.name) for m in ([conf / memoria, raiz / memoria] if memoria else []) if m.exists()]
        mem_pal = sum(len(m.read_text(encoding="utf-8", errors="ignore").split()) for m in ([conf / memoria, raiz / memoria] if memoria else []) if m.exists())
        arneses.append({"nombre": nombre, "binario": binario, "instalado": bool(ruta_bin), "config": tiene_conf,
                        "skills": sum(1 for x in mios if not x["es_agente"]), "agentes": sum(1 for x in mios if x["es_agente"]),
                        "memoria": mem, "memoria_palabras": mem_pal})
    # Canales: por dónde se le habla al agente además de la terminal.
    canales = []
    if not solo_carpeta and (CASA / ".claude" / "channels" / "telegram").exists():
        canales.append({"nombre": "Telegram", "via": "plugin de Claude Code"})
    if not solo_carpeta and ((CASA / ".hermes" / "gateway.pid").exists() or (CASA / ".hermes" / "platforms").exists()):
        canales.append({"nombre": "Gateway de Hermes", "via": "bots de Hermes (Telegram, Discord…)"})
    if (raiz / ".obsidian").exists():
        canales.append({"nombre": "Obsidian", "via": "el vault está abierto como bóveda de Obsidian"})
    # Candados: hooks de Claude Code (usuario y carpeta) y carpetas HOOKS del sistema.
    hooks = (0 if solo_carpeta else _hooks_en(CASA / ".claude" / "settings.json")) + _hooks_en(raiz / ".claude" / "settings.json") + _hooks_en(raiz / ".claude" / "settings.local.json")
    hooks_sh = len(list(raiz.glob("**/HOOKS/handlers/*.sh"))) if raiz.exists() else 0
    # MCP: servidores declarados en la carpeta (solo cuenta).
    mcp = 0
    for f in ((raiz / ".mcp.json",) if solo_carpeta else (raiz / ".mcp.json", CASA / ".claude.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8")); mcp += len((d.get("mcpServers") or {}))
        except Exception:  # noqa: BLE001
            pass
    # El suelo: ¿es un Cerebro Digital (carpetas numeradas por nota tipo)?
    notas, vistos = [], set()
    if raiz.exists():
        for d in sorted(raiz.iterdir()):
            if not d.is_dir():
                continue
            p2 = d.name[:2]
            p3 = d.name[:3]
            if p2 in NOTAS_TIPO and d.name[2:3] == " " and p2 not in vistos:
                vistos.add(p2); notas.append({"num": p2, "carpeta": d.name, "nombre": NOTAS_TIPO[p2]})
            elif p3 in NOTAS_TIPO and d.name[3:4] == " ":
                num = {"011": "020"}.get(p3, p3)
                if num not in vistos:
                    vistos.add(num); notas.append({"num": num, "carpeta": d.name, "nombre": NOTAS_TIPO[p3]})
    sistema_dirs = [d.name for d in raiz.iterdir() if d.is_dir() and (d.name.upper().startswith("000 NEXUS") or d.name.startswith("00 Sistema"))] if raiz.exists() else []
    # Lo que corre solo: por fuente, y si hay lanzador/vigilante entre ello.
    por_fuente = {}
    for t in tareas:
        por_fuente[t["fuente"]] = por_fuente.get(t["fuente"], 0) + 1
    lanzador = any(re.search(r"(?i)lanzador|launcher|dispatcher", t["que"]) for t in tareas) or any(raiz.glob("**/lanzador.py"))
    vigilante = sistema.get("vigilante") or any(re.search(r"(?i)vigilante|watchdog|arranque", t["que"]) for t in tareas)
    return {"arneses": arneses, "canales": canales, "hooks": hooks, "hooks_sh": hooks_sh, "mcp": mcp,
            "notas": notas, "sistema_dirs": sistema_dirs, "carpeta": raiz.name or str(raiz), "obsidian": (raiz / ".obsidian").exists(),
            "tareas_por_fuente": por_fuente, "lanzador": bool(lanzador), "vigilante": bool(vigilante),
            "tablero": bool(sistema.get("tablero")), "programadas": bool(sistema.get("programadas")),
            "flujos": bool(sistema.get("flujos")),
            "agentes": sum(1 for x in skills if x["es_agente"] and not x.get("ejemplo")),
            "skills": sum(1 for x in skills if not x["es_agente"] and not x.get("ejemplo"))}


def leer_kanban(raiz: Path) -> dict:
    kanban_dir = raiz / "03 Proyectos" / "Kanban"
    kanban = {"pendientes": [], "en_progreso": [], "en_revision": [], "hecho": [], "archivado": [], "total": 0}
    if not kanban_dir.exists():
        return kanban
    
    for col, key in [("Pendientes", "pendientes"), ("En_Progreso", "en_progreso"), ("En_Revision", "en_revision"), ("Hecho", "hecho"), ("Archivado", "archivado")]:
        d = kanban_dir / col
        if d.exists():
            for f in sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.name.lower() in ("index.md", "readme.md"):
                    continue
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                fm, cuerpo = frontmatter(txt)
                obj = ""
                m_obj = re.search(r"## 🎯 Objetivo\s*\n+([^\n#]+)", cuerpo)
                if m_obj:
                    obj = m_obj.group(1).strip().lstrip("- ")
                kanban[key].append({
                    "archivo": f.name,
                    "title": fm.get("title", f.stem),
                    "agent": fm.get("agent", "general"),
                    "skill": fm.get("skill", ""),
                    "pipeline": "pipeline" in fm or bool(re.search(r"\npipeline:\s*\n", txt)),
                    "prioridad": fm.get("prioridad", "🟡 Media"),
                    "estado": fm.get("estado", key),
                    "fecha_creacion": fm.get("fecha_creacion", ""),
                    "fecha_finalizacion": fm.get("fecha_finalizacion", ""),
                    "objetivo": obj[:180],
                    "cuerpo": cuerpo[:1500].strip()
                })
    kanban["total"] = sum(len(kanban[k]) for k in ("pendientes", "en_progreso", "en_revision", "hecho", "archivado"))
    return kanban


def leer_roadmap(raiz: Path) -> dict:
    roadmap_file = raiz / "01 Index" / "Roadmap del Sistema.md"
    res = {
        "stats": {"total": 0, "completados": 0, "en_curso": 0, "pendientes": 0, "progreso_pct": 0, "secciones": []},
        "items": []
    }
    if not roadmap_file.exists():
        return res
    try:
        txt = roadmap_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return res
    
    items = []
    in_table = False
    current_sec = "Pendientes de producto"
    for line in txt.splitlines():
        line_s = line.strip()
        if line_s.startswith("## ") or line_s.startswith("### "):
            sec_title = line_s.lstrip("#").strip()
            sec_clean = re.sub(r"^[^\w\s]+", "", sec_title).strip()
            if sec_clean:
                current_sec = sec_clean
        if line_s.startswith("| Pendiente |") or line_s.startswith("| Hallazgo |") or line_s.startswith("| # | Qué falta |") or line_s.startswith("| # | Pendiente |"):
            in_table = True
            continue
        if in_table:
            if not line_s.startswith("|"):
                in_table = False
                continue
            if re.match(r"^\|[\s-]+\|[\s-]+\|[\s-]+\|.*$", line_s):
                continue
            parts = [p.strip() for p in line_s.split("|")[1:-1]]
            if len(parts) >= 3:
                if parts[0].isdigit() or parts[0] == "—":
                    col1, col2, col3 = parts[1], parts[2], (parts[3] if len(parts) > 3 else "Baja")
                else:
                    col1, col2, col3 = parts[0], parts[1], parts[2]
                estado = "pendiente"
                if "✅" in col1 or "hecho" in col1.lower():
                    estado = "completado"
                elif "▶️" in col1:
                    estado = "en_curso"
                elif "⏸️" in col1 or "diferid" in col3.lower() or "bloquead" in col3.lower():
                    estado = "bloqueado"
                
                limpio_titulo = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", col1).strip()
                limpio_desc = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", col2).strip()
                
                items.append({
                    "nombre": col1,
                    "nombre_limpio": limpio_titulo,
                    "descripcion": limpio_desc[:260],
                    "prioridad": col3,
                    "estado": estado,
                    "seccion": current_sec
                })
    
    comp = sum(1 for x in items if x["estado"] == "completado")
    enc = sum(1 for x in items if x["estado"] == "en_curso")
    pend = sum(1 for x in items if x["estado"] in ("pendiente", "bloqueado"))
    pct = round((comp / len(items)) * 100) if items else 0
    secs = []
    for it in items:
        if it["seccion"] not in secs:
            secs.append(it["seccion"])
    res["stats"] = {
        "total": len(items),
        "completados": comp,
        "en_curso": enc,
        "pendientes": pend,
        "progreso_pct": pct,
        "secciones": secs
    }
    res["items"] = items
    return res


PLANTILLA = Path(__file__).resolve().with_name("mapa-agentes.plantilla.html")


def construir_html(datos):
    """Rellena la plantilla (HTML + CSS + JS, ~1600 líneas) con los datos.

    La plantilla vive en su propio archivo, al lado de este: así se edita como
    HTML (con resaltado y sin escapar nada) y este módulo queda con la lógica.
    Test de humo: tests/test_mapa_agentes.py.
    """
    j = json.dumps(datos, ensure_ascii=False)
    # read_text traduce los finales de linea: la plantilla da el mismo HTML en Windows y Linux.
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    return plantilla.replace("__DATOS__", j).replace("__ENLACE__", datos.get("enlace", "enlace pendiente"))


def leer_cuentas(raiz):
    """Los perfiles de Claude Code de esta máquina, vía panel-cuentas.py (su vecino
    en esta misma carpeta). Si no está o falla, el mapa sigue sin la pestaña: el
    dashboard nunca se cae por una pieza opcional."""
    try:
        import importlib.util
        ruta = Path(__file__).parent / "panel-cuentas.py"
        if not ruta.exists():
            return {}
        spec = importlib.util.spec_from_file_location("panel_cuentas", ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.recolectar(raiz) or {}
    except Exception:
        return {}


def recolectar_datos(raiz, sin_maquina=False, enlace=""):
    enc = {}
    for herramienta, raices in RAICES.items():
        rastrear(raices, herramienta, enc)
    rastrear([raiz], "carpeta propia", enc)

    # Consolidación Canónica Multi-Arnés
    canon = {}
    for s in enc.values():
        norm_name = re.sub(r'[^a-z0-9]+', '-', s["nombre"].lower()).strip('-')
        if norm_name not in canon:
            item = dict(s)
            item["herramientas"] = [s["herramienta"]]
            item["rutas"] = [s["ruta"]]
            item["copias_count"] = 1
            canon[norm_name] = item
        else:
            existente = canon[norm_name]
            existente["copias_count"] += 1
            if s["herramienta"] not in existente["herramientas"]:
                existente["herramientas"].append(s["herramienta"])
            if s["ruta"] not in existente["rutas"]:
                existente["rutas"].append(s["ruta"])
            # Preferencia: si una es local del vault, esa manda sobre una global de máquina
            if s.get("es_local") and not existente.get("es_local"):
                existente["ruta"] = s["ruta"]
                existente["es_local"] = True
                existente["herramienta"] = s["herramienta"]
                if s["descripcion"]:
                    existente["descripcion"] = s["descripcion"]
                existente["modificado"] = s["modificado"]
                existente["dias"] = s["dias"]
            elif s["modificado"] > existente["modificado"]:
                if not existente.get("es_local") or s.get("es_local"):
                    existente["modificado"] = s["modificado"]
                    existente["dias"] = s["dias"]
                    if s["descripcion"]:
                        existente["descripcion"] = s["descripcion"]

    skills_canonicas = sorted(canon.values(), key=lambda s: s["nombre"].lower())
    skills_todas = sorted(enc.values(), key=lambda s: s["nombre"].lower())

    skills = skills_canonicas
    aristas = relaciones(skills)
    avisos = semaforo(skills, aristas)
    tareas = [] if sin_maquina else cron_y_launchd() + rutinas_claude_nube(raiz) + rutinas_externas(raiz)
    dicen = programadas_en_texto(skills)
    sistema = detectar_sistema(raiz)
    flujos = leer_flujos_yml(raiz)
    sistema["flujos"] = bool(flujos)
    actores = detectar_actores(raiz, skills, tareas, sistema, solo_carpeta=sin_maquina)
    for s in skills:
        s["es"] = entradas_salidas(s)
    for s in skills_todas:
        s["es"] = entradas_salidas(s)
    inferidos = inferir_flujos(skills, aristas)
    for s in skills:
        s.pop("texto", None); s.pop("texto_orig", None)
    for s in skills_todas:
        s.pop("texto", None); s.pop("texto_orig", None)

    def _corta(r):
        for base, pre in ((str(raiz), ""), (str(CASA), "~")):
            if r.startswith(base + os.sep) or r == base:
                resto = r[len(base):].replace(os.sep, "/").lstrip("/")
                return (pre + "/" + resto) if pre else resto
        return r
    for s in skills:
        nueva = _corta(s["ruta"])
        if nueva != s["ruta"]:
            avisos[nueva] = avisos.pop(s["ruta"], [])
            s["ruta"] = nueva
        s["rutas"] = [_corta(x) for x in s.get("rutas", [])]
    for s in skills_todas:
        s["ruta"] = _corta(s["ruta"])
    datos = {
        "version": VERSION,
        "generado": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "skills": skills,
        "skills_todas": skills_todas,
        "stats_skills": {
            "canonicas": len(skills_canonicas),
            "todas": len(skills_todas)
        },
        "aristas": aristas,
        "avisos": avisos,
        "tareas": tareas,
        "dicen": dicen,
        "sistema": sistema,
        "flujos": flujos,
        "inferidos": inferidos,
        "actores": actores,
        "agentes_reales": leer_agentes(raiz),
        "pipelines_kanban": leer_pipelines_kanban(raiz),
        "ejemplos_cron": EJEMPLOS_CRON,
        "enlace": enlace,
        "kanban": leer_kanban(raiz),
        "roadmap": leer_roadmap(raiz),
        "cuentas": {} if sin_maquina else leer_cuentas(raiz)
    }
    return datos


class MissionControlHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _enviar_bytes(self, body: bytes, content_type: str = "application/json; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        chunk_size = 32768
        for i in range(0, len(body), chunk_size):
            self.wfile.write(body[i:i + chunk_size])
            self.wfile.flush()

    def _enviar_json(self, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._enviar_bytes(body, "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("", "/", "/index.html"):
            html_file = self.server.raiz / "Mapa de mis agentes.html"
            if html_file.exists():
                body = html_file.read_bytes()
            else:
                datos = recolectar_datos(self.server.raiz, sin_maquina=self.server.sin_maquina, enlace=self.server.enlace)
                html_content = construir_html(datos)
                body = html_content.encode("utf-8")
                html_file.write_bytes(body)
            self._enviar_bytes(body, "text/html; charset=utf-8")
        elif path == "/api/status":
            datos = recolectar_datos(self.server.raiz, sin_maquina=self.server.sin_maquina)
            skills_lst = datos.get("skills_canonicas") or datos.get("skills") or []
            agentes_lst = datos.get("agentes_reales") or datos.get("agentes") or []
            roadmap_data = datos.get("roadmap") or {}
            secciones_lst = roadmap_data.get("secciones") or (roadmap_data.get("stats") or {}).get("secciones") or []
            kb_data = datos.get("kanban") or {}
            kb_tot = sum(len(kb_data.get(k, [])) for k in ("pendientes", "en_progreso", "en_revision", "hecho"))
            res = {
                "ok": True,
                "version": datos["version"],
                "generado": datos["generado"],
                "skills_count": len(skills_lst),
                "agentes_count": len(agentes_lst),
                "secciones_count": len(secciones_lst),
                "kanban_count": kb_tot,
                "kanban": datos["kanban"],
                "roadmap": datos["roadmap"]
            }
            self._enviar_json(res)
        elif path == "/api/kanban":
            kb = leer_kanban(self.server.raiz)
            self._enviar_json(kb)
        else:
            self.send_error(404, "Ruta no encontrada")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        try:
            req_data = json.loads(raw_body) if raw_body else {}
        except Exception:
            req_data = {}

        if path == "/api/kanban/dispatch":
            scripts_dir = self.server.raiz / ".claude" / "scripts"
            card_target = req_data.get("card", "").strip()
            if card_target:
                cmd = [sys.executable, str(scripts_dir / "despachador-kanban.py"), "--card", card_target]
            else:
                cmd = [sys.executable, str(scripts_dir / "despachador-kanban.py"), "--dispatch-next"]
            try:
                proc = subprocess.run(cmd, cwd=self.server.raiz, capture_output=True, text=True, encoding="utf-8")
                res = {
                    "ok": proc.returncode == 0,
                    "output": proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip() or proc.stdout.strip(),
                    "kanban": leer_kanban(self.server.raiz)
                }
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            self._enviar_json(res)

        elif path == "/api/kanban/create":
            title = req_data.get("title", "").strip()
            if not title:
                self.send_error(400, "El título es obligatorio")
                return
            agent = req_data.get("agent", "general").strip()
            skill = req_data.get("skill", "manual").strip()
            prioridad = req_data.get("prioridad", "🟡 Media").strip()
            objetivo = req_data.get("objetivo", "").strip()
            
            today = dt.datetime.now().strftime("%Y-%m-%d")
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:50]
            filename = f"{today} - {slug}.md"
            target_path = self.server.raiz / "03 Proyectos" / "Kanban" / "Pendientes" / filename
            
            # El dueño sale del archivo de identidad (gitignorado); sin él, un nombre neutro.
            ident = self.server.raiz / "owner.env"
            m = re.search(r'^OWNER="?([^"\n]*)', ident.read_text(encoding="utf-8"), re.M) if ident.exists() else None
            dueno = m.group(1).strip() if m else "dueño del vault"
            card_content = f"""---
type: Project
title: "{title}"
tags: [kanban, tarea]
estado: 📥 Pendiente
prioridad: {prioridad}
responsable: "{dueno}"
agent: {agent}
skill: {skill}
fecha_creacion: {today}
id: "KB-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"
---

# {title}

## 🎯 Objetivo
{objetivo or title}

## ⚡ Contexto y Requisitos
- Generada desde Mission Control web.
- Agente asignado: `{agent}`.
- Skill requerida: `{skill}`.
"""
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(card_content, encoding="utf-8")
            
            res = {
                "ok": True,
                "file": filename,
                "archivo": filename,
                "kanban": leer_kanban(self.server.raiz)
            }
            self._enviar_json(res)

        elif path == "/api/refresh":
            datos = recolectar_datos(self.server.raiz, sin_maquina=self.server.sin_maquina, enlace=self.server.enlace)
            salida = self.server.raiz / "Mapa de mis agentes.html"
            salida.write_text(construir_html(datos), encoding="utf-8")
            skills_lst = datos.get("skills_canonicas") or datos.get("skills") or []
            agentes_lst = datos.get("agentes_reales") or datos.get("agentes") or []
            res = {
                "ok": True,
                "skills_count": len(skills_lst),
                "agentes_count": len(agentes_lst),
                "kanban": datos["kanban"],
                "roadmap": datos["roadmap"]
            }
            self._enviar_json(res)

        elif path == "/api/kanban/move":
            card_name = (req_data.get("card") or req_data.get("card_name") or "").strip()
            to_col = (req_data.get("to_col") or req_data.get("target_col") or "").strip().lower()
            if not card_name or not to_col:
                self.send_error(400, "Faltan parámetros: card/card_name o to_col")
                return

            col_map = {
                "pendientes": "Pendientes",
                "en_progreso": "En_Progreso",
                "en_revision": "En_Revision",
                "hecho": "Hecho",
                "archivado": "Archivado"
            }
            if to_col not in col_map:
                self.send_error(400, f"Columna destino inválida: {to_col}")
                return

            dest_folder = self.server.raiz / "03 Proyectos" / "Kanban" / col_map[to_col]
            dest_folder.mkdir(parents=True, exist_ok=True)

            found_card = None
            for folder_name in col_map.values():
                candidate = self.server.raiz / "03 Proyectos" / "Kanban" / folder_name / card_name
                if candidate.exists():
                    found_card = candidate
                    break

            if not found_card:
                self.send_error(404, f"Tarjeta {card_name} no encontrada")
                return

            try:
                content = found_card.read_text(encoding="utf-8")
                estado_str = {
                    "pendientes": "📥 Pendiente",
                    "en_progreso": "⚙️ En Progreso",
                    "en_revision": "👀 En Revisión",
                    "hecho": "✅ Hecho",
                    "archivado": "📦 Archivado"
                }.get(to_col, to_col)

                if re.search(r"(?m)^estado:\s*.*$", content):
                    content = re.sub(r"(?m)^estado:\s*.*$", f"estado: {estado_str}", content)
                else:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = f"---{parts[1]}estado: {estado_str}\n---{parts[2]}"

                if to_col == "hecho":
                    today = dt.datetime.now().strftime("%Y-%m-%d")
                    if re.search(r"(?m)^fecha_finalizacion:\s*.*$", content):
                        content = re.sub(r"(?m)^fecha_finalizacion:\s*.*$", f"fecha_finalizacion: {today}", content)
                    else:
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            content = f"---{parts[1]}fecha_finalizacion: {today}\n---{parts[2]}"

                target_dest = dest_folder / card_name
                if target_dest != found_card:
                    target_dest.write_text(content, encoding="utf-8")
                    found_card.unlink()
                else:
                    found_card.write_text(content, encoding="utf-8")

                res = {"ok": True, "kanban": leer_kanban(self.server.raiz)}
            except Exception as e:
                res = {"ok": False, "error": str(e)}
            self._enviar_json(res)

        else:
            self.send_error(404, "Endpoint no encontrado")

    def log_message(self, format, *args):
        sys.stderr.write(f"[MissionControl] {self.address_string()} - {format % args}\n")


def iniciar_servidor(raiz, puerto=8765, sin_maquina=False, enlace="", abrir_navegador=True):
    class CustomServer(http.server.ThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            self.raiz = raiz
            self.sin_maquina = sin_maquina
            self.enlace = enlace
            super().__init__(*args, **kwargs)

    try:
        servidor = CustomServer(("127.0.0.1", puerto), MissionControlHandler)
    except OSError as e:
        print(f"❌ Error al iniciar servidor en puerto {puerto}: {e}")
        return

    url = f"http://127.0.0.1:{puerto}/"
    print("\n🛸 Mission Control de Sistema Maestro activo:")
    print(f"   ▶ URL: {url}")
    print("   ▶ Acciones en vivo: Despacho de tareas, creación y recarga en tiempo real.")
    print("   ▶ Presiona Ctrl+C para detener el servidor.\n")
    if abrir_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo Mission Control...")
        servidor.server_close()
        print("✓ Servidor cerrado.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=None, help="carpeta que rastrear (por defecto, la carpeta desde la que se ejecuta)")
    ap.add_argument("--salida", default=None); ap.add_argument("--json", action="store_true")
    ap.add_argument("--sin-maquina", action="store_true", help="no mirar la máquina (cron, launchd, arneses, hooks del usuario): solo la carpeta. Para generar la muestra que se distribuye")
    ap.add_argument("--enlace", default="", help="enlace opcional")
    ap.add_argument("--serve", action="store_true", help="iniciar servidor interactivo de Mission Control en localhost")
    ap.add_argument("--puerto", type=int, default=8765, help="puerto para el servidor web (por defecto: 8765)")
    ap.add_argument("--no-browser", action="store_true", help="no abrir el navegador automáticamente al iniciar el servidor")
    a = ap.parse_args()

    raiz = Path(a.raiz).expanduser() if a.raiz else Path.cwd()
    datos = recolectar_datos(raiz, sin_maquina=a.sin_maquina, enlace=a.enlace)

    salida = Path(a.salida) if a.salida else raiz / "Mapa de mis agentes.html"
    salida.write_text(construir_html(datos), encoding="utf-8")
    if a.json:
        salida.with_suffix(".json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    kb_tot = datos["kanban"]["total"]
    rm_tot = datos["roadmap"]["stats"]["total"]
    rm_pct = datos["roadmap"]["stats"]["progreso_pct"]
    print(f"✓ {salida}  ·  {len(datos['skills'])} skills/agentes · {len(datos['aristas'])} llamadas · {len(datos['tareas'])} programadas · {kb_tot} tareas Kanban · Roadmap al {rm_pct}% ({rm_tot} hitos)")
    print("  Ábrelo con doble clic (o arrástralo al navegador). No se ha enviado nada a ningún sitio.")

    if a.serve:
        iniciar_servidor(raiz, puerto=a.puerto, sin_maquina=a.sin_maquina, enlace=a.enlace, abrir_navegador=not a.no_browser)


if __name__ == "__main__":
    main()
