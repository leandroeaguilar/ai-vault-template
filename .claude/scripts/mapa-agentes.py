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
import html
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
            $tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match '(?i)SistemaMaestro|Claude|Agent' }
            $list = @()
            foreach ($t in $tasks) {
                if ($t.TaskName -match '(?i)SpacePort|Mozilla|ASUS|Edge') { continue }
                $tr = $t.Triggers[0]
                $action = $t.Actions[0]
                $execStr = if ($action) { "$($action.Execute) $($action.Arguments)" } else { "" }
                $list += [PSCustomObject]@{
                    Name = $t.TaskName
                    State = [string]$t.State
                    Start = $tr.StartBoundary
                    Interval = $tr.Repetition.Interval
                    DaysOfWeek = [string]$tr.DaysOfWeek
                    Trigger = $tr.CimClass.CimClassName
                    Exec = $execStr
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
                            "estado": item.get("State", "Ready")
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
    for ln in lineas:
        low = ln.lower()
        lee = re.search(V_LEE, low); esc = re.search(V_ESC, low)
        rutas = [r for r in (_limpia(m.group(0)) for m in RE_RUTA.finditer(ln)) if r]
        for r in rutas:
            if esc and (not lee or esc.start() < lee.start()):
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
                                steps.append(f"{k.strip()}: {v.strip().strip('\"\'')}")
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
    kanban = {"pendientes": [], "en_progreso": [], "hecho": [], "archivado": [], "total": 0}
    if not kanban_dir.exists():
        return kanban
    
    for col, key in [("Pendientes", "pendientes"), ("En_Progreso", "en_progreso"), ("Hecho", "hecho"), ("Archivado", "archivado")]:
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
    kanban["total"] = len(kanban["pendientes"]) + len(kanban["en_progreso"]) + len(kanban["hecho"]) + len(kanban["archivado"])
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


def construir_html(datos):
    j = json.dumps(datos, ensure_ascii=False)
    return r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sistema Maestro — Mapa de mis agentes</title>
<style>
:root {
  --fondo: #f8fafc;
  --tarjeta: #ffffff;
  --tarjeta-subtle: #f1f5f9;
  --tarjeta-hover: #e2e8f0;
  --tinta: #0f172a;
  --gris: #64748b;
  --gris-claro: #94a3b8;
  --linea: #e2e8f0;
  --linea-suave: #f1f5f9;
  --hueco: #cbd5e1;
  --acento: #4f46e5;
  --acento-glow: rgba(79, 70, 229, 0.12);
  --ok: #059669;
  --aviso: #d97706;
  --mal: #e11d48;
  --sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, Menlo, Consolas, "SF Mono", monospace;
  --sombra-sm: 0 1px 3px rgba(0, 0, 0, 0.04), 0 0 0 1px var(--linea);
  --sombra-md: 0 4px 16px rgba(0, 0, 0, 0.06), 0 0 0 1px var(--linea);
  --radio-card: 10px;
  --radio-pill: 999px;
  --c001: #C0392B; --c010: #B8860B; --c020: #27AE60; --c050: #E67E22;
  --c200: #34495E; --c400: #A03758; --c900: #2C3E50; --c000: #5A6673;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --fondo: #090a0f;
    --tarjeta: #13151f;
    --tarjeta-subtle: #191c28;
    --tarjeta-hover: #1e2235;
    --tinta: #f1f5f9;
    --gris: #94a3b8;
    --gris-claro: #64748b;
    --linea: #202434;
    --linea-suave: #181b29;
    --hueco: #1e2337;
    --acento: #6366f1;
    --acento-glow: rgba(99, 102, 241, 0.16);
    --ok: #10b981;
    --aviso: #f59e0b;
    --mal: #f43f5e;
    --sombra-sm: 0 1px 3px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--linea);
    --sombra-md: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--linea);
    --c001: #E8725F; --c010: #D9AC4A; --c020: #5FD08D; --c050: #F0A055;
    --c200: #7C9BBD; --c400: #D1738F; --c900: #FFFFFF; --c000: #97A3B0;
  }
}
:root[data-theme="dark"] {
  --fondo: #090a0f;
  --tarjeta: #13151f;
  --tarjeta-subtle: #191c28;
  --tarjeta-hover: #1e2235;
  --tinta: #f1f5f9;
  --gris: #94a3b8;
  --gris-claro: #64748b;
  --linea: #202434;
  --linea-suave: #181b29;
  --hueco: #1e2337;
  --acento: #6366f1;
  --acento-glow: rgba(99, 102, 241, 0.16);
  --ok: #10b981;
  --aviso: #f59e0b;
  --mal: #f43f5e;
  --sombra-sm: 0 1px 3px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--linea);
  --sombra-md: 0 4px 20px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--linea);
  --c001: #E8725F; --c010: #D9AC4A; --c020: #5FD08D; --c050: #F0A055;
  --c200: #7C9BBD; --c400: #D1738F; --c900: #FFFFFF; --c000: #97A3B0;
}
.t001,.t06{--c:var(--c001);--cs:#F7E2DF}.t010,.t01{--c:var(--c010);--cs:#F5EBCF}.t020,.t03{--c:var(--c020);--cs:#DFF1E6}.t050,.t02{--c:var(--c050);--cs:#FBE7D3}.t200,.t04{--c:var(--c200);--cs:#DFE4EA}.t400,.t99{--c:var(--c400);--cs:#F6E0E8}.t900,.t05{--c:var(--c900);--cs:#FFFFFF}.t000,.t00{--c:var(--c000);--cs:#E4E7E5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .t001,:root:not([data-theme="light"]) .t010,:root:not([data-theme="light"]) .t020,:root:not([data-theme="light"]) .t050,:root:not([data-theme="light"]) .t200,:root:not([data-theme="light"]) .t400,:root:not([data-theme="light"]) .t000,:root:not([data-theme="light"]) .t00,:root:not([data-theme="light"]) .t01,:root:not([data-theme="light"]) .t02,:root:not([data-theme="light"]) .t03,:root:not([data-theme="light"]) .t04,:root:not([data-theme="light"]) .t06,:root:not([data-theme="light"]) .t99{--cs:color-mix(in srgb,var(--c) 20%,var(--fondo))} :root:not([data-theme="light"]) .t900,:root:not([data-theme="light"]) .t05{--cs:var(--tarjeta)}}
:root[data-theme="dark"] .t001,:root[data-theme="dark"] .t010,:root[data-theme="dark"] .t020,:root[data-theme="dark"] .t050,:root[data-theme="dark"] .t200,:root[data-theme="dark"] .t400,:root[data-theme="dark"] .t000,:root[data-theme="dark"] .t00,:root[data-theme="dark"] .t01,:root[data-theme="dark"] .t02,:root[data-theme="dark"] .t03,:root[data-theme="dark"] .t04,:root[data-theme="dark"] .t06,:root[data-theme="dark"] .t99{--cs:color-mix(in srgb,var(--c) 20%,var(--fondo))}:root[data-theme="dark"] .t900,:root[data-theme="dark"] .t05{--cs:var(--tarjeta)}
*{box-sizing:border-box}
::selection{background:color-mix(in srgb,var(--acento) 25%,transparent);color:inherit}
:focus-visible{outline:2px solid var(--acento);outline-offset:2px}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--linea);border-radius:999px}
::-webkit-scrollbar-thumb:hover{background:var(--gris-claro)}
body{margin:0;background:var(--fondo);color:var(--tinta);font:14px/1.55 var(--sans);padding-block:24px;padding-inline:clamp(16px,4vw,44px);-webkit-font-smoothing:antialiased;letter-spacing:-0.01em}
h1{font-size:1.45rem;font-weight:700;letter-spacing:-0.025em;margin:0;line-height:1.2}
h2{font-size:1.1rem;font-weight:600;letter-spacing:-0.02em;margin:22px 0 10px}
.sub{color:var(--gris);margin:0 0 16px;font-size:.88rem;max-width:76ch;line-height:1.5}
.topline{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px 20px;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--linea)}
.brand{display:flex;flex-direction:column;gap:4px}
.brand-title{display:flex;align-items:center;gap:10px}
.brand-sub{margin:0;color:var(--gris);font-size:.8rem}
.version-badge{display:inline-flex;align-items:center;gap:6px;font:500 .72rem/1 var(--mono);color:var(--gris);padding:4px 9px;background:var(--tarjeta-subtle);border:1px solid var(--linea);border-radius:999px}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse-live 2.5s infinite ease-in-out;flex:none}
@keyframes pulse-live{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.85)}}
#tema{width:34px;height:34px;border-radius:8px;border:1px solid var(--linea);background:var(--tarjeta);font-size:1rem;line-height:1;color:var(--tinta);cursor:pointer;flex:none;transition:all .15s ease;display:flex;align-items:center;justify-content:center}
#tema:hover{border-color:var(--acento);background:var(--tarjeta-subtle)}
.controles{display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap}
.sw-wrap{display:flex;align-items:center;gap:8px}
.sw-et{font:.68rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--gris)}
.sw-wrap button{position:relative;width:42px;height:24px;flex:none;border-radius:999px;border:1px solid var(--linea);background:var(--tarjeta-subtle);transition:all .15s ease;cursor:pointer}
.sw-wrap button::after{content:"";position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:var(--gris);transition:transform .15s ease,background .15s ease}
.sw-wrap button[aria-checked="true"]{background:var(--acento);border-color:var(--acento)}
.sw-wrap button[aria-checked="true"]::after{transform:translateX(18px);background:#fff}
.aviso-priv{margin:0 0 16px;padding:10px 14px;border-radius:8px;font-size:.85rem;background:color-mix(in srgb,var(--acento) 10%,var(--tarjeta));border:1px solid color-mix(in srgb,var(--acento) 30%,transparent);color:var(--tinta)}
/* Modo privacidad */
body.privado [data-priv="1"]{display:none!important}
body.privado .n.ruta,body.privado .cal .n,body.privado #plano .dato li,body.privado .cal-caja li .n{filter:blur(6px)}
.pestanas{display:flex;flex-wrap:wrap;gap:4px;padding:4px;background:var(--tarjeta);border:1px solid var(--linea);border-radius:10px;margin:16px 0 22px;box-shadow:var(--sombra-sm)}
.pestanas button{border:0;background:transparent;color:var(--gris);font:600 .82rem var(--sans);padding:7px 14px;border-radius:7px;cursor:pointer;transition:all .15s ease;letter-spacing:-0.01em}
.pestanas button:hover{color:var(--tinta);background:var(--tarjeta-subtle)}
.pestanas button[aria-selected=true]{color:var(--tinta);background:var(--tarjeta-hover);box-shadow:0 1px 3px rgba(0,0,0,0.1),0 0 0 1px var(--linea);font-weight:600}
.cifras{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:0 0 18px}
.cifra{background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:12px 14px;box-shadow:var(--sombra-sm);transition:all .15s cubic-bezier(0.16,1,0.3,1)}
.cifra:hover{border-color:color-mix(in srgb,var(--acento) 40%,var(--linea));box-shadow:var(--sombra-md);transform:translateY(-1px)}
.cifra b{display:block;font-size:1.55rem;font-weight:700;letter-spacing:-0.03em;line-height:1.1;font-variant-numeric:tabular-nums;color:var(--tinta)}
.cifra span{color:var(--gris);font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-top:4px;display:block}
.buscador{display:flex;align-items:center;gap:10px;height:40px;padding:0 12px;border:1px solid var(--linea);border-radius:8px;background:var(--tarjeta);margin:0 0 14px;box-shadow:var(--sombra-sm);transition:all .15s ease}
.buscador:focus-within{border-color:var(--acento);box-shadow:0 0 0 3px var(--acento-glow),var(--sombra-sm)}
.buscador input{flex:1;border:0;background:transparent;font:.88rem var(--sans);color:var(--tinta);outline:none}
.buscador input::placeholder{color:var(--gris-claro)}
table{width:100%;border-collapse:separate;border-spacing:0;background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);overflow:hidden;box-shadow:var(--sombra-sm)}
th,td{text-align:left;padding:9px 12px;border-top:1px solid var(--linea);vertical-align:top;font-size:.84rem}
th{color:var(--gris);font-size:.7rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;border-top:0;background:var(--tarjeta-subtle)}
tr:hover td{background:color-mix(in srgb,var(--tarjeta-hover) 35%,transparent)}
.tabla{overflow-x:auto}
.n{font-family:var(--mono);font-size:.82rem}
.d{color:var(--gris)}
.sk-filtros{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 14px}
.sk-f{border:1px solid var(--linea);background:var(--tarjeta);color:var(--tinta);border-radius:var(--radio-pill);padding:5px 12px;font:500 .78rem var(--sans);cursor:pointer;transition:all .15s ease;display:inline-flex;align-items:center;gap:6px}
.sk-f:hover{border-color:var(--gris);background:var(--tarjeta-subtle)}
.sk-f[aria-pressed=true]{background:var(--tinta);color:var(--fondo);border-color:var(--tinta);font-weight:600}
.sk-f span{color:var(--gris);font-family:var(--mono);font-size:.72rem;font-variant-numeric:tabular-nums}
.sk-f[aria-pressed=true] span{color:inherit;opacity:.85}
.sk-sep{width:1px;height:18px;background:var(--linea);margin:0 4px}
.sem{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.sem.gris{background:var(--hueco)}.sem.ok{background:var(--ok)}.sem.aviso{background:var(--aviso)}.sem.mal{background:var(--mal)}
.av{font-size:.82rem;color:var(--gris);margin:0;padding-left:14px}.av li{margin:0}
.grafo{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
.nodo{background:var(--tarjeta);border:1px solid var(--linea);border-radius:10px;padding:12px 14px;box-shadow:var(--sombra-sm)}
.nodo b{display:block;font-size:.9rem}
.nodo .sale,.nodo .entra{font-size:.82rem;margin-top:6px}
.nodo .sale::before{content:"→ llama a: ";color:var(--gris)}
.nodo .entra::before{content:"← la llaman: ";color:var(--gris)}
.huerfana{border-style:dashed;color:var(--gris)}
.rel{display:grid;grid-template-columns:minmax(150px,1fr) 28px minmax(220px,1.4fr) 28px minmax(150px,1fr);align-items:center;gap:6px 0;background:var(--tarjeta);border:1px solid var(--linea);border-radius:12px;padding:14px 16px;margin-bottom:12px;box-shadow:var(--sombra-sm)}
.rel.huerfana{border-style:dashed;opacity:.8}
.rel .lado{display:flex;flex-direction:column;gap:6px}
.rel .lado.izq{align-items:flex-end}
.rel .lado.der{align-items:flex-start}
.chip{display:inline-block;font:.78rem var(--mono);padding:4px 9px;border-radius:6px;border:1px solid var(--linea);background:var(--fondo);color:var(--tinta);max-width:100%;white-space:normal;text-align:left;line-height:1.3}
.chip.nadie{border-style:dashed;color:var(--gris)}
.chip.cu-ok{color:var(--ok);border-color:currentColor}
.chip.cu-mal{color:var(--mal);border-color:currentColor}
.chip.cu-av{color:var(--aviso);border-color:currentColor}.chip.mencion{border-style:dotted;color:var(--gris);opacity:.75}
.chip.decl{border-color:var(--ok);background:color-mix(in srgb,var(--ok) 8%,var(--tarjeta))}.chip.inf{border-color:var(--aviso);border-style:dashed;background:color-mix(in srgb,var(--aviso) 8%,var(--tarjeta))}.chip.sup{border-style:dotted;color:var(--gris)}
.rel .lado .chip{max-width:100%}
.rel.opaca .centro{border-style:dashed;border-color:var(--gris);background:transparent}
.rel .usa{grid-column:1/-1;font-size:.78rem;color:var(--gris);margin-top:6px}.rel .usa b{color:var(--tinta)}
.rel .herr{font-size:.72rem;color:var(--gris)}
.rel .centro{border:1.5px solid var(--acento);border-radius:10px;padding:10px 14px;background:color-mix(in srgb,var(--acento) 8%,var(--tarjeta))}
.rel .centro b{display:block;font:700 .95rem var(--mono)}.rel .centro span{display:block;font-size:.82rem;color:var(--gris);margin-top:3px}
.rel .centro .cnt{font:.7rem var(--mono);color:var(--acento);margin-top:6px;display:block}
.rel .conector{height:2px;background:var(--linea);position:relative}
.rel .conector::after{content:"";position:absolute;right:-1px;top:50%;transform:translateY(-50%);border-left:8px solid var(--linea);border-top:5px solid transparent;border-bottom:5px solid transparent}
.rel .conector.on{background:var(--acento)}.rel .conector.on::after{border-left-color:var(--acento)}
.rel .etq{font:.66rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--gris);margin-bottom:2px}
@media (max-width:760px){.rel{grid-template-columns:1fr}.rel .conector{display:none}.rel .lado.izq,.rel .lado.der{align-items:flex-start}}
.cal{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.cal-resumen{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:4px 0 18px}
.cal-caja{border:1px solid var(--linea);border-radius:10px;padding:10px 12px;background:var(--tarjeta);min-width:0;box-shadow:var(--sombra-sm)}
.cal-caja h4{margin:0 0 6px;font:700 .66rem var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--gris)}
.cal-caja h4 b{font:700 .92rem inherit;letter-spacing:0;margin-right:6px;color:var(--tinta)}
.cal-caja ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
.cal-caja li{font:.76rem/1.35 var(--mono);color:var(--tinta);display:flex;gap:8px;align-items:baseline;min-width:0}
.cal-caja li .h{flex:none;font-variant-numeric:tabular-nums;color:var(--gris);min-width:5ch}
.cal-caja li .n{overflow-wrap:anywhere}
.cal-caja li .q{color:var(--gris);font-size:.68rem}
.cal-caja li.parada{opacity:.5;text-decoration:line-through}
.cal-caja li.virtual{opacity:.6;font-style:italic}
.cal-caja .nada{color:var(--gris);font-size:.76rem;font-style:italic}
@media (max-width:760px){.cal-resumen{grid-template-columns:1fr}}
.cal-cabecera{display:flex;align-items:center;gap:10px;margin:4px 0 8px}
.cal-mes{font:600 1.1rem var(--mono);margin:0;min-width:180px;text-transform:capitalize}
.cal-nav,.cal-hoy{font:600 .85rem var(--mono);border:1px solid var(--linea);background:var(--tarjeta);color:var(--tinta);border-radius:6px;padding:4px 10px;cursor:pointer;transition:all .15s ease}
.cal-nav:hover,.cal-hoy:hover{border-color:var(--acento)}
.cal-hoy{font-size:.76rem;margin-left:auto}
.cal-semana{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-top:10px}
.cal-semana span{font:600 .68rem var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--gris);padding:0 6px}
.cal-rejilla{display:grid;grid-template-columns:repeat(7,1fr);gap:6px;margin-top:4px}
.cal-dia{min-height:92px;border:1px solid var(--linea);border-radius:8px;padding:6px 6px 8px;background:var(--tarjeta);box-shadow:var(--sombra-sm)}
.cal-dia.fuera{opacity:.35}
.cal-dia.hoy{border-color:var(--acento);border-width:1.5px;box-shadow:0 0 0 1px var(--acento)}
.cal-dia .num{font:.76rem var(--mono);color:var(--gris);font-variant-numeric:tabular-nums}
.cal-dia.hoy .num{color:var(--acento);font-weight:700}
.cal-puntos{display:flex;flex-direction:column;gap:3px}
.arranque{display:inline-flex;align-items:center;gap:5px;line-height:1}
.arranque .hora{font:.64rem var(--mono);color:var(--gris);font-variant-numeric:tabular-nums}
.punto{width:12px;height:12px;border-radius:50%;border:2px solid var(--c);background:var(--c);cursor:pointer;position:relative;flex:0 0 auto;transition:transform .12s ease}
.punto:hover,.punto:focus-visible{transform:scale(1.35);outline:none;box-shadow:0 0 0 3px color-mix(in srgb,var(--c) 30%,transparent)}
.punto.virtual{background:transparent;border-style:dashed}
.punto.declarada{background:transparent}
.cal-leyenda{display:flex;flex-wrap:wrap;gap:8px 18px;margin:12px 0 4px;font-size:.82rem;color:var(--gris)}
.cal-leyenda i{display:inline-block;vertical-align:middle;margin-right:6px}
.ej{display:inline-block;font:700 .58rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#fff;background:var(--aviso);border-radius:999px;padding:2px 8px;vertical-align:middle;white-space:nowrap}
.rel .centro .ej,.flujo h4 .ej,.n .ej{display:inline-block;width:auto;font:700 .58rem var(--mono);color:#fff;margin:0 0 0 6px}
.aviso-ejemplo{margin:0 0 16px;padding:10px 14px;border:1px dashed var(--aviso);border-radius:8px;background:color-mix(in srgb,var(--aviso) 8%,var(--tarjeta));font-size:.85rem}
.aviso-ejemplo b{color:var(--aviso)}
.cal-caja li .ej{margin-left:4px}
.aviso-virtual{margin:10px 0 0;padding:10px 14px;border:1px dashed var(--hueco);border-radius:8px;color:var(--gris);font-size:.85rem}
#globo{position:fixed;z-index:60;max-width:min(50ch,84vw);background:var(--tinta);color:var(--fondo);border-radius:8px;padding:8px 12px;font:.76rem/1.45 var(--sans);box-shadow:0 8px 24px rgba(0,0,0,0.3);pointer-events:none;opacity:0;visibility:hidden;transition:opacity .1s ease;white-space:pre-line}
#globo.visible{opacity:1;visibility:visible}
#globo b{font-weight:700}
#globo::after{content:"";position:absolute;top:100%;left:var(--flecha,50%);transform:translateX(-50%);border:6px solid transparent;border-top-color:var(--tinta)}
#globo.abajo::after{top:auto;bottom:100%;border-top-color:transparent;border-bottom-color:var(--tinta)}
@media (max-width:560px){.arranque .hora{font-size:.56rem}.cal-dia{min-height:60px}}
.hueco{border:1px dashed var(--linea);border-radius:10px;padding:16px;color:var(--gris);background:var(--tarjeta);min-height:110px}
.hueco b{display:block;color:var(--tinta);margin-bottom:6px}.hueco.lleno{border-style:solid;border-color:var(--ok)}
.flujos{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:16px}
.lista-flujos{display:flex;flex-direction:column;gap:12px}
.flujo{background:var(--tarjeta);border:1px solid var(--linea);border-left:4px solid var(--acento);border-radius:8px;padding:14px 16px 12px;box-shadow:var(--sombra-sm);transition:all .15s ease}
.flujo:hover{box-shadow:var(--sombra-md);transform:translateY(-1px)}
.flujo h4{margin:0 0 4px;font-size:1rem;font-weight:600}
.flujo .desc{margin:0 0 10px;color:var(--gris);font-size:.85rem;max-width:72ch}
.flujo .meta{display:flex;flex-wrap:wrap;gap:6px 14px;font:.74rem var(--mono);color:var(--gris);margin-bottom:10px}
.flujo .meta .ok{color:var(--ok)}.flujo .meta .est-av{color:var(--aviso)}
.cadena{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px}
.paso{border:1px solid var(--linea);border-radius:8px;padding:8px 12px;min-width:140px;max-width:260px;background:var(--fondo)}
.paso b{display:block;font-family:var(--mono);font-size:.82rem}.paso span{display:block;font-size:.75rem;color:var(--gris);margin-top:2px}
.paso.dir{border-color:var(--acento);border-style:solid}.paso.falta{border-style:dashed;color:var(--gris)}
.fl{align-self:center;color:var(--gris);font-size:1.1rem}
.destinos{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 14px}
.destinos .etq{font-size:.82rem;color:var(--gris);margin-right:4px}
.destinos button{border:1px solid var(--linea);background:var(--tarjeta);color:var(--tinta);border-radius:var(--radio-pill);padding:5px 12px;font:.82rem var(--sans);cursor:pointer;transition:all .15s ease}
.destinos button[aria-pressed=true]{background:var(--tinta);color:var(--fondo);border-color:var(--tinta)}.destinos button span{opacity:.6;margin-left:6px;font-size:.74rem}
.destinos button.terr{border:1px solid var(--c);background:var(--cs);color:var(--c);font-weight:600}.destinos button.terr span{opacity:.75}
.destinos button.terr[aria-pressed=true]{background:var(--c);color:var(--fondo);border-color:var(--c);box-shadow:0 0 0 2px color-mix(in srgb,var(--c) 26%,transparent)}.destinos button.terr.t900[aria-pressed=true]{color:var(--tinta)}
.cifras-fl{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 18px}.cifras-fl .etq{font-size:.82rem;color:var(--gris)}
.cifra-fl{background:var(--tarjeta);border:1px solid var(--linea);border-radius:8px;padding:6px 12px;font:.85rem var(--sans);color:var(--tinta);cursor:pointer;text-align:left;transition:all .15s ease}
.cifra-fl b{font-size:1.15rem;margin-right:6px;font-variant-numeric:tabular-nums}
.cifra-fl:hover{border-color:var(--acento)}.cifra-fl[aria-pressed=true]{border-color:var(--acento);background:color-mix(in srgb,var(--acento) 12%,var(--tarjeta))}.cifra-fl[aria-pressed=true] b{color:var(--acento)}.cifra-fl.total{border-style:dashed}
.fig{border:1px solid var(--linea);border-radius:12px;background:var(--tarjeta);padding:16px;margin:14px 0 20px;box-shadow:var(--sombra-sm)}
.fig .fig-cab{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;margin-bottom:12px}
.fig .fig-cab h3{margin:0;font-size:1.05rem}.fig .fig-cab .cuando{font:.74rem var(--mono);color:var(--gris)}
.fig .fig-cab .cuando b{color:var(--aviso)}
.fig .director{display:inline-flex;align-items:center;gap:10px;border:2px solid #6366f1;border-radius:8px;padding:8px 12px;background:var(--fondo);margin:0 auto 6px;max-width:100%;text-align:left}
.fig .director .nom{font:700 .92rem var(--mono)}.fig .director .que{font-size:.78rem;color:var(--gris);max-width:48ch}
.fig .chapa{font:700 .56rem var(--mono);letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 7px;white-space:nowrap}
.fig .chapa.dir{background:#6366f1;color:#fff}.fig .chapa.obr{background:var(--hueco);color:var(--tinta)}
.fig .centro{text-align:center}.fig .baja{font:.7rem var(--mono);color:var(--gris);text-align:center;margin:2px 0 10px}
.fig .baja::before{content:"↓ "}
.fig .pasos{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.fig .paso{border:1px solid var(--linea);border-radius:8px;background:var(--fondo);padding:8px 10px;display:flex;flex-direction:column;gap:6px;position:relative;min-width:0}
.fig .paso .num{position:absolute;top:-9px;left:10px;background:var(--tinta);color:var(--fondo);font:700 .62rem var(--mono);border-radius:999px;padding:1px 6px}
.fig .paso header{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:4px}
.fig .paso .nom{font:700 .8rem var(--mono);overflow-wrap:anywhere}
.fig .paso .sk{display:inline-block;font:.66rem var(--mono);border:1px solid var(--linea);border-radius:999px;padding:1px 7px;color:var(--tinta);align-self:flex-start;background:var(--tarjeta)}
.fig .caja{border:1px solid var(--linea);border-radius:6px;padding:4px 7px;font:.68rem/1.35 var(--mono);color:var(--tinta);background:var(--tarjeta)}
.fig .caja .et{display:block;font:600 .56rem var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--gris)}
.fig .caja.ext{border-style:dashed}.fig .caja.her{box-shadow:inset 3px 0 0 var(--gris)}.fig .caja.deja{border-color:var(--ok);background:color-mix(in srgb,var(--ok) 8%,var(--tarjeta))}
.fig .paso .hace{font-size:.74rem;color:var(--gris);line-height:1.35}
.fig .leyenda{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px;font-size:.74rem;color:var(--gris)}
.fig .leyenda span{display:flex;align-items:center;gap:6px}.fig .leyenda i{display:inline-block;width:20px;height:12px;border:1px solid var(--gris);border-radius:3px}
.fig .leyenda i.ext{border-style:dashed}.fig .leyenda i.her{box-shadow:inset 3px 0 0 var(--gris)}.fig .leyenda i.deja{border-color:var(--ok);background:color-mix(in srgb,var(--ok) 8%,var(--tarjeta))}
.fig .leyenda i.dir{border:2px solid #6366f1}.fig .leyenda i.obr{border:1.5px solid var(--tinta)}
.flujo{border-left-color:var(--c,var(--acento))}
.plano{--mi:140px;position:relative;padding:6px 40px 6px var(--mi);margin:8px 0 20px}
.plano-hilos{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible;color:var(--gris)}
.plano-hilos path{fill:none;stroke:currentColor;stroke-width:1.5}.plano-hilos path.vig{stroke-dasharray:5 4}.plano-hilos path.aviso{stroke-dasharray:1.5 4;stroke-linecap:round}.plano-hilos path.candado{stroke-dasharray:2 3;stroke:var(--mal)}.plano-hilos path.falta{stroke-dasharray:3 5;opacity:.6}
.plano-hilos text{font:600 .6rem var(--mono);fill:var(--gris);paint-order:stroke;stroke:var(--fondo);stroke-width:3px;stroke-linejoin:round}
.capa{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;position:relative;margin:0 0 42px}.capa:last-child{margin-bottom:0}
.capa-et{position:absolute;left:calc(var(--mi) * -1);top:0;width:65px;font:700 .58rem/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--gris);text-align:right;padding-top:10px}
.actor{position:relative;grid-column:span 3;border:1px solid var(--linea);background:var(--tarjeta);border-radius:8px;padding:10px 12px;min-width:0;display:flex;flex-direction:column;gap:6px;box-shadow:var(--sombra-sm)}
.actor.persona{border-color:var(--aviso);background:color-mix(in srgb,var(--aviso) 8%,var(--tarjeta))}.actor.canal{border-style:dashed;border-color:var(--ok);background:color-mix(in srgb,var(--ok) 6%,var(--tarjeta))}
.actor.continuo{border-width:2px;border-color:#6366f1}.actor.tablero{border-color:#4f46e5}.actor.base{border-color:var(--linea);background:var(--fondo)}
.actor.vault{border-color:#4f46e5;border-radius:4px;background:repeating-linear-gradient(0deg,transparent 0 22px,color-mix(in srgb,#4f46e5 8%,transparent) 22px 23px),color-mix(in srgb,#4f46e5 4%,var(--tarjeta))}
.actor.contexto{border-color:#6366f1;border-style:double;border-width:3px;background:color-mix(in srgb,#6366f1 6%,var(--tarjeta))}
.actor.falta{border-style:dashed;background:var(--tarjeta-subtle);color:var(--gris)}.actor.falta h4{color:var(--gris)}
.actor>header{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.actor h4{margin:0;font-size:.92rem;line-height:1.2}.actor h4 small{display:block;font:.66rem/1.3 var(--mono);color:var(--gris);font-weight:400;margin-top:1px}
.chapa-act{margin-left:auto;font:700 .56rem var(--mono);letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 7px;background:var(--hueco);color:var(--tinta);white-space:nowrap}
.chapa-act.res{background:#6366f1;color:#fff}.chapa-act.reloj{background:var(--aviso);color:#fff}.chapa-act.efi{background:transparent;border:1px dashed var(--gris);color:var(--gris)}.chapa-act.conv{background:var(--ok);color:#fff}.chapa-act.falta{background:transparent;border:1px dashed var(--mal);color:var(--mal)}
.actor p{margin:0;font-size:.78rem;line-height:1.4;color:var(--gris)}
.actor .dato{display:flex;flex-wrap:wrap;gap:4px 6px;margin:0;padding:0;list-style:none}.actor .dato li{font:.68rem/1.3 var(--mono);color:var(--tinta);border:1px solid var(--linea);border-radius:5px;padding:2px 6px;background:var(--tarjeta);max-width:100%;overflow-wrap:anywhere}
.actor .dato li.ok{border-color:var(--ok)}.actor .dato li.no{border-color:var(--mal);color:var(--mal)}.actor .dato li b{font-weight:600;color:var(--gris)}.actor .dato li[data-globo]{cursor:help}
.actor .dato li.terr{border:1px solid var(--c);background:var(--cs);color:var(--c);font-weight:600}.actor .dato li.terr.falta-nt{border-style:dashed;background:transparent;opacity:.55}.actor .dato li.terr.t900{color:var(--tinta)}.actor .dato li.terr b{color:inherit;font-weight:700;margin-right:4px}
.leyenda-act{display:flex;flex-wrap:wrap;gap:14px;font-size:.8rem;color:var(--gris);padding:10px 14px;background:var(--tarjeta);border:1px solid var(--linea);border-radius:8px;box-shadow:var(--sombra-sm)}.leyenda-act span{display:flex;align-items:center;gap:6px}.leyenda-act .chapa-act{margin-left:0}
@media (max-width:760px){.plano{padding-left:0;padding-right:0}.capa{grid-template-columns:1fr;margin-bottom:28px}.capa-et{position:static;width:auto;text-align:left;padding:0 0 6px}.actor{grid-column:1/-1!important}}
.flujo.fantasma{border-style:dashed;border-left-style:dashed;opacity:.62;filter:grayscale(1)}.flujo.fantasma h4::after{content:" · así se vería";font:.72rem var(--mono);color:var(--gris)}
.flujo.inferido{border-left-color:var(--aviso)}.flujo.inferido h4::after{content:" · inferido, no declarado";font:.72rem var(--mono);color:var(--aviso)}

/* Kanban Studio Minimal */
.kb-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:14px;align-items:start}
.kb-col{background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:14px;display:flex;flex-direction:column;gap:10px;box-shadow:var(--sombra-sm)}
.kb-col h3{font:700 .75rem var(--mono);margin:0 0 2px;display:flex;justify-content:space-between;align-items:center;text-transform:uppercase;letter-spacing:.08em;color:var(--gris)}
.kb-col h3 span{background:var(--tarjeta-subtle);border:1px solid var(--linea);border-radius:var(--radio-pill);padding:1px 8px;font-size:.72rem;color:var(--tinta);font-variant-numeric:tabular-nums}
.kb-card{background:var(--fondo);border:1px solid var(--linea);border-radius:8px;padding:12px 14px;font-size:.85rem;display:flex;flex-direction:column;gap:7px;box-shadow:var(--sombra-sm);transition:all .15s cubic-bezier(0.16,1,0.3,1);cursor:pointer}
.kb-card:hover{border-color:color-mix(in srgb,var(--acento) 40%,var(--linea));box-shadow:var(--sombra-md);transform:translateY(-1.5px)}
.kb-card b{font-size:.88rem;font-weight:600;color:var(--tinta);line-height:1.35;letter-spacing:-0.01em}
.kb-card p{margin:0;font-size:.8rem;color:var(--gris);line-height:1.45}
.kb-card .meta{font:.72rem var(--mono);color:var(--gris);display:flex;flex-wrap:wrap;gap:5px;margin-top:4px;align-items:center}
.kb-card .tag{padding:2px 7px;border-radius:5px;background:var(--tarjeta);border:1px solid var(--linea);color:var(--tinta);font-size:.7rem;font-weight:500;font-family:var(--mono)}
.kb-card .tag.prio-alta{background:color-mix(in srgb,var(--mal) 12%,var(--tarjeta));border-color:color-mix(in srgb,var(--mal) 30%,transparent);color:var(--mal);font-weight:600}
.kb-card .tag.prio-media{background:color-mix(in srgb,var(--aviso) 12%,var(--tarjeta));border-color:color-mix(in srgb,var(--aviso) 30%,transparent);color:var(--aviso);font-weight:600}
.kb-card .tag.prio-baja{background:color-mix(in srgb,var(--ok) 12%,var(--tarjeta));border-color:color-mix(in srgb,var(--ok) 30%,transparent);color:var(--ok);font-weight:600}
.kb-vacio{color:var(--gris);font-style:italic;font-size:.82rem;padding:16px 4px;text-align:center}

/* Roadmap Studio Minimal */
.rm-header{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:16px 20px;margin-bottom:16px;box-shadow:var(--sombra-sm)}
.rm-barra-wrap{flex:1;min-width:240px}
.rm-barra-info{display:flex;justify-content:space-between;font:600 .78rem var(--mono);color:var(--gris);margin-bottom:6px;font-variant-numeric:tabular-nums}
.rm-barra{height:8px;background:var(--fondo);border:1px solid var(--linea);border-radius:999px;overflow:hidden}
.rm-fill{height:100%;background:linear-gradient(90deg,var(--acento),var(--ok));border-radius:999px;transition:width .5s cubic-bezier(0.16,1,0.3,1)}
.rm-filtros{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.cu-h{margin:26px 0 4px;font-size:1rem;font-weight:600;color:var(--tinta)}
.cu-kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font:.8rem/1.5 var(--mono);margin:0}
.cu-kv dt{color:var(--gris)}.cu-kv dd{margin:0;overflow-wrap:anywhere}
.cu-sev{font:600 .7rem var(--mono);text-transform:uppercase;letter-spacing:.05em}
.cu-sev.alta{color:var(--mal)}.cu-sev.media{color:var(--aviso)}.cu-sev.baja{color:var(--gris)}
.rm-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:12px}
.rm-card{background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:14px 16px;display:flex;flex-direction:column;justify-content:space-between;gap:8px;box-shadow:var(--sombra-sm);transition:all .15s cubic-bezier(0.16,1,0.3,1)}
.rm-card:hover{border-color:color-mix(in srgb,var(--acento) 40%,var(--linea));box-shadow:var(--sombra-md);transform:translateY(-1.5px)}
.rm-card h4{margin:0;font-size:.92rem;font-weight:600;line-height:1.35;color:var(--tinta)}
.rm-card p{margin:0;font-size:.82rem;color:var(--gris);line-height:1.45}
.rm-card .meta{font:.72rem var(--mono);display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--linea);padding-top:8px;margin-top:4px}
.rm-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:5px;font:600 .7rem var(--mono);border:1px solid transparent}
.rm-badge.completado{background:color-mix(in srgb,var(--ok) 12%,var(--tarjeta));color:var(--ok);border-color:color-mix(in srgb,var(--ok) 25%,transparent)}
.rm-badge.en_curso{background:color-mix(in srgb,var(--acento) 12%,var(--tarjeta));color:var(--acento);border-color:color-mix(in srgb,var(--acento) 25%,transparent)}
.rm-badge.pendiente{background:color-mix(in srgb,var(--aviso) 12%,var(--tarjeta));color:var(--aviso);border-color:color-mix(in srgb,var(--aviso) 25%,transparent)}
.rm-badge.bloqueado{background:color-mix(in srgb,var(--gris) 12%,var(--tarjeta));color:var(--gris);border-color:color-mix(in srgb,var(--gris) 25%,transparent)}
/* Mission Control Action Bar */
.kb-action-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:10px 14px;margin:10px 0 16px;box-shadow:var(--sombra-sm)}
.kb-status-pill{display:inline-flex;align-items:center;gap:8px;font:600 .75rem var(--mono);color:var(--tinta);background:var(--tarjeta-subtle);border:1px solid var(--linea);border-radius:999px;padding:4px 10px}
.kb-btn-group{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.mc-btn{border:1px solid var(--linea);background:var(--tarjeta);color:var(--tinta);border-radius:6px;padding:6px 12px;font:600 .8rem var(--sans);cursor:pointer;transition:all .15s ease;display:inline-flex;align-items:center;gap:6px}
.mc-btn:hover{background:var(--tarjeta-subtle);border-color:var(--gris)}
.mc-btn-primary{background:var(--acento);color:#fff;border-color:var(--acento)}
.mc-btn-primary:hover{background:color-mix(in srgb,var(--acento) 85%,#000);border-color:color-mix(in srgb,var(--acento) 85%,#000);color:#fff}
.mc-btn-icon{padding:6px 9px;font-size:.95rem}
.mc-btn:disabled{opacity:.5;cursor:not-allowed}
/* Toast flotante */
.kb-toast{position:fixed;bottom:24px;right:24px;z-index:99;background:var(--tarjeta);border:1px solid var(--linea);border-radius:8px;padding:12px 18px;font:500 .84rem var(--sans);color:var(--tinta);box-shadow:0 8px 30px rgba(0,0,0,0.3);display:flex;align-items:center;gap:10px;transition:opacity .2s ease,transform .2s ease}
.kb-toast.ok{border-left:4px solid var(--ok)}
.kb-toast.error{border-left:4px solid var(--mal)}
.kb-toast.info{border-left:4px solid var(--acento)}
/* Modal Nueva Tarjeta */
.mc-modal{border:1px solid var(--linea);border-radius:12px;background:var(--tarjeta);color:var(--tinta);padding:20px 24px;max-width:480px;width:90vw;box-shadow:0 16px 40px rgba(0,0,0,0.5)}
.mc-modal::backdrop{background:rgba(0,0,0,0.6);backdrop-filter:blur(4px)}
.mc-modal-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.mc-modal-header h3{margin:0;font-size:1.05rem;font-weight:600}
.mc-modal-close{background:transparent;border:0;color:var(--gris);font-size:1.1rem;cursor:pointer;padding:4px}
.mc-modal-close:hover{color:var(--tinta)}
.mc-modal-body{display:flex;flex-direction:column;gap:12px}
.mc-modal-body label{display:flex;flex-direction:column;gap:4px;font:600 .74rem var(--mono);color:var(--gris);text-transform:uppercase;letter-spacing:.06em}
.mc-modal-body input,.mc-modal-body select,.mc-modal-body textarea{border:1px solid var(--linea);background:var(--fondo);color:var(--tinta);border-radius:6px;padding:8px 10px;font:.86rem var(--sans);outline:none;transition:border-color .15s ease}
.mc-modal-body input:focus,.mc-modal-body select:focus,.mc-modal-body textarea:focus{border-color:var(--acento);box-shadow:0 0 0 2px var(--acento-glow)}
.mc-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.mc-modal-footer{display:flex;justify-content:flex-end;gap:10px;margin-top:20px;padding-top:14px;border-top:1px solid var(--linea)}
.mc-modal-large{max-width:720px;width:95vw}
.mc-meta-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;font:.74rem var(--mono)}
.mc-card-section{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
.mc-card-section label{font:700 .7rem var(--mono);color:var(--gris);text-transform:uppercase;letter-spacing:.08em}
.mc-card-text{font-size:.88rem;color:var(--tinta);margin:0;line-height:1.5}
.mc-card-full-body{margin:0;padding:12px;border-radius:6px;background:var(--fondo);border:1px solid var(--linea);font:.78rem/1.5 var(--mono);color:var(--tinta);max-height:300px;overflow-y:auto;white-space:pre-wrap}
.sk-top-bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.sk-top-bar .buscador{flex:1;min-width:240px;margin-bottom:0}
.sk-mode-toggle{display:inline-flex;background:var(--tarjeta);border:1px solid var(--linea);border-radius:8px;padding:3px;gap:4px}
.sk-toggle-btn{border:0;background:transparent;color:var(--gris);border-radius:6px;padding:5px 12px;font:600 .75rem var(--mono);cursor:pointer;transition:all .15s ease}
.sk-toggle-btn.active{background:var(--fondo);color:var(--tinta);box-shadow:0 1px 3px rgba(0,0,0,0.2)}
.chip-h{display:inline-block;padding:2px 6px;border-radius:4px;font:600 .68rem var(--mono);background:color-mix(in srgb, var(--acento) 12%, var(--tarjeta));color:var(--acento);border:1px solid color-mix(in srgb, var(--acento) 25%, transparent);margin-right:4px}
.chip-loc{display:inline-block;padding:2px 6px;border-radius:4px;font:600 .68rem var(--mono);background:color-mix(in srgb, var(--ok) 12%, var(--tarjeta));color:var(--ok);border:1px solid color-mix(in srgb, var(--ok) 25%, transparent);margin-right:4px}
.chip-copias{display:inline-block;padding:2px 6px;border-radius:4px;font:600 .68rem var(--mono);background:color-mix(in srgb, var(--aviso) 12%, var(--tarjeta));color:var(--aviso);border:1px solid color-mix(in srgb, var(--aviso) 25%, transparent)}
.cal-dia{cursor:pointer;transition:all .15s ease}
.cal-dia:hover{background:color-mix(in srgb, var(--acento) 10%, var(--tarjeta));border-color:var(--acento)}
.cal-dia.seleccionado{border-color:var(--acento)!important;background:color-mix(in srgb, var(--acento) 16%, var(--tarjeta))!important;box-shadow:0 0 0 2px var(--acento)}
.cal-timeline-box{margin-top:20px;padding:16px 20px;border-radius:12px;background:var(--tarjeta);border:1px solid var(--linea);box-shadow:var(--sombra-sm)}
.cal-timeline-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;border-bottom:1px solid var(--linea);padding-bottom:10px}
.cal-timeline-header h3{margin:0;font-size:1.05rem;font-weight:600;color:var(--tinta)}
.cal-timeline-sub{font-size:.78rem;color:var(--gris);font-family:var(--mono)}
.cal-timeline-badge{font:600 .7rem var(--mono);padding:3px 10px;border-radius:999px;background:color-mix(in srgb,var(--ok) 12%,var(--tarjeta));color:var(--ok);border:1px solid color-mix(in srgb,var(--ok) 30%,transparent)}
.cal-timeline-lista{display:flex;flex-direction:column;gap:8px}
.cal-tl-item{display:flex;align-items:center;gap:14px;padding:10px 14px;border-radius:8px;background:var(--fondo);border:1px solid var(--linea);transition:all .15s ease}
.cal-tl-item:hover{border-color:color-mix(in srgb,var(--acento) 40%,var(--linea))}
.cal-tl-time{font:700 .84rem var(--mono);color:var(--acento);min-width:110px}
.cal-tl-info{flex:1;display:flex;flex-direction:column;gap:3px}
.cal-tl-name{font-weight:600;font-size:.9rem;color:var(--tinta);display:flex;align-items:center;gap:8px}
.cal-tl-desc{font-size:.8rem;color:var(--gris)}
.cal-tl-cadencia{font:600 .68rem var(--mono);padding:1px 6px;border-radius:4px;background:var(--tarjeta);border:1px solid var(--linea);color:var(--gris)}
.cal-tl-source{font:600 .72rem var(--mono);color:var(--gris);text-align:right}
.cal-tl-vacio{font-style:italic;color:var(--gris);padding:16px;text-align:center;font-size:.85rem}
/* Agentes y Pipelines */
.ag-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:14px}
.ag-card{background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:16px 18px;display:flex;flex-direction:column;gap:10px;box-shadow:var(--sombra-sm);transition:all .15s ease}
.ag-card:hover{border-color:color-mix(in srgb,var(--acento) 40%,var(--linea));box-shadow:var(--sombra-md);transform:translateY(-1.5px)}
.ag-card-header{display:flex;align-items:center;justify-content:space-between;gap:8px}
.ag-card-title{font-size:1.02rem;font-weight:700;color:var(--tinta);display:flex;align-items:center;gap:8px}
.ag-model{font:600 .72rem var(--mono);padding:2px 8px;border-radius:4px;background:color-mix(in srgb,var(--acento) 12%,var(--tarjeta));color:var(--acento);border:1px solid color-mix(in srgb,var(--acento) 25%,transparent)}
.ag-cadence{font:600 .74rem var(--mono);color:var(--gris)}
.ag-desc{font-size:.84rem;color:var(--gris);line-height:1.45;margin:0}
.ag-tools{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}
.ag-tool-tag{font:500 .68rem var(--mono);padding:1px 6px;border-radius:4px;background:var(--fondo);border:1px solid var(--linea);color:var(--tinta)}
.pipe-card{background:var(--tarjeta);border:1px solid var(--linea);border-radius:var(--radio-card);padding:14px 16px;margin-bottom:12px;box-shadow:var(--sombra-sm)}
.pipe-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pipe-title{font-weight:600;font-size:.92rem;color:var(--tinta)}
.pipe-steps{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:6px}
.pipe-step{background:var(--fondo);border:1px solid var(--linea);border-radius:6px;padding:4px 10px;font:600 .75rem var(--mono);color:var(--tinta)}
.pipe-arrow{color:var(--acento);font-weight:bold}
/* Sub-nav de Skills */
.sk-subnav{display:inline-flex;background:var(--tarjeta);border:1px solid var(--linea);border-radius:8px;padding:3px;gap:4px}
.sk-subtab{border:0;background:transparent;color:var(--gris);border-radius:6px;padding:5px 14px;font:600 .78rem var(--sans);cursor:pointer;transition:all .15s ease}
.sk-subtab:hover{color:var(--tinta)}
.sk-subtab.active{background:var(--fondo);color:var(--tinta);box-shadow:0 1px 3px rgba(0,0,0,0.2);font-weight:600}
/* Filtros por sección Roadmap */
.rm-sec-f{border:1px solid var(--linea);background:var(--tarjeta);color:var(--gris);border-radius:var(--radio-pill);padding:3px 10px;font:500 .72rem var(--sans);cursor:pointer;transition:all .15s ease}
.rm-sec-f:hover{color:var(--tinta);border-color:var(--gris)}
.rm-sec-f[aria-pressed=true]{background:var(--acento);color:#fff;border-color:var(--acento);font-weight:600}
.rm-sec-tag{font:600 .68rem var(--mono);color:var(--gris);background:var(--tarjeta-subtle);border:1px solid var(--linea);padding:1px 6px;border-radius:4px}
/* Transición de estados en modal de tarjeta */
.vc-move-group{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.vc-move-btn{font-size:.76rem;padding:4px 10px}
.pie{margin-top:32px;color:var(--gris);font-size:.82rem;border-top:1px solid var(--linea);padding-top:12px}
[hidden]{display:none!important}
</style></head><body>
<header class="topline">
  <div class="brand">
    <div class="brand-title">
      <h1>Sistema Maestro</h1>
      <span class="version-badge"><span class="live-dot"></span><span id="version"></span></span>
    </div>
    <p class="brand-sub">Centro de Control · Agentes, Skills, Tablero Kanban &amp; Roadmap</p>
  </div>
  <div class="controles">
    <span class="sw-wrap"><span class="sw-et" id="priv-et">Privacidad</span><button id="priv" type="button" role="switch" aria-checked="false" aria-labelledby="priv-et"></button></span>
    <button id="tema" type="button" aria-label="Cambiar entre tema claro y oscuro" title="Cambiar tema">☀︎</button>
  </div>
</header>
<p class="aviso-priv" id="aviso-priv" hidden></p>
<div class="cifras" id="cifras"></div>
<nav class="pestanas" role="tablist">
  <button role="tab" aria-selected="true" data-v="kanban">Tablero Kanban</button>
  <button role="tab" aria-selected="false" data-v="roadmap">Roadmap Sistema</button>
  <button role="tab" aria-selected="false" data-v="cal">Calendario &amp; Agenda</button>
  <button role="tab" aria-selected="false" data-v="skills">Skills &amp; Contratos</button>
  <button role="tab" aria-selected="false" data-v="agentes">Agentes del Sistema</button>
  <button role="tab" aria-selected="false" data-v="actores">Arquitectura Vault</button>
  <button role="tab" aria-selected="false" data-v="cuentas">Cuentas Claude Code</button>
</nav>
<section id="v-kanban">
  <p class="sub">Tablero Headless Kanban en vivo (<code>03 Proyectos/Kanban/</code>). Tarjetas procesadas por agentes atómicos desatendidos y el despachador determinista.</p>
  <div class="kb-action-bar">
    <div class="kb-status-pill">
      <span class="live-dot" id="server-dot"></span>
      <span id="server-status-text">Mission Control</span>
    </div>
    <div class="kb-btn-group">
      <button type="button" class="mc-btn mc-btn-primary" id="btn-dispatch-next" title="Despacha la siguiente tarea pendiente">
        ▶ Despachar Siguiente
      </button>
      <button type="button" class="mc-btn" id="btn-open-modal" title="Crear una nueva tarjeta en Kanban">
        + Nueva Tarjeta
      </button>
      <button type="button" class="mc-btn mc-btn-icon" id="btn-refresh" title="Refrescar tablero">
        ↻
      </button>
    </div>
  </div>
  <div id="kb-toast" class="kb-toast" hidden></div>
  <dialog id="modal-new-card" class="mc-modal">
    <form id="form-new-card" method="dialog">
      <div class="mc-modal-header">
        <h3>Nueva Tarjeta Kanban</h3>
        <button type="button" class="mc-modal-close" id="btn-close-modal">✕</button>
      </div>
      <div class="mc-modal-body">
        <label>Título de la Tarea:
          <input type="text" id="nc-title" required placeholder="Ej: Auditar enlaces rotos del vault...">
        </label>
        <div class="mc-grid-2">
          <label>Agente:
            <select id="nc-agent">
              <option value="general">general (Asistido)</option>
              <option value="mantenedor">mantenedor (Mantenimiento)</option>
              <option value="cerrador">cerrador (Cierre del día)</option>
              <option value="procesador-raw">procesador-raw (Ingesta)</option>
              <option value="vigilante">vigilante (Watchdog)</option>
              <option value="redactor">redactor (Contenido)</option>
            </select>
          </label>
          <label>Skill:
            <select id="nc-skill">
              <option value="rankear-ideas">rankear-ideas</option>
              <option value="check-links">check-links</option>
              <option value="mantener-el-vault">mantener-el-vault</option>
              <option value="cerrar-el-dia">cerrar-el-dia</option>
              <option value="procesar-capturas">procesar-capturas</option>
              <option value="vigilante">vigilante</option>
              <option value="redactar">redactar</option>
              <option value="manual">manual (Asistida)</option>
            </select>
          </label>
        </div>
        <label>Prioridad:
          <select id="nc-priority">
            <option value="🟡 Media">🟡 Media</option>
            <option value="🔥 Alta">🔥 Alta</option>
            <option value="🟢 Baja">🟢 Baja</option>
          </select>
        </label>
        <label>Objetivo / Instrucciones:
          <textarea id="nc-objective" rows="3" placeholder="Detalle de qué debe realizar esta tarjeta..."></textarea>
        </label>
      </div>
      <div class="mc-modal-footer">
        <button type="button" class="mc-btn" id="btn-cancel-modal">Cancelar</button>
        <button type="submit" class="mc-btn mc-btn-primary">Crear Tarjeta</button>
      </div>
    </form>
  </dialog>
  <dialog id="modal-view-card" class="mc-modal mc-modal-large">
    <div class="mc-modal-header">
      <h3 id="vc-title">Detalle de Tarjeta</h3>
      <button type="button" class="mc-modal-close" id="btn-close-view-modal">✕</button>
    </div>
    <div class="mc-modal-body">
      <div class="mc-meta-row" id="vc-meta"></div>
      <div class="mc-card-section">
        <label>Objetivo</label>
        <p id="vc-obj" class="mc-card-text"></p>
      </div>
      <div class="mc-card-section">
        <label>Contenido / Requisitos</label>
        <pre id="vc-cuerpo" class="mc-card-full-body"></pre>
      </div>
      <div class="mc-card-section" id="vc-move-section">
        <label>Mover de Columna / Estado</label>
        <div class="vc-move-group">
          <button type="button" class="mc-btn vc-move-btn" data-to="pendientes" id="vc-move-pend">📥 A Pendiente</button>
          <button type="button" class="mc-btn vc-move-btn" data-to="en_progreso" id="vc-move-prog">⚙️ En Progreso</button>
          <button type="button" class="mc-btn vc-move-btn" data-to="hecho" id="vc-move-hecho">✅ Hecho</button>
          <button type="button" class="mc-btn vc-move-btn" data-to="archivado" id="vc-move-arch">📦 Archivar</button>
        </div>
      </div>
    </div>
    <div class="mc-modal-footer">
      <button type="button" class="mc-btn" id="btn-close-view-footer">Cerrar</button>
      <button type="button" class="mc-btn mc-btn-primary" id="btn-vc-dispatch" hidden>▶ Despachar esta tarea</button>
    </div>
  </dialog>
  <div class="kb-grid" id="kb-tablero"></div>
</section>
<section id="v-roadmap" hidden>
  <p class="sub">Evolución y próximos builds estratégicos de <a href="file:///c:/Users/aguil/Vaults/sistema-maestro/01 Index/Roadmap del Sistema.md" style="color:inherit;text-decoration:underline;">Roadmap del Sistema</a>.</p>
  <div id="rm-resumen"></div>
  <div class="buscador"><input id="q-rm" type="search" placeholder="Escribe para filtrar hitos del roadmap por título o detalle…" aria-label="Filtrar roadmap"></div>
  <div class="rm-filtros" id="rm-filtros"></div>
  <div class="rm-filtros" id="rm-sec-filtros" style="margin-top:-6px;margin-bottom:16px;"></div>
  <div class="rm-grid" id="rm-lista"></div>
</section>
<section id="v-cuentas" hidden>
  <p class="sub">Una carpeta y un comando por cuenta de Claude Code (<code>CLAUDE_CONFIG_DIR</code>). Lo que queda separado: login, MCP de usuario, historial y plugins. Lo que no: el disco, la identidad de git y las credenciales de la máquina. Guía completa en <b>00 Sistema/Guía - Varias cuentas de Claude Code en la misma máquina.md</b>.</p>
  <div id="cu-resumen"></div>
  <div class="rm-grid" id="cu-tarjetas"></div>
  <h3 class="cu-h">Skills: enlace o copia</h3>
  <p class="sub">Con la política <b>aislado</b>, lo que no querés es que dos perfiles apunten al mismo origen. Una copia propia que deriva es el precio aceptado.</p>
  <div class="tabla" id="cu-matriz"></div>
  <h3 class="cu-h">Diagnóstico</h3>
  <div class="rm-grid" id="cu-diag"></div>
</section>
<section id="v-skills" hidden>
  <div class="sk-top-bar">
    <div class="sk-subnav" role="tablist">
      <button type="button" class="sk-subtab active" data-sub="tabla">Tabla de Skills</button>
      <button type="button" class="sk-subtab" data-sub="grafo">Entradas y Salidas</button>
      <button type="button" class="sk-subtab" data-sub="cadenas">Cadenas Inferidas (<span id="cnt-sk-inf">0</span>)</button>
    </div>
    <div class="sk-mode-toggle" id="sk-mode-toggle-wrap">
      <button type="button" class="sk-toggle-btn active" id="btn-sk-canon">Consolidadas (<span id="cnt-sk-canon">0</span>)</button>
      <button type="button" class="sk-toggle-btn" id="btn-sk-todas">En disco (<span id="cnt-sk-todas">0</span>)</button>
    </div>
  </div>

  <div id="sk-subview-tabla">
    <div class="buscador"><input id="q" type="search" placeholder="Escribe para filtrar por nombre o descripción…" aria-label="Filtrar skills"></div>
    <div class="sk-filtros" id="sk-filtros"></div>
    <div class="tabla"><table><thead><tr><th></th><th>Skill</th><th>Herramientas / Arneses</th><th>Qué hace</th><th>La monta</th><th>Tamaño</th><th>Tokens ≈</th><th>Tocada</th><th>Avisos</th></tr></thead><tbody id="tb"></tbody></table></div>
  </div>

  <div id="sk-subview-grafo" hidden>
    <p class="sub">Solo skills (los agentes, en su pestaña). Para cada una: a la izquierda <b>qué lee</b>, en el centro la skill y qué hace, a la derecha <b>qué produce y dónde lo deja</b>. <span class="chip decl">declarado</span> · <span class="chip inf">inferido</span> · <span class="chip sup">supuesto</span></p>
    <div class="buscador"><input id="q-rel" type="search" placeholder="Escribe para filtrar por skill, fichero o carpeta…" aria-label="Filtrar entradas y salidas"></div>
    <div id="grafo"></div>
  </div>

  <div id="sk-subview-cadenas" hidden>
    <p class="sub">Flujos posibles inferidos encadenando automáticamente lo que una skill deja con lo que otra lee.</p>
    <div id="sk-cadenas-lista" class="lista-flujos"></div>
  </div>
</section>
<section id="v-cal" hidden><p class="sub"><b>Agentes y tareas programadas en esta máquina</b>: Barriendo el Programador de Tareas de Windows (Task Scheduler), cron y programaciones declaradas en skills. Haz clic en cualquier día para inspeccionar el cronograma horario detallado.</p>
  <div class="cal-resumen" id="cal-resumen" aria-label="Lo programado, por cadencia"></div>
  <div class="cal-cabecera"><button type="button" class="cal-nav" id="cal-prev" aria-label="Mes anterior">‹</button><h3 class="cal-mes" id="cal-mes"></h3><button type="button" class="cal-nav" id="cal-next" aria-label="Mes siguiente">›</button><button type="button" class="cal-hoy" id="cal-hoy">hoy</button></div>
  <div class="cal-semana"><span>lun</span><span>mar</span><span>mié</span><span>jue</span><span>vie</span><span>sáb</span><span>dom</span></div>
  <div class="cal-rejilla" id="cal-rejilla"></div><div class="cal-leyenda" id="cal-leyenda"></div>

  <!-- Timeline Diario Interactivo -->
  <div class="cal-timeline-box" id="cal-timeline-box">
    <div class="cal-timeline-header">
      <div>
        <h3 id="cal-timeline-titulo">Agenda del Día</h3>
        <span id="cal-timeline-sub" class="cal-timeline-sub"></span>
      </div>
      <div class="cal-timeline-badge" id="cal-timeline-badge">● Tareas Programadas Windows</div>
    </div>
    <div id="cal-timeline-lista" class="cal-timeline-lista"></div>
  </div>

  <h2>Lo que corre solo en esta máquina</h2><div class="cal" id="cal"></div></section>
<div id="globo" role="tooltip" aria-hidden="true"></div>
<section id="v-actores" hidden><p class="sub">Lo que hay <b>alrededor</b> de tus agentes en esta máquina: con qué herramienta hablas, por dónde, qué corre solo, qué candados hay y sobre qué carpeta trabajan. Lo que existe sale con trazo lleno; lo que falta para que esto sea un sistema, con trazo discontinuo. Pasa el cursor por las etiquetas.</p>
  <div class="plano" id="plano"><svg class="plano-hilos" id="plano-hilos" aria-hidden="true"></svg><div id="plano-capas"></div></div>
  <div class="leyenda-act"><span><i class="chapa-act conv">conversa</i>habla contigo</span><span><i class="chapa-act res">residente</i>proceso vivo siempre</span><span><i class="chapa-act reloj">reloj</i>salta a una hora</span><span><i class="chapa-act efi">efímero</i>nace para una tarjeta y muere</span><span><i class="chapa-act falta">falta</i>no detectado</span></div>
</section>
<section id="v-agentes" hidden>
  <p class="sub">Roster de agentes atómicos de Sistema Maestro (<code>.claude/agents/*.md</code>) y pipelines de ejecución multi-paso declarados en tarjetas Kanban.</p>
  <h2>Agentes Especializados</h2>
  <div class="ag-grid" id="ag-grid"></div>

  <h2 style="margin-top:28px;">Pipelines de Ejecución Kanban</h2>
  <p class="sub">Cadenas de pasos declaradas en tareas Kanban (<code>pipeline: [...]</code>) listas para despachar.</p>
  <div id="pipe-lista"></div>
</section>
<p class="pie">Generado por «Mapa de mis agentes» el <span id="fecha"></span>. Solo lectura: no ha tocado ningún fichero, no ha usado internet ni claves.</p>
<script>
const D = __DATOS__;
const $ = s => document.querySelector(s);
const escT = v => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
// Tema claro/oscuro: sigue al sistema hasta que pulsas el sol/la luna; la elección se guarda en este navegador.
const bt = $("#tema");
function oscuroAhora(){ const t = document.documentElement.dataset.theme; return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches; }
function pintarTema(){ bt.textContent = oscuroAhora() ? "☀︎" : "☾"; }
bt.addEventListener("click", () => { const sig = oscuroAhora() ? "light" : "dark"; document.documentElement.dataset.theme = sig; try { localStorage.setItem("tema-mapa-agentes", sig); } catch (e) {} pintarTema(); });
try { const g = localStorage.getItem("tema-mapa-agentes"); if (g) document.documentElement.dataset.theme = g; } catch (e) {}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", pintarTema); pintarTema();
// Modo privacidad: esconde lo marcado `visibilidad: privado` (o `private: true`) en el frontmatter y difumina rutas y comandos. Se recuerda entre visitas.
const bp = $("#priv"), avisoP = $("#aviso-priv");
const nPriv = D.skills.filter(s => s.privado).length;
function pintarPriv(on){ document.body.classList.toggle("privado", on); bp.setAttribute("aria-checked", String(on)); avisoP.hidden = !on;
  avisoP.textContent = on ? (nPriv ? `Modo privacidad activo: ${nPriv} ${nPriv === 1 ? "pieza oculta" : "piezas ocultas"}; rutas y comandos difuminados.` : "Modo privacidad activo: rutas y comandos difuminados. No hay ninguna skill marcada como privada (ponle `visibilidad: privado` en su frontmatter para esconderla).") : ""; }
bp.addEventListener("click", () => { const on = bp.getAttribute("aria-checked") !== "true"; try { localStorage.setItem("privacidad-mapa-agentes", on ? "1" : "0"); } catch (e) {} pintarPriv(on); });
try { pintarPriv(localStorage.getItem("privacidad-mapa-agentes") === "1"); } catch (e) { pintarPriv(false); }
$("#fecha").textContent = D.generado;
$("#version").textContent = "v" + (D.version || "1.0") + " · " + D.generado;
const nAv = D.skills.filter(s => (D.avisos[s.ruta]||[]).length).length;
const kbTotal = D.kanban ? D.kanban.total : 0;
const rmPct = D.roadmap ? D.roadmap.stats.progreso_pct + "%" : "0%";
const rmComp = D.roadmap ? D.roadmap.stats.completados : 0;
const rmTot = D.roadmap ? D.roadmap.stats.total : 0;
const nAgentes = D.agentes_reales ? D.agentes_reales.length : D.skills.filter(s=>s.es_agente).length;
$("#cifras").innerHTML = [
  [D.skills.filter(s=>!s.es_agente).length, "skills", "skills"],
  [nAgentes, "agentes", "agentes"],
  [D.skills.filter(s => !s.es_agente && s.es && s.es.opaca).length, "skills opacas", "skills-opacas"],
  [D.tareas.length, "cosas que corren solas", "cal"],
  [kbTotal, "tareas en Kanban", "kanban"],
  [rmPct, `avance Roadmap (${rmComp}/${rmTot} hitos)`, "roadmap"],
  [nAv, "skills con avisos", "skills-avisos"]
].map(([n,t,tg])=>`<div class="cifra" data-target="${tg}" title="Ver ${t}"><b>${n}</b><span>${t}</span></div>`).join("");

function activarPestana(v) {
  document.querySelectorAll(".pestanas button").forEach(x => x.setAttribute("aria-selected", x.dataset.v === v));
  ["kanban","roadmap","cal","skills","agentes","actores","cuentas"].forEach(tab => {
    const el = $("#v-"+tab);
    if (el) el.hidden = (tab !== v);
  });
  if (v === "actores") requestAnimationFrame(dibujarHilos);
}

document.querySelectorAll(".pestanas button").forEach(b => b.addEventListener("click", () => {
  activarPestana(b.dataset.v);
}));

function activarSubSk(subId) {
  document.querySelectorAll(".sk-subtab").forEach(b => b.classList.toggle("active", b.dataset.sub === subId));
  ["tabla", "grafo", "cadenas"].forEach(s => {
    const el = $("#sk-subview-" + s);
    if (el) el.hidden = (s !== subId);
  });
  const toggleWrap = $("#sk-mode-toggle-wrap");
  if (toggleWrap) toggleWrap.style.display = (subId === "tabla") ? "inline-flex" : "none";
}

document.querySelectorAll(".sk-subtab").forEach(b => b.addEventListener("click", () => activarSubSk(b.dataset.sub)));

document.querySelectorAll(".cifra").forEach(c => {
  c.addEventListener("click", () => {
    const tg = c.dataset.target;
    if (tg === "skills") {
      activarPestana("skills");
      activarSubSk("tabla");
    } else if (tg === "skills-opacas") {
      activarPestana("skills");
      activarSubSk("grafo");
    } else if (tg === "skills-avisos") {
      activarPestana("skills");
      activarSubSk("tabla");
      fSk = "avisos";
      pintarFiltrosSk();
      pintar();
    } else if (tg) {
      activarPestana(tg);
    }
  });
});
// Quién monta cada skill: si un AGENTE la llama de verdad, la usan agentes atómicos; si no, la usa el agente continuo (tú, al pedirla).
const montadaPor = {}; D.aristas.forEach(([a,b,fz]) => { const A = D.skills.find(x => x.nombre === a); if (fz === "llama" && A && A.es_agente) (montadaPor[b] = montadaPor[b] || new Set()).add(a); });
let fSk = "todos";
let modoSk = "canon";

function getSkillsActivas() {
  return modoSk === "todas" ? (D.skills_todas || D.skills) : D.skills;
}

const FILTROS_SK = [
  ["todos", "Todas", s => true],
  ["multi", "⚡ Multi-arnés (2+)", s => (s.herramientas || []).length > 1 || (s.copias_count || 1) > 1],
  ["locales", "📁 Locales en Vault", s => s.es_local],
  ["claude", "Claude Code", s => (s.herramientas || [s.herramienta]).includes("Claude Code")],
  ["antigravity", "Gemini / Antigravity", s => (s.herramientas || [s.herramienta]).includes("Gemini / Antigravity")],
  ["30", '<i class="sem ok"></i>Tocadas en 30d', s => s.dias <= 30],
  ["agentes", "Agentes", s => s.es_agente],
  ["avisos", "Con avisos", s => (D.avisos[s.ruta]||[]).length > 0]
];

function pintarFiltrosSk(){
  const dataset = getSkillsActivas();
  const cCanon = D.stats_skills ? D.stats_skills.canonicas : D.skills.length;
  const cTodas = D.stats_skills ? D.stats_skills.todas : (D.skills_todas || []).length;
  if ($("#cnt-sk-canon")) $("#cnt-sk-canon").textContent = cCanon;
  if ($("#cnt-sk-todas")) $("#cnt-sk-todas").textContent = cTodas;
  $("#sk-filtros").innerHTML = FILTROS_SK.map(([k, etq, f]) => `<button type="button" class="sk-f" data-k="${k}" aria-pressed="${fSk===k}">${etq}<span>${dataset.filter(f).length}</span></button>`).join("");
  $("#sk-filtros").querySelectorAll(".sk-f").forEach(b => b.addEventListener("click", () => { fSk = b.dataset.k; pintarFiltrosSk(); pintar(); }));
}

function pintar(){
  const dataset = getSkillsActivas();
  const q = ($("#q").value||"").toLowerCase();
  const filtro = (FILTROS_SK.find(x => x[0] === fSk) || FILTROS_SK[0])[2];
  const filas = dataset.filter(s => filtro(s) && (!q || (s.nombre+" "+s.descripcion).toLowerCase().includes(q))).sort((a,b)=> (D.avisos[b.ruta]||[]).length - (D.avisos[a.ruta]||[]).length || a.nombre.localeCompare(b.nombre));
  $("#tb").innerHTML = filas.map(s => {
    const av = D.avisos[s.ruta]||[];
    const cl = av.length>=3?"mal":av.length?"aviso":"ok";
    const tools = (s.herramientas && s.herramientas.length) ? s.herramientas : [s.herramienta];
    const badgesH = tools.map(h => `<span class="chip-h">${escT(h)}</span>`).join("");
    const badgeLocal = s.es_local ? '<span class="chip-loc" title="Skill local en este vault">local</span>' : '';
    const badgeCopias = (s.copias_count > 1) ? `<span class="chip-copias" title="${escT((s.rutas || []).join('\n'))}">${s.copias_count} instancias</span>` : '';
    return `<tr data-priv="${s.privado?1:0}">
      <td><span class="sem ${cl}"></span></td>
      <td>
        <span class="n">${escT(s.nombre)}</span>
        ${s.es_agente?' <span class="d">(agente)</span>':''}
        ${badgeLocal}
        ${badgeCopias}
      </td>
      <td class="d">${badgesH}</td>
      <td>${escT(s.descripcion)||'<span class="d">—</span>'}</td>
      <td class="d">${s.es_agente ? '—' : (montadaPor[s.nombre] ? [...montadaPor[s.nombre]].sort().join(", ") : 'agente continuo')}</td>
      <td class="d">${s.palabras} pal.</td>
      <td class="d" title="Tokens que cuesta cargarla cada vez (≈ palabras × 1,3)">${Math.round(s.palabras * 1.3).toLocaleString("es-ES")}</td>
      <td class="d">${s.modificado}</td>
      <td><ul class="av">${av.map(a=>`<li>${escT(a)}</li>`).join("")}</ul></td>
    </tr>`;
  }).join("") || `<tr><td colspan="9" class="d">Nada que coincida.</td></tr>`;
}

if ($("#btn-sk-canon")) {
  $("#btn-sk-canon").addEventListener("click", () => {
    modoSk = "canon";
    $("#btn-sk-canon").classList.add("active");
    $("#btn-sk-todas").classList.remove("active");
    pintarFiltrosSk();
    pintar();
  });
}
if ($("#btn-sk-todas")) {
  $("#btn-sk-todas").addEventListener("click", () => {
    modoSk = "todas";
    $("#btn-sk-todas").classList.add("active");
    $("#btn-sk-canon").classList.remove("active");
    pintarFiltrosSk();
    pintar();
  });
}

$("#q").addEventListener("input", pintar); pintarFiltrosSk(); pintar();
const esSkill = {}; D.skills.forEach(s => esSkill[s.nombre] = !s.es_agente);
const sale = {}, entra = {}, saleM = {}, entraM = {};
D.aristas.forEach(([a,b,fz]) => { if (!esSkill[a] || !esSkill[b]) return; if (fz === "llama") { (sale[a]=sale[a]||new Set()).add(b); (entra[b]=entra[b]||new Set()).add(a); } else { (saleM[a]=saleM[a]||new Set()).add(b); (entraM[b]=entraM[b]||new Set()).add(a); } });
function chips(set, setM, vacio){ const f = set && set.size ? [...set].sort().map(n => `<span class="chip" title="Llamada real: hay una instrucción de usar ${n}">${n}</span>`).join("") : "";
  const m = setM && setM.size ? [...setM].sort().filter(n => !(set && set.has(n))).map(n => `<span class="chip mencion" title="Solo la nombra: no hay instrucción de ejecutarla">${n}</span>`).join("") : "";
  return (f + m) || `<span class="chip nadie">${vacio}</span>`; }
const NIVEL = {declarado: ["decl", "Declarado: la ruta está escrita en la skill"], inferido: ["inf", "Inferido: hay un verbo de leer/escribir cerca"], supuesto: ["sup", "Supuesto: la skill no lo dice; se deduce por su tipo"]};
function chipsES(lst){ return lst.length ? lst.map(x => `<span class="chip ${NIVEL[x.nivel][0]}" title="${NIVEL[x.nivel][1]} — ${escT(x.por)}">${escT(x.que)}</span>`).join("") : `<span class="chip nadie">nada</span>`; }
function pintarRel(){
  const q = ($("#q-rel").value || "").toLowerCase();
  const lista = D.skills.filter(s => !s.es_agente && (!q || s.nombre.toLowerCase().includes(q) || (s.es.entradas.concat(s.es.salidas)).some(x => x.que.toLowerCase().includes(q))))
    .sort((a,b) => (b.es.opaca ? 0 : 1) - (a.es.opaca ? 0 : 1) || a.nombre.localeCompare(b.nombre));
  $("#grafo").innerHTML = lista.map(s => { const o = sale[s.nombre]||new Set(); const es = s.es;
    const nE = es.entradas.filter(x => x.nivel !== "supuesto").length, nS = es.salidas.filter(x => x.nivel !== "supuesto").length;
    return `<div class="rel${es.opaca?' opaca':''}" data-priv="${s.privado?1:0}">
      <div class="lado izq"><span class="etq">qué lee</span>${chipsES(es.entradas)}</div><div class="conector${nE?' on':''}"></div>
      <div class="centro"><b>${s.nombre}${s.ejemplo?' <span class="ej">ejemplo</span>':''}</b><span>${s.descripcion || 'sin descripción'}</span>${es.herramientas.length?`<span class="herr">usa: ${es.herramientas.join(", ")}</span>`:''}<span class="cnt">${es.opaca ? 'caja opaca: no declara qué lee ni qué produce' : nE + ' entrada' + (nE===1?'':'s') + ' y ' + nS + ' salida' + (nS===1?'':'s') + ' con base en el texto'}</span></div>
      <div class="conector${nS?' on':''}"></div><div class="lado der"><span class="etq">qué produce · dónde</span>${chipsES(es.salidas)}</div>
      ${o.size ? `<div class="usa">llama a: <b>${[...o].sort().join("</b>, <b>")}</b></div>` : ''}</div>`; }).join("") || `<p class="d">Nada que coincida.</p>`;
}
$("#q-rel").addEventListener("input", pintarRel); pintarRel();
$("#cal").innerHTML = (D.tareas.map(t => `<div class="nodo"><b>${t.cuando}</b><div class="d">${t.fuente}</div><div class="n">${t.que}</div></div>`).join("") || `<div class="hueco"><b>Nada programado</b>Ninguna skill corre sola en esta máquina. Todo lo que hacen tus agentes empieza cuando tú lo pides.</div>`)
  + D.dicen.map(x => `<div class="nodo huerfana"><b>${x.skill}</b><div class="d">dice «${x.dice}», pero nadie la lanza</div></div>`).join("");
// Los territorios del Cerebro Digital (7 notas tipo + la máquina), con el nombre que se enseña y para qué sirve cada uno.
const TERR = [["000","Mantenimiento","La máquina que mantiene el sistema: vigilar, archivar, limpiar, avisar. No es contenido de tu cerebro; es lo que lo mantiene vivo."],
 ["001","Recursos externos","Todo lo que capturas de fuera antes de procesarlo: artículos, vídeos, libros, ideas, notas de voz, lo que te mandan. Responde a «¿dónde lo dejo? ¿dónde estaba aquello?»."],
 ["010","Visión","Hacia dónde vas y por qué: visión, objetivos, lo que quieres que pase. Responde a «¿por qué hago esto? ¿para qué?»."],
 ["020","Proyectos","La ejecución: proyectos, tareas, lo que estás haciendo ahora. Responde a «¿cómo lo hago? ¿qué toca hoy?»."],
 ["050","Activos","Lo que construyes y te queda: el negocio, el canal, los productos, la casa, las herramientas. Responde a «¿con qué cuento? ¿qué tengo montado?»."],
 ["200","Conocimiento","Lo que sabes, ya procesado y enlazado: tus notas de conocimiento por temas. Responde a «¿qué sé sobre esto? ¿qué aprendí?»."],
 ["400","Sabiduría","Tus modelos mentales, principios y criterios: cómo decides. Responde a «¿quién soy? ¿cómo pienso? ¿con qué criterio?»."],
 ["900","Tiempo","Cómo empleas el tiempo: el diario, los cierres del día, lo que pasó y cuándo. Responde a «¿cuándo fue? ¿qué hice ese día?»."]];
function terrDe(sirve){ const v = String(sirve || "").trim(); if (!v) return null; if (v.toLowerCase() === "mantenimiento") return "000"; const m = v.match(/^(\d{3})/); if (m) return m[1] === "011" ? "020" : m[1]; return "050"; }
function nombreTerr(n){ const t = TERR.find(x => x[0] === n); return t ? t[1] : n; }
let fDest = "todos";
function tarjetaFlujo(f, fantasma){
  const cls = f.estado === "funcionando" ? "ok" : "est-av";
  const inf = f.estado === "inferido";
  const pasos = (f.director ? [`<div class="paso dir"><b>${f.director}</b><span>director: reparte, espera, junta</span></div><div class="fl">→</div>`] : [])
    .concat(f.pasos.map((p, i) => `${i ? '<div class="fl">→</div>' : ''}<div class="paso${p.falta ? ' falta' : ''}"><b>${p.perfil}${p.falta ? ' (por construir)' : ''}</b>${p.nota ? `<span>${p.nota}</span>` : ''}</div>`));
  return `<article class="flujo t${terrDe(f.sirve_a) || '000'}${fantasma ? ' fantasma' : ''}${inf ? ' inferido' : ''}" data-dest="${terrDe(f.sirve_a) || ''}" data-nombre="${escT(f.nombre)}"><h4>${f.nombre}${(f.pasos || []).some(p => (D.skills.find(s => s.nombre === p.perfil) || {}).ejemplo) ? ' <span class="ej">ejemplo</span>' : ''}</h4><p class="desc">${f.resumen || ''}</p>
    <div class="meta"><span class="${cls}">${f.estado || 'sin estado'}</span>${f.programada ? `<span>programada: ${f.programada}</span>` : '<span>lo lanzas tú</span>'}<span>${f.pasos.length} ${f.pasos.length === 1 ? 'paso' : 'pasos'}</span>${f.sirve_a ? `<span title="${(TERR.find(x=>x[0]===terrDe(f.sirve_a))||[])[2]||''}">entrega a ${nombreTerr(terrDe(f.sirve_a))}${terrDe(f.sirve_a)==='050' && f.sirve_a.toLowerCase()!=='mantenimiento' ? ' · ' + f.sirve_a : ''}</span>` : ''}</div>
    <div class="cadena">${pasos.join("")}</div></article>`;
}
/* Calendario: clon del mapa de arquitectura del autor. Reales en color; virtuales en gris discontinuo. */
const PALETA = ["#B4642E","#3D6296","#2F7D4F","#8B3A62","#8A6A1F","#2C7A75","#6B4E96","#4E6B73"];
const colorDe = (() => { const m = {}; let i = 0; return n => (n in m ? m[n] : (m[n] = PALETA[i++ % PALETA.length])); })();
const DIAS = {"lunes":1,"martes":2,"miércoles":3,"jueves":4,"viernes":5,"sábado":6,"domingo":0};
const PROGS = D.tareas.filter(t => t.cada && t.cada !== "otro").map(t => ({nombre: t.nombre || t.que.slice(0, 30), cada: t.cada, dia: t.dia, hora: t.hora, quien: t.fuente, que: t.que, virtual: false, declarada: false}))
  .concat(D.dicen.filter(x => x.cada && x.cada !== "otro").map(x => ({nombre: x.skill, cada: x.cada, dia: x.dia, hora: x.hora, quien: "declarada en la skill", ej: !!(D.skills.find(s => s.nombre === x.skill) || {}).ejemplo, que: `La skill dice «${x.dice}»${x.hora ? '' : ' (sin hora: se pinta al final del día)'}; nadie la lanza desde cron o launchd, que se sepa. ` + (x.que || ''), virtual: false, declarada: true})))
  .concat(D.ejemplos_cron.filter(e => !D.tareas.some(t => (t.nombre||"").includes(e.nombre)) && !D.dicen.some(x => x.skill === e.nombre || x.skill === e.quien)).map(e => ({...e, virtual: true, declarada: false})));
PROGS.forEach(p => colorDe(p.virtual ? "ejemplo" : p.quien));
let calAno, calMes;
const hoyStr = (() => { const d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); })();
const fechaStr = (a, m, d) => a + "-" + String(m + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
function tocaEse(p, a, m, d){ if (p.cada === "dia") return true; const dow = new Date(a, m, d).getDay(); if (p.cada === "semana") return DIAS[p.dia] === dow; if (p.cada === "mes") return String(d) === String(parseInt(p.dia, 10)); return false; }
const DIAS_NOMBRE = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 0: "domingo"};
let calDiaSel = null;

function pintarTimelineDia(a, m, d){
  const fStr = fechaStr(a, m, d);
  const fechaObj = new Date(a, m, d);
  const diaSemana = DIAS_NOMBRE[fechaObj.getDay()];
  const mesNombre = fechaObj.toLocaleDateString("es-ES", {month: "long"});
  
  const elTit = $("#cal-timeline-titulo");
  const elSub = $("#cal-timeline-sub");
  if (elTit) elTit.textContent = `Agenda para el ${diaSemana} ${d} de ${mesNombre}`;
  if (elSub) elSub.textContent = (fStr === hoyStr ? "● Jornada de Hoy (vigilancia en tiempo real)" : `Programación para la fecha ${fStr}`);
  
  const evs = [];
  PROGS.forEach(p => {
    if (tocaEse(p, a, m, d)) evs.push(p);
  });
  evs.sort((x, y) => (x.hora || "99:99").localeCompare(y.hora || "99:99"));

  const kbEvs = [];
  if (D.kanban) {
    const todasTarjetas = [
      ...(D.kanban.pendientes || []).map(t => ({...t, col: "pendientes"})),
      ...(D.kanban.en_progreso || []).map(t => ({...t, col: "en_progreso"})),
      ...(D.kanban.hecho || []).map(t => ({...t, col: "hecho"})),
      ...(D.kanban.archivado || []).map(t => ({...t, col: "archivado"}))
    ];
    todasTarjetas.forEach(t => {
      if (t.fecha_creacion && t.fecha_creacion.startsWith(fStr)) {
        kbEvs.push({
          hora: "Creada",
          nombre: t.title,
          cadencia: "Kanban",
          que: `Tarea Kanban creada para el agente ${t.agent || 'general'}${t.skill ? ' (Skill: ' + t.skill + ')' : ''}`,
          quien: "Kanban (Creada)",
          color: "var(--acento)"
        });
      }
      if (t.fecha_finalizacion && t.fecha_finalizacion.startsWith(fStr)) {
        kbEvs.push({
          hora: "Finalizada",
          nombre: t.title,
          cadencia: "Kanban",
          que: `Tarea Kanban finalizada y marcada como hecha por ${t.agent || 'general'}`,
          quien: "Kanban (Hecho)",
          color: "var(--ok)"
        });
      }
    });
  }
  
  const listaEl = $("#cal-timeline-lista");
  if (!listaEl) return;
  if (!evs.length && !kbEvs.length) {
    listaEl.innerHTML = `<div class="cal-tl-vacio">No hay agentes programados ni actividad de Kanban registrada para este día.</div>`;
    return;
  }
  const progHtml = evs.map(p => {
    const horaTxt = p.intervalo ? `${p.hora} (cada ${p.intervalo})` : (p.hora || "Horario flexible");
    const esIntradia = Boolean(p.intervalo);
    const c = colorDe(p.quien);
    return `<div class="cal-tl-item" style="border-left: 3px solid ${c};">
      <div class="cal-tl-time">${escT(horaTxt)}</div>
      <div class="cal-tl-info">
        <div class="cal-tl-name">
          <span>${escT(p.nombre)}</span>
          <span class="cal-tl-cadencia">${p.cada === 'semana' ? 'Semanal' : (esIntradia ? 'Intradía (repetitivo)' : 'Diario')}</span>
        </div>
        <div class="cal-tl-desc">${escT(p.que)}</div>
      </div>
      <div class="cal-tl-source">${escT(p.quien)}</div>
    </div>`;
  }).join("");

  const kbHtml = kbEvs.map(k => `
    <div class="cal-tl-item" style="border-left: 3px solid ${k.color};background:color-mix(in srgb, ${k.color} 4%, var(--fondo));">
      <div class="cal-tl-time" style="color:${k.color}">${escT(k.hora)}</div>
      <div class="cal-tl-info">
        <div class="cal-tl-name">
          <span>${escT(k.nombre)}</span>
          <span class="cal-tl-cadencia" style="border-color:${k.color};color:${k.color};font-weight:600">${escT(k.cadencia)}</span>
        </div>
        <div class="cal-tl-desc">${escT(k.que)}</div>
      </div>
      <div class="cal-tl-source" style="color:${k.color};font-weight:600">${escT(k.quien)}</div>
    </div>
  `).join("");

  listaEl.innerHTML = progHtml + kbHtml;
}

/* Las tres cajas de arriba: todo lo programado junto, por cadencia. */
function pintarResumenCal(){
  const caja = $("#cal-resumen"); if (!caja || caja.dataset.ok) return; caja.dataset.ok = "1";
  const cuando = p => p.cada === "semana" ? (p.dia ? "cada " + p.dia : "cada semana") : p.cada === "mes" ? (p.dia ? "el día " + p.dia : "cada mes") : (p.intervalo ? "cada " + p.intervalo : "cada día");
  const fila = p => `<li class="${p.virtual ? "virtual" : ""}" data-globo="${escT((p.hora || "??:??") + " · " + p.nombre + " · " + p.quien + "\n" + (p.que || ""))}" tabindex="0"><span class="h">${escT(p.hora || "—")}</span><span class="n">${escT(p.nombre)}${p.cada !== "dia" || p.intervalo ? ` <span class="q">${escT(cuando(p))}</span>` : ""}${(p.virtual || p.ej) ? '<span class="ej">ejemplo</span>' : ""}</span></li>`;
  const grupo = (et, cada) => { const xs = PROGS.filter(p => p.cada === cada).sort((x, y) => (x.virtual - y.virtual) || (x.hora || "99").localeCompare(y.hora || "99"));
    return `<div class="cal-caja"><h4><b>${xs.filter(x => !x.virtual).length}</b>${et}</h4>${xs.length ? `<ul>${xs.map(fila).join("")}</ul>` : `<p class="nada">ninguna</p>`}</div>`; };
  caja.innerHTML = grupo("diarias / intradía", "dia") + grupo("semanales", "semana") + grupo("mensuales", "mes");
}

function pintarCalendario(){
  pintarResumenCal();
  if (calAno === undefined) { const d = new Date(); calAno = d.getFullYear(); calMes = d.getMonth(); }
  $("#cal-mes").textContent = new Date(calAno, calMes, 1).toLocaleDateString("es-ES", {month: "long", year: "numeric"});
  const desplaz = (new Date(calAno, calMes, 1).getDay() + 6) % 7, nDias = new Date(calAno, calMes + 1, 0).getDate(), celdas = [];
  for (let i = 0; i < desplaz; i++) celdas.push('<div class="cal-dia fuera" aria-hidden="true"></div>');
  for (let d = 1; d <= nDias; d++) {
    const f = fechaStr(calAno, calMes, d), puntos = [];
    PROGS.forEach(p => { if (!tocaEse(p, calAno, calMes, d)) return;
      const c = colorDe(p.quien);
      const horaStr = p.intervalo ? `${p.hora} (${p.intervalo})` : (p.hora || '');
      const tip = (p.hora || "??:??") + " · " + p.nombre + " → " + p.quien + (p.intervalo ? ` (cada ${p.intervalo})` : '') + "\n" + (p.que ? p.que : "tarea programada en esta máquina");
      puntos.push({hora: p.hora || "99:99", html: `<span class="arranque"><span class="punto${p.declarada ? ' declarada' : ''}" style="--c:${c}" tabindex="0" role="button" aria-label="${escT(tip)}" data-globo="${escT(tip)}"></span><span class="hora">${horaStr}</span></span>`}); });
    puntos.sort((x, y) => x.hora.localeCompare(y.hora));
    const esHoy = (f === hoyStr);
    const esSel = calDiaSel ? (calDiaSel.a === calAno && calDiaSel.m === calMes && calDiaSel.d === d) : esHoy;
    celdas.push(`<div class="cal-dia${esHoy ? " hoy" : ""}${esSel ? " seleccionado" : ""}" data-dia="${d}"><span class="num">${d}</span><div class="cal-puntos">${puntos.map(x => x.html).join("")}</div></div>`);
  }
  $("#cal-rejilla").innerHTML = celdas.join("");

  $("#cal-rejilla").querySelectorAll(".cal-dia:not(.fuera)").forEach(el => {
    el.addEventListener("click", () => {
      const d = parseInt(el.dataset.dia, 10);
      calDiaSel = {a: calAno, m: calMes, d: d};
      $("#cal-rejilla").querySelectorAll(".cal-dia").forEach(x => x.classList.remove("seleccionado"));
      el.classList.add("seleccionado");
      pintarTimelineDia(calAno, calMes, d);
    });
  });

  const hoyD = new Date().getDate();
  const diaInicial = (calAno === new Date().getFullYear() && calMes === new Date().getMonth()) ? hoyD : 1;
  calDiaSel = {a: calAno, m: calMes, d: diaInicial};
  pintarTimelineDia(calAno, calMes, diaInicial);

  const realesP = PROGS.filter(p => !p.virtual);
  const porQuien = {}; realesP.forEach(p => { (porQuien[p.quien] = porQuien[p.quien] || []).push(p); });
  $("#cal-leyenda").innerHTML = Object.keys(porQuien).sort().map(q => `<span><i class="punto" style="--c:${colorDe(q)}"></i>${q} <small>· ${porQuien[q].map(p => p.nombre).join(", ")}</small></span>`).join("")
    + (realesP.some(p => p.declarada) ? `<span><i class="punto declarada" style="--c:${colorDe("declarada en la skill")}"></i>declarada dentro de la skill (nadie la lanza)</span>` : "");
  const av = $("#aviso-virtual"); if (av) av.hidden = true;
}
$("#cal-prev").addEventListener("click", () => { calMes--; if (calMes < 0) { calMes = 11; calAno--; } pintarCalendario(); });
$("#cal-next").addEventListener("click", () => { calMes++; if (calMes > 11) { calMes = 0; calAno++; } pintarCalendario(); });
$("#cal-hoy").addEventListener("click", () => { calAno = undefined; pintarCalendario(); });
pintarCalendario();
{ const globo = $("#globo");
  const mostrar = el => { const txt = el.dataset.globo; if (!txt) return; const ln = txt.split("\n");
    globo.innerHTML = `<b>${escT(ln[0])}</b>` + (ln.length > 1 ? "\n" + ln.slice(1).map(escT).join("\n") : ""); globo.classList.add("visible");
    const r = el.getBoundingClientRect(), g = globo.getBoundingClientRect(); let x = Math.max(8, Math.min(r.left + r.width / 2 - g.width / 2, window.innerWidth - g.width - 8)); let y = r.top - g.height - 10, abajo = false; if (y < 8) { y = r.bottom + 10; abajo = true; }
    globo.style.left = x + "px"; globo.style.top = y + "px"; globo.style.setProperty("--flecha", (r.left + r.width / 2 - x) + "px"); globo.classList.toggle("abajo", abajo); };
  const ocultar = () => globo.classList.remove("visible");
  document.addEventListener("mouseover", e => { const el = e.target.closest("[data-globo]"); if (el) mostrar(el); });
  document.addEventListener("mouseout", e => { if (e.target.closest("[data-globo]")) ocultar(); });
  document.addEventListener("focusin", e => { const el = e.target.closest("[data-globo]"); if (el) mostrar(el); });
  document.addEventListener("focusout", e => { if (e.target.closest("[data-globo]")) ocultar(); });
  window.addEventListener("scroll", ocultar, {passive: true}); }
// La figura del flujo de ejemplo se dibuja a partir de D.flujo_ejemplo (datos dummy
// del script): quien quiera otra figura cambia los datos, no el HTML.
function figuraFlujo(F){
  const ET = {ext: "lee de fuera", her: "hereda del paso anterior", cd: "lee de tu cerebro"};
  const caja = (cls, et, txt) => `<div class="caja ${cls}"><span class="et">${et}</span>${escT(txt)}</div>`;
  const paso = (p, i) => `<div class="paso"><span class="num">${i + 1}</span><header><span class="nom">${escT(p.perfil)}</span><span class="chapa obr">obrero</span></header><span class="sk">${escT(p.skill)}</span>${(p.lee || []).map(([c, t]) => caja(c, ET[c] || c, t)).join("")}<div class="hace">${escT(p.hace)}</div>${caja("deja", "deja en", p.deja)}</div>`;
  return `<div class="fig">
  <div class="fig-cab"><h3><span class="ej">ejemplo</span> Un flujo de agentes atómicos: «${escT(F.nombre)}»</h3><span class="cuando">⚡ programada <b>${escT(F.cuando)}</b> · ${F.pasos.length} obreros en cadena · ${escT(F.duracion)}</span></div>
  <div class="centro"><div class="director"><span class="chapa dir">director</span><div><div class="nom">${escT(F.director.nombre)}</div><div class="que">${escT(F.director.que)}</div></div></div></div>
  <div class="baja">una tarjeta por paso, en orden; cada obrero lee lo que dejó el anterior</div>
  <div class="pasos">${F.pasos.map(paso).join("")}</div>
  <div class="leyenda"><span><i class="dir"></i>perfil director — encadena, no trabaja</span><span><i class="obr"></i>perfil obrero — trabaja y cierra</span><span><i></i>lee de tu cerebro digital</span><span><i class="her"></i>hereda del paso anterior</span><span><i class="ext"></i>fuente externa</span><span><i class="deja"></i>lo que deja (y lee el siguiente)</span></div>
</div>`;
}
const p = D.sistema;
const reales = D.flujos && D.flujos.length;
const inferidos = D.inferidos || [];
const lista = reales ? D.flujos : D.ejemplos;   // los inferidos tienen su propia pestaña («Flujos trabajo skills»)
let fEst = null;
const ESTADOS_FL = [
  ["construido", "construidos", "Todos sus pasos existen: se puede lanzar hoy", f => f.estado === "funcionando" || f.estado === "sin probar"],
  ["pendiente", "pendientes", "Enunciados, pero les falta al menos una pieza por construir", f => f.estado === "falta una pieza" || f.estado === "en construccion" || (f.pasos||[]).some(p => p.falta)],
];
function cuentaDest(n){ return lista.filter(f => (n === "todos" || terrDe(f.sirve_a) === n) && (!fEst || ESTADOS_FL.find(e => e[0] === fEst)[3](f))).length; }
function botonesDestino(){
  return `<div class="cifras-fl" id="cifras-fl"><span class="etq">Flujos de trabajo</span><button type="button" class="cifra-fl total" data-k="" aria-pressed="${!fEst}" title="Quitar el filtro de estado"><b>${lista.length}</b>${lista.length === 1 ? "flujo en total" : "flujos en total"}</button>` +
    ESTADOS_FL.map(([k, et, ti, f]) => `<button type="button" class="cifra-fl" data-k="${k}" aria-pressed="${fEst===k}" title="${ti}"><b>${lista.filter(f).length}</b>${et}</button>`).join("") + `</div>` +
    `<div class="destinos" id="destinos"><span class="etq">Destino</span><button type="button" data-d="todos" aria-pressed="${fDest==='todos'}">Todos<span>${cuentaDest("todos")}</span></button>` +
    TERR.filter(t => t[0] !== "000").concat(TERR.filter(t => t[0] === "000")).map(t => `<button type="button" class="terr t${t[0]}" data-d="${t[0]}" title="${t[2]}" aria-pressed="${fDest===t[0]}">${t[1]}<span>${cuentaDest(t[0])}</span></button>`).join("") + `</div>`;
}
function aplicarFlujos(){
  document.querySelectorAll("#lista-flujos .flujo, .lista-inf .flujo").forEach(a => { const f = lista.find(x => x.nombre === a.dataset.nombre) || {}; a.hidden = (fDest !== "todos" && a.dataset.dest !== fDest) || (fEst && !ESTADOS_FL.find(e => e[0] === fEst)[3](f)); });
  document.querySelectorAll("#destinos button").forEach(x => { x.setAttribute("aria-pressed", x.dataset.d === fDest); x.querySelector("span").textContent = cuentaDest(x.dataset.d); });
  document.querySelectorAll("#cifras-fl .cifra-fl").forEach(x => x.setAttribute("aria-pressed", (x.dataset.k || null) === fEst));
}
const elSkCad = $("#sk-cadenas-lista");
if (elSkCad) {
  elSkCad.innerHTML = inferidos.length
    ? inferidos.map(f => tarjetaFlujo(f, false)).join("")
    : `<div class="kb-vacio">No se han detectado cadenas inferidas entre las skills actuales.</div>`;
}
if ($("#cnt-sk-inf")) $("#cnt-sk-inf").textContent = inferidos.length;

function pintarAgentes() {
  const agGrid = $("#ag-grid");
  const pipeLista = $("#pipe-lista");
  if (!agGrid) return;
  const agentes = D.agentes_reales || [];
  if (!agentes.length) {
    agGrid.innerHTML = `<div class="kb-vacio">No se encontraron agentes en <code>.claude/agents/*.md</code>.</div>`;
  } else {
    agGrid.innerHTML = agentes.map(a => {
      const toolsHtml = (a.tools && a.tools.length) ? a.tools.map(t => `<span class="ag-tool-tag">${escT(t)}</span>`).join("") : '<span class="d">Sin herramientas especiales</span>';
      return `
        <div class="ag-card">
          <div class="ag-card-header">
            <span class="ag-card-title">🤖 ${escT(a.name)}</span>
            <span class="ag-model">${escT(a.model)}</span>
          </div>
          <div class="ag-cadence">⚡ ${escT(a.cadencia)}</div>
          <p class="ag-desc">${escT(a.description || a.rol)}</p>
          <div>
            <div style="font:600 .7rem var(--mono);color:var(--gris);margin-bottom:4px;text-transform:uppercase;">Herramientas permitidas</div>
            <div class="ag-tools">${toolsHtml}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  if (pipeLista) {
    const pipelines = D.pipelines_kanban || [];
    if (!pipelines.length) {
      pipeLista.innerHTML = `<div class="kb-vacio">No hay tarjetas Kanban con pipeline multi-paso actualmente. Para declarar una, incluye <code>pipeline: [paso1, paso2]</code> en el frontmatter de una tarjeta.</div>`;
    } else {
      pipeLista.innerHTML = pipelines.map(p => {
        const stepsHtml = (p.pipeline || []).map((step, idx) => `
          ${idx > 0 ? '<span class="pipe-arrow">→</span>' : ''}
          <span class="pipe-step">${idx + 1}. ${escT(step)}</span>
        `).join("");
        return `
          <div class="pipe-card">
            <div class="pipe-header">
              <span class="pipe-title">⛓️ ${escT(p.title)}</span>
              <span class="tag">Estado: ${escT(p.estado)}</span>
            </div>
            <div style="font:.78rem var(--mono);color:var(--gris);margin-bottom:6px;">Archivo: <code>${escT(p.archivo)}</code> · Agente: ${escT(p.agent)}</div>
            <div class="pipe-steps">${stepsHtml}</div>
          </div>
        `;
      }).join("");
    }
  }
}
pintarAgentes();

/* ── Actores: el plano de lo que hay alrededor de tus agentes ─────────── */
{
  const A = D.actores || {}, esc = escT;
  const capas = $("#plano-capas"), svg = $("#plano-hilos"), plano = $("#plano");
  const chip = (t, cls = "", g = "") => `<li class="${cls}"${g ? ` data-globo="${esc(g)}" tabindex="0"` : ""}>${t}</li>`;
  const nodo = (id, cls, titulo, sub, chapa, cuerpo, span = 3) => `<article class="actor ${cls}" id="ac-${id}" style="grid-column:span ${span}"><header><h4>${titulo}${sub ? `<small>${sub}</small>` : ""}</h4>${chapa || ""}</header>${cuerpo}</article>`;
  const CH = {res: '<span class="chapa-act res">residente</span>', rel: '<span class="chapa-act reloj">reloj</span>', efi: '<span class="chapa-act efi">efímero</span>', conv: '<span class="chapa-act conv">conversa</span>', falta: '<span class="chapa-act falta">falta</span>'};
  const AR = A.arneses || [], CA = A.canales || [], NT = A.notas || [], TF = A.tareas_por_fuente || {};
  const nTareas = Object.values(TF).reduce((a, b) => a + b, 0);
  const capa = (et, html) => `<div class="capa"><span class="capa-et">${et}</span>${html}</div>`;
  // Quien manda: tú, y el reloj si algo corre solo.
  const tu = nodo("tu", "persona", "Tú", "quien manda: pides, revisas, decides", "", `<ul class="dato">${chip("⌨ terminal")}${CA.map(c => chip(esc(c.nombre), "", c.via)).join("")}</ul>`, nTareas ? 7 : 12);
  const reloj = nTareas ? nodo("reloj", "persona", "Lo programado", `${nTareas} ${nTareas === 1 ? "tarea" : "tareas"} · ${Object.entries(TF).map(([k, v]) => `${k} ${v}`).join(" · ")}`, CH.rel, `<ul class="dato">${(D.tareas || []).slice(0, 8).map(t => chip(`${esc(t.nombre)}${t.hora ? " · " + esc(t.hora) : ""}`, "", `${t.fuente}: ${t.cuando}\n${t.que}`)).join("")}${(D.tareas || []).length > 8 ? chip(`+${D.tareas.length - 8} más (pestaña Calendario)`) : ""}</ul>`, 5) : "";
  // Conversan: un agente continuo por herramienta encontrada.
  const spanAr = AR.length ? Math.max(3, Math.floor(12 / AR.length)) : 12;
  const continuos = AR.length ? AR.map(a => nodo("arnes-" + a.binario, "continuo", esc(a.nombre), `${a.instalado ? "instalado" : "config sin binario"}${a.memoria.length ? " · " + a.memoria.map(esc).join(", ") : ""}`, CH.conv,
    `<ul class="dato">${chip(`<b>${a.skills}</b> skills`, "", "Skills de esta herramienta encontradas en esta máquina (pestaña Skills).")}${a.agentes ? chip(`<b>${a.agentes}</b> agentes`, "", "Perfiles o subagentes: piezas que pueden trabajar por tarjeta, no solo en conversación.") : ""}${a.memoria.length ? chip("instrucciones propias", "ok", "Tiene un fichero de instrucciones (" + a.memoria.join(", ") + "): sabe cómo trabajas antes de que se lo digas.") : chip("sin fichero de instrucciones", "no", "Ningún " + (a.binario === "claude" ? "CLAUDE.md" : a.binario === "gemini" ? "GEMINI.md" : "AGENTS.md") + " encontrado: cada sesión empieza de cero.")}${a.binario === "claude" && A.mcp ? chip(`<b>${A.mcp}</b> MCP`, "", "Servidores MCP declarados: herramientas externas conectadas al agente.") : ""}</ul>`, spanAr)).join("")
    : nodo("arnes-ninguno", "continuo falta", "Ningún agente encontrado", "ni Claude Code, ni Codex, ni Gemini CLI, ni Hermes", CH.falta, `<p>No hay ningún binario ni carpeta de configuración de un agente de terminal. Todo lo que hagas con IA hoy pasa por una web y no deja rastro aquí.</p>`, 12);
  // El tablero y el reparto: si hay sistema de agentes atómicos, se dibuja; si no, la caja gris dice qué falta.
  const tablero = A.tablero ? nodo("tablero", "tablero", "El tablero", "tarjetas: pendientes → en curso → hechas" + (A.programadas ? " · programadas ⚡" : ""), "", `<p>Cada encargo es una tarjeta; el que la atiende deja Registro. Es lo único que pasa de un agente a otro.</p>`, 12)
    : nodo("tablero", "tablero falta", "Sin tablero", "todo se pide y se revisa en la conversación", CH.falta, `<p>No hay tarjetas ni columnas: lo que pides vive en el chat y se borra con él. Un tablero es lo que permite que un agente trabaje sin que estés delante y que otro lo revise después.</p>`, 12);
  const lanzador = A.lanzador ? nodo("lanzador", "base", "El lanzador", "reparte las tarjetas", CH.res, `<p>Un proceso residente mira el tablero, elige quién atiende cada tarjeta y levanta al obrero.</p>`, 4)
    : nodo("lanzador", "base falta", "Sin lanzador", "nadie reparte", CH.falta, `<p>Sin lanzador, nada arranca solo: eres tú el que abre la sesión y pide. Es la pieza que convierte tareas programadas en trabajo hecho.</p>`, 4);
  const obreros = A.agentes ? nodo("obreros", "base", "Obreros", `${A.agentes} ${A.agentes === 1 ? "perfil" : "perfiles"} · uno por tarjeta`, CH.efi, `<p>Agentes que nacen con un perfil y una tarjeta, hacen lo que dice el perfil y mueren. Sin conversación.</p>`, 4)
    : nodo("obreros", "base falta", "Sin obreros", "solo el agente que conversa", CH.falta, `<p>No hay perfiles ni subagentes: el único que trabaja es el que habla contigo, y solo mientras hablas.</p>`, 4);
  const vigilante = A.vigilante ? nodo("vigilante", "base", "El vigilante", "mira que todo siga vivo", CH.res, `<p>Un proceso independiente comprueba que el agente y el lanzador siguen vivos, y avisa si no.</p>`, 4)
    : nodo("vigilante", "base falta", "Sin vigilante", "nadie avisa si algo se rompe", CH.falta, `<p>Cuando un agente se cuelga o una programada deja de salir, te enteras cuando lo echas de menos.</p>`, 4);
  const planificador = nTareas ? nodo("planificador", "base", "Planificador del sistema", Object.keys(TF).map(esc).join(" · "), "", `<p>Lo único que late fuera del agente: dispara los relojes y resucita a los residentes.</p><ul class="dato">${Object.entries(TF).map(([k, v]) => chip(`<b>${v}</b> ${esc(k)}`)).join("")}</ul>`, 4)
    : nodo("planificador", "base falta", "Nada corre solo", "ni cron, ni launchd, ni tareas programadas", CH.falta, `<p>No hay ninguna tarea del sistema operativo que llame a tus agentes. Sin esto, trabajan solo mientras tecleas.</p>`, 4);
  const hooks = (A.hooks || A.hooks_sh) ? nodo("hooks", "base", "Candados · hooks", `${A.hooks} en settings${A.hooks_sh ? ` · ${A.hooks_sh} scripts` : ""}`, "", `<p>Interceptan cada herramienta del agente antes de ejecutarse: lo que no debe leer, borrar o publicar, no lo hace.</p>`, 4)
    : nodo("hooks", "base falta", "Sin candados", "ningún hook configurado", CH.falta, `<p>El agente puede leer y escribir cualquier cosa a la que llegue: claves, notas privadas, ficheros que no debe tocar. Un hook es un «no» que no depende de que el modelo se acuerde.</p>`, 4);
  // La ventana de contexto del agente con el que hablas: lo que carga al arrancar
  // (sus ficheros de instrucciones, medidos) y lo que le pasa cuando se llena.
  const palIns = AR.reduce((n, a) => n + (a.memoria_palabras || 0), 0);
  const contexto = nodo("contexto", "contexto", "Ventana de contexto", "la memoria de trabajo del agente con el que hablas · se carga al arrancar, se llena con el día y se compacta", "",
    `<ul class="dato">${AR.length ? chip(`<b>${palIns.toLocaleString("es-ES")}</b> palabras de instrucciones al arrancar`, palIns ? "" : "no", palIns ? "Lo que tus ficheros de instrucciones (CLAUDE.md, AGENTS.md, GEMINI.md, SOUL.md…) cargan en cada arranque, antes de que digas nada." : "Ningún fichero de instrucciones: cada sesión empieza de cero y todo lo que sabe de ti se lo tienes que contar cada vez.") : chip("sin agente, sin ventana", "no")}${chip("cuando se llena, se compacta", "no", "El agente resume lo de atrás para hacer sitio a lo de delante: las instrucciones concretas se convierten en una frase que ya no manda nada. Por eso los flujos que viven dentro de la conversación se degradan.")}${chip("un agente atómico nace con la suya", "", "Pequeña y limpia: un perfil y una tarjeta. Por eso hace lo mismo dentro de tres meses.")}</ul>`, 12);
  // Las ocho dimensiones del vault Sistema Maestro (00 Sistema a 99 Archivo)
  const NOTAS_TIPO = [
    ["00", "00 Sistema"],
    ["01", "01 Index"],
    ["02", "02 MOCs"],
    ["03", "03 Proyectos"],
    ["04", "04 Knowledge"],
    ["05", "05 Diario"],
    ["06", "06 Raw"],
    ["99", "99 Archivo"]
  ];
  const tieneNT = Object.fromEntries(NT.map(t => [t.num, t]));
  const suelo = nodo("suelo", "vault", "Tu carpeta · Sistema Maestro", esc(A.carpeta || "") + " · donde todos escriben y ninguno manda", "",
    `<ul class="dato">${NOTAS_TIPO.map(([n, nom]) => tieneNT[n] ? chip(esc(nom), `terr t${n}`, `${tieneNT[n].carpeta}: existe en tu carpeta.`) : chip(esc(nom), `terr t${n} falta-nt`, `No hay carpeta «${n} …» en tu carpeta.`)).join("")}${(A.sistema_dirs || []).map(d => chip(`<b>${esc(d)}</b> agentes`, "", "Carpeta del sistema de agentes: skills, perfiles, tablero, hooks.")).join("")}${chip(`<b>${A.skills}</b> skills · <b>${A.agentes}</b> agentes tuyos en esta carpeta`, "", "Lo que el rastreo encontró dentro de la carpeta (pestaña Skills).")}${!NT.length ? chip("ninguna de las carpetas estándar todavía", "no", "No hay carpetas de las 8 dimensiones del vault: el agente trabaja sobre una carpeta sin estructura.") : ""}</ul>`, 12);
  capas.innerHTML = capa("quien manda", tu + reloj) + capa("conversan", continuos) + capa("el tablero", tablero) + capa("el reparto", vigilante + lanzador + obreros) + capa("la base", hooks + planificador + nodo("nota", "base", "Lo que no se mira", "por diseño", "", `<p>Este mapa no lee claves, ni mensajes, ni el contenido de tus notas: solo qué ficheros y binarios existen.</p>`, 4)) + capa("la memoria de trabajo", contexto) + capa("el suelo", suelo);
  const primer = AR.length ? "arnes-" + AR[0].binario : "arnes-ninguno";
  const HILOS = [["tu", primer, "conversación"], ...(nTareas ? [["reloj", "tablero", A.tablero ? "materializa" : "", "", "der", 20]] : []),
    [primer, "tablero", A.tablero ? "deja tarjetas" : "", A.tablero ? "" : "falta"], ["tablero", "lanzador", A.lanzador ? "reclama · despacha" : "", A.lanzador ? "" : "falta"],
    ["lanzador", "obreros", A.agentes ? "levanta" : "", A.agentes ? "" : "falta"], ["obreros", "tablero", A.agentes && A.tablero ? "cierran" : "", A.agentes && A.tablero ? "" : "falta"],
    ["planificador", "lanzador", nTareas ? "KeepAlive" : "", "vig"], ["vigilante", primer, A.vigilante ? "levanta la sesión" : "", "vig", "izq", 20],
    ["hooks", primer, (A.hooks || A.hooks_sh) ? "candado" : "", "candado", "izq", 40], ["obreros", "suelo", A.agentes ? "escriben" : "", "", "der", 40], [primer, "contexto", "se carga al arrancar", "", "izq", 60], ["contexto", "suelo", "lee y escribe"]];
  function dibujarHilos(){
    if ($("#v-actores").hidden) return;
    const P = plano.getBoundingClientRect(), W = plano.clientWidth, H = plano.clientHeight;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("width", W); svg.setAttribute("height", H);
    const rect = id => { const el = document.getElementById("ac-" + id); if (!el) return null; const r = el.getBoundingClientRect(); return {left: r.left - P.left, right: r.right - P.left, top: r.top - P.top, bottom: r.bottom - P.top, cx: (r.left + r.right) / 2 - P.left, cy: (r.top + r.bottom) / 2 - P.top}; };
    const clamp = (v, a, b) => Math.max(a, Math.min(b, v)), ancla = (r, x) => { const ins = Math.min(60, (r.right - r.left) / 4); return clamp(x, r.left + ins, r.right - ins); };
    const estrecho = matchMedia("(max-width:760px)").matches, mi = parseFloat(getComputedStyle(plano).paddingLeft), md = parseFloat(getComputedStyle(plano).paddingRight);
    let out = `<defs><marker id="fl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="currentColor"/></marker><marker id="fl-c" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#B0473A"/></marker></defs>`;
    const vistosH = {};
    HILOS.forEach(([de, a, rot, cls = "", ruta = "", sep]) => {
      const s = rect(de), t = rect(a); if (!s || !t) return; if (estrecho && ruta) return;
      let d = "", lx = 0, ly = 0, rotar = false, anchor = "middle";
      if (ruta) { const izq = ruta === "izq", X = izq ? mi - sep : W - md + sep, y1 = s.cy, y2 = t.cy, sg = Math.sign(y2 - y1) || 1, x1 = izq ? s.left : s.right, x2 = izq ? t.left : t.right, k = izq ? 8 : -8;
        d = `M${x1} ${y1}L${X + k} ${y1}Q${X} ${y1} ${X} ${y1 + sg * 8}L${X} ${y2 - sg * 8}Q${X} ${y2} ${X + k} ${y2}L${x2} ${y2}`; lx = X; ly = (y1 + y2) / 2; rotar = true; }
      else if (t.top >= s.bottom - 1) { const sx = ancla(s, t.cx), tx = ancla(t, sx), my = (s.bottom + t.top) / 2; d = `M${sx} ${s.bottom}C${sx} ${my} ${tx} ${my} ${tx} ${t.top}`; lx = (sx + tx) / 2 + (sx === tx ? 7 : 0); ly = my + 3; anchor = sx === tx ? "start" : "middle"; }
      else if (s.top >= t.bottom - 1) { const sx = ancla(s, t.cx), tx = ancla(t, sx), my = (s.top + t.bottom) / 2; d = `M${sx} ${s.top}C${sx} ${my} ${tx} ${my} ${tx} ${t.bottom}`; lx = (sx + tx) / 2 + (sx === tx ? 7 : 0); ly = my + 3; anchor = sx === tx ? "start" : "middle"; }
      else { const n = (vistosH[de] = (vistosH[de] || 0) + 1), dy = (n - 1) * 16 - 8, der = t.left >= s.right, x1 = der ? s.right : s.left, x2 = der ? t.left : t.right, y = clamp(s.cy + dy, Math.max(s.top, t.top) + 14, Math.min(s.bottom, t.bottom) - 14), mx = (x1 + x2) / 2; d = `M${x1} ${y}C${mx} ${y} ${mx} ${y} ${x2} ${y}`; lx = mx; ly = y - 4; if (Math.abs(x2 - x1) < 50) rot = ""; }
      const m = cls === "candado" ? "fl-c" : "fl";
      out += `<path d="${d}" class="${cls}" marker-end="url(#${m})"/>`;
      if (rot) out += `<text x="${lx}" y="${ly}" text-anchor="${anchor}" class="${cls}"${rotar ? ` transform="rotate(-90 ${lx} ${ly})" dy="${ruta === "izq" ? -4 : 10}"` : ""}>${esc(rot)}</text>`;
    });
    svg.innerHTML = out;
  }
  let tmr; addEventListener("resize", () => { clearTimeout(tmr); tmr = setTimeout(dibujarHilos, 120); });
  window.dibujarHilos = dibujarHilos; requestAnimationFrame(dibujarHilos);
}
let tarjetaSeleccionada = null;

function verDetalleTarjeta(t, colId) {
  tarjetaSeleccionada = { card: t, colId: colId };
  const modal = $("#modal-view-card");
  if (!modal) return;
  
  $("#vc-title").textContent = t.title || "Detalle de Tarjeta";
  const pr = (t.prioridad||"").toLowerCase();
  const cl = pr.includes("alta") ? "alta" : pr.includes("baja") ? "baja" : "media";
  const cardFile = t.archivo || t.filename || '';
  
  const metaHtml = `
    <span class="tag">🤖 Agente: ${escT(t.agent || 'general')}</span>
    ${t.skill ? `<span class="tag">⚡ Skill: ${escT(t.skill)}</span>` : ''}
    <span class="tag prio-${cl}">${escT(t.prioridad || 'Media')}</span>
    <span class="tag">📄 ${escT(cardFile)}</span>
    ${t.fecha_creacion ? `<span class="tag">📅 Creación: ${escT(t.fecha_creacion)}</span>` : ''}
    ${t.fecha_finalizacion ? `<span class="tag">🏁 Fin: ${escT(t.fecha_finalizacion)}</span>` : ''}
  `;
  $("#vc-meta").innerHTML = metaHtml;
  $("#vc-obj").textContent = t.objetivo || "(Sin objetivo especificado)";
  $("#vc-cuerpo").textContent = t.cuerpo || "(Esta tarjeta no contiene cuerpo markdown adicional)";
  
  document.querySelectorAll(".vc-move-btn").forEach(btn => {
    const isCurrent = (btn.dataset.to === colId);
    btn.disabled = isCurrent;
    btn.classList.toggle("mc-btn-primary", isCurrent);
  });

  const btnDisp = $("#btn-vc-dispatch");
  if (btnDisp) {
    if (colId === "pendientes") {
      btnDisp.hidden = false;
      btnDisp.textContent = "▶ Despachar esta tarea";
      btnDisp.disabled = false;
    } else {
      btnDisp.hidden = true;
    }
  }
  modal.showModal();
}

async function moverTarjeta(toCol) {
  if (!tarjetaSeleccionada || !tarjetaSeleccionada.card) return;
  const cardName = tarjetaSeleccionada.card.archivo || tarjetaSeleccionada.card.filename;
  if (!cardName) return;
  if (!serverOnline) {
    mostrarToast("Iniciá el servidor para mover tarjetas: python .claude/scripts/mapa-agentes.py --serve", "info", 5000);
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/kanban/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card: cardName, card_name: cardName, to_col: toCol })
    });
    const data = await res.json();
    if (data.ok) {
      mostrarToast(`✅ Tarjeta movida a ${toCol}`, "ok", 3000);
      $("#modal-view-card").close();
      if (data.kanban) {
        D.kanban = data.kanban;
        pintarKanban();
      }
    } else {
      mostrarToast(`⚠️ Error: ${data.error || 'No se pudo mover'}`, "error", 5000);
    }
  } catch (e) {
    mostrarToast(`❌ Error: ${e.message}`, "error");
  }
}

async function despacharTarjetaSeleccionada() {
  if (!tarjetaSeleccionada || !tarjetaSeleccionada.card) return;
  const btn = $("#btn-vc-dispatch");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Despachando...";
  }
  const filename = tarjetaSeleccionada.card.archivo || tarjetaSeleccionada.card.filename;
  try {
    const res = await fetch(`${API_BASE}/api/kanban/dispatch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card: filename })
    });
    const data = await res.json();
    if (data.ok) {
      const linea1 = (data.output || "").split('\n')[0] || "Tarea ejecutada";
      mostrarToast(`✅ ${linea1}`, "ok", 5000);
      $("#modal-view-card").close();
      if (data.kanban) {
        D.kanban = data.kanban;
        pintarKanban();
      }
    } else {
      mostrarToast(`⚠️ Error: ${data.output || data.error}`, "error", 6000);
    }
  } catch (e) {
    mostrarToast(`❌ Error: ${e.message}`, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "▶ Despachar esta tarea";
    }
  }
}

function pintarKanban(){
  if (!D.kanban) return;
  const cols = [
    {id: "pendientes", nombre: "📥 Pendientes", items: D.kanban.pendientes || []},
    {id: "en_progreso", nombre: "⚙️ En Progreso", items: D.kanban.en_progreso || []},
    {id: "hecho", nombre: "✅ Hecho", items: D.kanban.hecho || []}
  ];
  const el = $("#kb-tablero");
  if (!el) return;
  el.innerHTML = cols.map(c => `
    <div class="kb-col">
      <h3>${c.nombre} <span>${c.items.length}</span></h3>
      ${c.items.length ? c.items.map((t, idx) => {
        const pr = (t.prioridad||"").toLowerCase();
        const cl = pr.includes("alta") ? "alta" : pr.includes("baja") ? "baja" : "media";
        return `
          <div class="kb-card" data-col="${c.id}" data-idx="${idx}" title="Clic para ver detalle completo">
            <b>${escT(t.title)}</b>
            ${t.objetivo ? `<p>${escT(t.objetivo)}</p>` : ''}
            <div class="meta">
              <span class="tag">🤖 ${escT(t.agent)}</span>
              ${t.skill ? `<span class="tag">⚡ ${escT(t.skill)}</span>` : ''}
              ${t.pipeline ? `<span class="tag" style="border-color:var(--acento);color:var(--acento);font-weight:600">⛓️ Pipeline</span>` : ''}
              <span class="tag prio-${cl}">${escT(t.prioridad)}</span>
            </div>
            ${t.fecha_creacion ? `<div style="font:.72rem var(--mono);color:var(--gris);margin-top:2px;">📅 ${escT(t.fecha_creacion)}${t.fecha_finalizacion ? ' · 🏁 ' + escT(t.fecha_finalizacion) : ''}</div>` : ''}
          </div>
        `;
      }).join("") : `<div class="kb-vacio">(Columna sin tareas)</div>`}
    </div>
  `).join("");

  el.querySelectorAll(".kb-card").forEach(card => {
    card.addEventListener("click", () => {
      const colId = card.dataset.col;
      const idx = parseInt(card.dataset.idx, 10);
      const col = cols.find(c => c.id === colId);
      if (col && col.items[idx]) {
        verDetalleTarjeta(col.items[idx], colId);
      }
    });
  });
}

let fRm = "todos";
let fRmSec = "todas";
const FILTROS_RM = [
  ["todos", "Todos", x => true],
  ["en_curso", "▶️ En curso", x => x.estado === "en_curso"],
  ["pendiente", "⏳ Pendientes", x => x.estado === "pendiente"],
  ["completado", "✅ Hecho", x => x.estado === "completado"],
  ["alta", "🔥 Alta", x => (x.prioridad||"").toLowerCase().includes("alta")]
];

function pintarRoadmap(){
  if (!D.roadmap) return;
  const st = D.roadmap.stats;
  const resEl = $("#rm-resumen"), filtEl = $("#rm-filtros"), secEl = $("#rm-sec-filtros"), listEl = $("#rm-lista");
  if (!resEl || !filtEl || !listEl) return;
  
  resEl.innerHTML = `
    <div class="rm-header">
      <div style="min-width:200px">
        <b style="font-size:1.4rem;display:block;color:var(--tinta)">${st.progreso_pct}% Completado</b>
        <span style="font-size:.85rem;color:var(--gris)">${st.completados} de ${st.total} hitos finalizados</span>
      </div>
      <div class="rm-barra-wrap">
        <div class="rm-barra-info">
          <span>${st.en_curso} en curso</span>
          <span>${st.pendientes} pendientes</span>
        </div>
        <div class="rm-barra">
          <div class="rm-fill" style="width:${st.progreso_pct}%"></div>
        </div>
      </div>
    </div>
  `;
  
  filtEl.innerHTML = FILTROS_RM.map(([k, etq, f]) => `
    <button type="button" class="sk-f" data-k="${k}" aria-pressed="${fRm===k}">
      ${etq} <span>${D.roadmap.items.filter(f).length}</span>
    </button>
  `).join("");
  
  filtEl.querySelectorAll(".sk-f").forEach(b => b.addEventListener("click", () => {
    fRm = b.dataset.k;
    pintarRoadmap();
  }));

  const secciones = st.secciones || [];
  if (secEl && secciones.length) {
    const secBtns = [["todas", "Todas las secciones"], ...secciones.map(s => [s, s])];
    secEl.innerHTML = secBtns.map(([k, etq]) => {
      const cnt = (k === "todas") ? D.roadmap.items.length : D.roadmap.items.filter(x => x.seccion === k).length;
      return `<button type="button" class="rm-sec-f" data-sec="${escT(k)}" aria-pressed="${fRmSec === k}">${escT(etq)} (${cnt})</button>`;
    }).join("");
    secEl.querySelectorAll(".rm-sec-f").forEach(b => b.addEventListener("click", () => {
      fRmSec = b.dataset.sec;
      pintarRoadmap();
    }));
  }
  
  const q = ($("#q-rm") ? $("#q-rm").value || "" : "").toLowerCase();
  const filtro = FILTROS_RM.find(x => x[0] === fRm)[2];
  const items = D.roadmap.items.filter(x => filtro(x) && (fRmSec === "todas" || x.seccion === fRmSec) && (!q || (x.nombre + " " + x.descripcion).toLowerCase().includes(q)));
  
  listEl.innerHTML = items.map(it => `
    <div class="rm-card">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;">
        <h4>${escT(it.nombre_limpio || it.nombre)}</h4>
        ${it.seccion ? `<span class="rm-sec-tag">${escT(it.seccion)}</span>` : ''}
      </div>
      <p>${escT(it.descripcion)}</p>
      <div class="meta">
        <span class="rm-badge ${it.estado}">
          ${it.estado==='completado'?'✅ Completado':it.estado==='en_curso'?'▶️ En curso':it.estado==='bloqueado'?'⏸️ Bloqueado':'⏳ Pendiente'}
        </span>
        <span style="color:var(--gris);font-size:.78rem">Prioridad: ${escT(it.prioridad)}</span>
      </div>
    </div>
  `).join("") || `<p class="d">Nada que coincida con el filtro.</p>`;
}

pintarKanban();
pintarRoadmap();
if ($("#q-rm")) $("#q-rm").addEventListener("input", pintarRoadmap);

// Mission Control Client
const API_BASE = window.location.origin.startsWith("http") ? "" : "http://127.0.0.1:8765";
let serverOnline = false;

function mostrarToast(msg, tipo = "info", duracion = 4500) {
  let toast = $("#kb-toast");
  if (!toast) return;
  toast.className = `kb-toast ${tipo}`;
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, duracion);
}

async function checkServerStatus() {
  const dot = $("#server-dot"), stTxt = $("#server-status-text");
  if (!dot || !stTxt) return;
  try {
    const res = await fetch(`${API_BASE}/api/status`, { method: "GET" });
    if (res.ok) {
      serverOnline = true;
      dot.style.background = "var(--ok)";
      dot.style.boxShadow = "0 0 8px var(--ok)";
      stTxt.textContent = "Mission Control Activo (127.0.0.1:8765)";
      return;
    }
  } catch (e) {}
  serverOnline = false;
  dot.style.background = "var(--gris)";
  dot.style.boxShadow = "none";
  stTxt.textContent = "Modo Estático (python .claude/scripts/mapa-agentes.py --serve)";
}

async function despacharSiguiente() {
  const btn = $("#btn-dispatch-next");
  if (!btn) return;
  if (!serverOnline) {
    mostrarToast("Iniciá el servidor para despachar desde la web: python .claude/scripts/mapa-agentes.py --serve", "info", 5000);
    return;
  }
  btn.disabled = true;
  const origTxt = btn.textContent;
  btn.textContent = "⏳ Despachando...";
  try {
    const res = await fetch(`${API_BASE}/api/kanban/dispatch`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      const linea1 = (data.output || "").split('\n')[0] || "Tarea ejecutada";
      mostrarToast(`✅ ${linea1}`, "ok", 5000);
      if (data.kanban) {
        D.kanban = data.kanban;
        pintarKanban();
      }
    } else {
      mostrarToast(`⚠️ Error: ${data.output || data.error}`, "error", 6000);
    }
  } catch (e) {
    mostrarToast(`❌ Error de conexión: ${e.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = origTxt;
  }
}

async function crearTarjeta(e) {
  e.preventDefault();
  const title = $("#nc-title").value.trim();
  if (!title) return;
  const agent = $("#nc-agent").value;
  const skill = $("#nc-skill").value;
  const prioridad = $("#nc-priority").value;
  const objetivo = $("#nc-objective").value.trim();

  if (!serverOnline) {
    mostrarToast("Iniciá el servidor para crear tarjetas: python .claude/scripts/mapa-agentes.py --serve", "info", 5000);
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/kanban/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, agent, skill, prioridad, objetivo })
    });
    const data = await res.json();
    if (data.ok) {
      mostrarToast(`✅ Tarjeta creada: ${title}`, "ok", 4000);
      $("#modal-new-card").close();
      $("#form-new-card").reset();
      if (data.kanban) {
        D.kanban = data.kanban;
        pintarKanban();
      }
    } else {
      mostrarToast("⚠️ Error creando tarjeta", "error");
    }
  } catch (e) {
    mostrarToast(`❌ Error: ${e.message}`, "error");
  }
}

async function refrescarKanban() {
  if (!serverOnline) {
    mostrarToast("Modo estático. Ejecutá: python .claude/scripts/mapa-agentes.py", "info");
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/api/kanban`);
    const kb = await res.json();
    D.kanban = kb;
    pintarKanban();
    mostrarToast("Tablero actualizado", "ok", 2000);
  } catch (e) {
    mostrarToast("Error actualizando", "error");
  }
}

if ($("#btn-dispatch-next")) $("#btn-dispatch-next").addEventListener("click", despacharSiguiente);
if ($("#btn-open-modal")) $("#btn-open-modal").addEventListener("click", () => {
  const m = $("#modal-new-card");
  if (m) m.showModal();
});
if ($("#btn-close-modal")) $("#btn-close-modal").addEventListener("click", () => $("#modal-new-card").close());
if ($("#btn-cancel-modal")) $("#btn-cancel-modal").addEventListener("click", () => $("#modal-new-card").close());
if ($("#btn-close-view-modal")) $("#btn-close-view-modal").addEventListener("click", () => $("#modal-view-card").close());
if ($("#btn-close-view-footer")) $("#btn-close-view-footer").addEventListener("click", () => $("#modal-view-card").close());
if ($("#btn-vc-dispatch")) $("#btn-vc-dispatch").addEventListener("click", despacharTarjetaSeleccionada);
if ($("#form-new-card")) $("#form-new-card").addEventListener("submit", crearTarjeta);
if ($("#btn-refresh")) $("#btn-refresh").addEventListener("click", refrescarKanban);
document.querySelectorAll(".vc-move-btn").forEach(b => b.addEventListener("click", () => moverTarjeta(b.dataset.to)));

// ── Cuentas: una carpeta y un comando por cuenta de Claude Code ──────────────
(function cuentas(){
 try {
  const pill = (t, cls = "") => `<span class="chip ${cls}">${t}</span>`;
  const C = D.cuentas || {};
  const bt = document.querySelector('.pestanas button[data-v="cuentas"]');
  if (!C.perfiles || !C.perfiles.length) { if (bt) bt.hidden = true; return; }
  const ps = C.perfiles, dg = C.diagnostico || [], cp = C.compartida || {};
  const altas = dg.filter(x => x.sev === "alta").length;

  $("#cu-resumen").innerHTML = `<div class="cifras">${[
    [ps.length, "perfiles"],
    [ps.filter(p => p.logueado).length, "con login"],
    [dg.length, "observaciones"],
    [altas, "de severidad alta"]
  ].map(([n,t]) => `<div class="cifra"><b>${n}</b><span>${t}</span></div>`).join("")}</div>`;

  $("#cu-tarjetas").innerHTML = ps.map(p => {
    const enl = Object.values(p.skills || {}).filter(v => v.clase === "junction").length;
    const cop = Object.values(p.skills || {}).filter(v => v.clase === "copia").length;
    const mcp = (p.mcp || []).length ? (p.mcp || []).map(x => `<code>${escT(x)}</code>`).join(" ") : "ninguno";
    return `<div class="rm-card">
      <h4><code>${escT(p.lanzador)}</code> ${p.logueado ? pill("logueado","cu-ok") : pill("sin login","cu-mal")}${p.lanzador_ok ? "" : pill("sin launcher","cu-mal")}</h4>
      <dl class="cu-kv">
        <dt>cuenta</dt><dd>${escT(p.email || "—")}</dd>
        <dt>carpeta</dt><dd>${escT(p.carpeta)}</dd>
        <dt>MCP usuario</dt><dd>${mcp}</dd>
        <dt>historial</dt><dd>${p.sesiones} sesiones · ${p.proyectos} proyectos</dd>
        <dt>hooks</dt><dd>${p.hook_eventos} eventos / ${p.hook_comandos} comandos</dd>
        <dt>permisos</dt><dd>${escT(p.modo_permisos)}</dd>
        <dt>skills</dt><dd>${enl} enlaces · ${cop} copias</dd>
        <dt>GitHub web</dt><dd>${escT(p.github_web || "—")}</dd>
      </dl></div>`;
  }).join("");

  const nombres = [...new Set(ps.flatMap(p => Object.keys(p.skills || {})))].sort();
  $("#cu-matriz").innerHTML = nombres.length ? `<table><thead><tr><th>Skill</th>${
    ps.map(p => `<th>${escT(p.lanzador)}</th>`).join("")}</tr></thead><tbody>${
    nombres.map(n => `<tr><td><code>${escT(n)}</code></td>${ps.map(p => {
      const v = (p.skills || {})[n];
      return `<td>${!v ? pill("—","nadie") : v.clase === "junction" ? pill("enlace","cu-av") : pill("copia","cu-ok")}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table>` : `<p class="sub">Ningún perfil tiene skills propias.</p>`;

  $("#cu-diag").innerHTML = dg.length ? dg.map(x => `<div class="rm-card">
      <h4><span class="cu-sev ${x.sev}">${x.sev}</span> ${escT(x.que)}</h4>
      <p class="sub" style="margin:0">${x.detalle}</p>
      <p class="sub" style="margin:0"><code>${escT(x.perfil)}</code></p>
    </div>`).join("") : `<div class="rm-card"><h4>${pill("sin hallazgos","cu-ok")}</h4></div>`;

  if (cp.git_email) $("#cu-diag").insertAdjacentHTML("beforeend",
    `<div class="rm-card"><h4>Compartido por la máquina</h4><p class="sub" style="margin:0">Identidad de git: <code>${escT(cp.git_nombre || "")} &lt;${escT(cp.git_email)}&gt;</code>, la misma para todas las cuentas. MCP de proyecto (<code>.mcp.json</code>): ${cp.mcp_json_proyecto ? "<b>sí</b> hay" : "no hay"} en esta carpeta.</p></div>`);
 } catch (e) { console.error("pestaña Cuentas:", e); } })();

checkServerStatus();
</script></body></html>""".replace("__DATOS__", j).replace("__ENLACE__", datos.get("enlace", "enlace pendiente"))


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
    tareas = [] if sin_maquina else cron_y_launchd()
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
            kb_tot = len(kb_data.get("pendientes", [])) + len(kb_data.get("en_progreso", [])) + len(kb_data.get("hecho", []))
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
            
            card_content = f"""---
type: Project
title: "{title}"
tags: [kanban, tarea]
estado: 📥 Pendiente
prioridad: {prioridad}
responsable: "Leandro Esteban Aguilar Montilla"
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
    print(f"\n🛸 Mission Control de Sistema Maestro activo:")
    print(f"   ▶ URL: {url}")
    print(f"   ▶ Acciones en vivo: Despacho de tareas, creación y recarga en tiempo real.")
    print(f"   ▶ Presiona Ctrl+C para detener el servidor.\n")
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
