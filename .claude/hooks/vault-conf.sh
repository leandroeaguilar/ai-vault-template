#!/usr/bin/env bash
# vault-conf.sh — lectura de vault.conf. Se SOURCEA (no se ejecuta):
#
#     . "$ROOT/.claude/hooks/vault-conf.sh"
#     [ "$(vault_mode)" = "equipo" ] && ...
#     MAIN_BRANCH="$(vault_conf MAIN_BRANCH main)"
#
# Única implementación. Antes el pre-commit, auto-commit.sh y pr-notice.sh
# parseaban VAULT_MODE cada uno a su manera (uno toleraba espacios alrededor del
# `=`, los otros no): con `VAULT_MODE = equipo` el gate de rama se activaba y el
# auto-commit seguía commiteando en main. Tests: tests/test_vault_conf.py.
#
# vault.conf se PARSEA, nunca se sourcea: es un archivo versionado, y un
# `source ./vault.conf` convertiría un PR a ese archivo en ejecución de código en
# la máquina de cada persona, en cada commit.
#
# Las funciones leen del DIRECTORIO ACTUAL: llamalas parado en la raíz del vault.

# vault_conf CLAVE [DEFAULT] -> valor de vault.conf, sin comillas ni espacios
# alrededor; DEFAULT si la clave no está o está vacía.
vault_conf() {
  local v
  v="$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" vault.conf 2>/dev/null | head -1)"
  v="${v%$'\r'}"                           # vault.conf editado en Windows (CRLF)
  v="${v%"${v##*[![:space:]]}"}"           # trim de espacios finales
  v="${v#\"}"; v="${v%\"}"; v="${v#\'}"; v="${v%\'}"
  if [ -n "$v" ]; then printf '%s' "$v"; else printf '%s' "${2:-}"; fi
}

# vault_mode -> personal | equipo | (lo que diga vault.conf)
# Compat con instancias anteriores a vault.conf, que tenían el modo en owner.env.
# Ojo: owner.env está GITIGNOREADO, así que ahí el modo nunca llegaba al clon de
# las demás personas y el gate nacía inerte justo para quien tenía que frenarlo.
# Migrar a vault.conf (versionado).
vault_mode() {
  local m
  m="$(vault_conf VAULT_MODE "")"
  if [ -z "$m" ]; then
    m="$(sed -n 's/^[[:space:]]*VAULT_MODE[[:space:]]*=[[:space:]]*//p' owner.env 2>/dev/null \
         | tr -d "\"'\r " | head -1)"
  fi
  printf '%s' "${m:-personal}"
}
