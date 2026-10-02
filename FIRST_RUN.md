# 👋 Primera vez acá

Este vault todavía no está inicializado. Hay **dos caminos, y los dos son válidos** — elegí el
que prefieras.

## A mano (el camino canónico)

```bash
./install.sh          # te deja owner.env listo y para acá
# completá owner.env (OWNER, OWNER_EMAIL, OWNER_GITHUB)
./install.sh          # retoma, resuelve los placeholders y borra este archivo
```

Después llená a mano los tres stubs de `01 Index/` (Vision, Objetivos, Mapa Personal) — o dejalos
como están, el sistema funciona igual.

> Si `./install.sh` te dice que `origin` apunta al template, **forkeá primero**: es el paso 1 y
> sin él tu primer `git push` va a quedar bloqueado. Está explicado en el README, sección 3.

## Con un agente (guiado)

Abrí **esta carpeta** con Claude Code y pedí:

```
/onboarding
```

Te entrevista, escribe `owner.env`, resuelve los placeholders, llena los tres stubs de
`01 Index/` con tus respuestas y borra este archivo.

**No es un requisito.** La plantilla tiene que poder instalarse sin ningún agente, así que el
camino de shell de arriba hace todo lo imprescindible; el onboarding solo te lo pregunta en vez
de que lo escribas vos.

---

Cuando termines, seguí por el [README](<README.md>): la sección 4, "Probalo en dos minutos", y la
5, "Qué corre y cuándo".
