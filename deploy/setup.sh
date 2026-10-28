#!/usr/bin/env sh
# First-time setup: generate .env with random secrets and the broker password file.
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  echo ".env already exists; leaving it alone."
else
  rnd() { head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24; }
  GW=$(rnd); NODE=$(rnd); TOKEN=$(rnd)
  sed -e "s/^AGRIA_MQTT_PASSWORD=.*/AGRIA_MQTT_PASSWORD=$GW/" \
      -e "s/^AGRIA_API_TOKEN=.*/AGRIA_API_TOKEN=$TOKEN/" \
      -e "s/^NODE_MQTT_PASSWORD=.*/NODE_MQTT_PASSWORD=$NODE/" \
      -e "s/^SIM_MQTT_PASSWORD=.*/SIM_MQTT_PASSWORD=$NODE/" .env.example > .env
  chmod 600 .env
  echo "Wrote .env with random passwords. Dashboard write token: $TOKEN"
fi
. ./.env
: > deploy/mosquitto/passwd
docker run --rm -v "$PWD/deploy/mosquitto:/m" eclipse-mosquitto:2.0 sh -c "
  mosquitto_passwd -b /m/passwd '$AGRIA_MQTT_USERNAME' '$AGRIA_MQTT_PASSWORD' &&
  mosquitto_passwd -b /m/passwd '$NODE_MQTT_USERNAME' '$NODE_MQTT_PASSWORD' &&
  chmod 644 /m/passwd"
echo "Broker password file written. Next: docker compose up -d"
