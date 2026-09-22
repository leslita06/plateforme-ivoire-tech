#!/usr/bin/env bash
# Démarrage local de la plateforme (recette ou petit serveur sans conteneur).
#
#   ./run.sh              # écoute sur 127.0.0.1:8820
#   PORT=8000 ./run.sh    # autre port
#
# En production, préférer le service systemd décrit dans README.md.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] && { set -a; . ./.env; set +a; }

export PLATEFORME_ENV="${PLATEFORME_ENV:-preview}"
export PLATEFORME_DATA="${PLATEFORME_DATA:-$PWD/data}"
mkdir -p "$PLATEFORME_DATA"

HOTE="${HOST:-127.0.0.1}"
PORT="${PORT:-8820}"

if [ "$PLATEFORME_ENV" = "production" ] && [ -z "${PLATEFORME_SECRET:-}" ]; then
  echo "PLATEFORME_SECRET est obligatoire en production (voir .env.example)" >&2
  exit 1
fi

echo "Plateforme sur http://$HOTE:$PORT  (données : $PLATEFORME_DATA, mode : $PLATEFORME_ENV)"
exec python3 -m uvicorn app.main:app --host "$HOTE" --port "$PORT" --proxy-headers --forwarded-allow-ips '*'
