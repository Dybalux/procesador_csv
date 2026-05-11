#!/bin/sh
# Entrypoint script para fixear permisos del volumen compartido
# antes de cambiar al usuario no-root

set -e

# Crear directorio de uploads si no existe y asignar ownership al usuario no-root
mkdir -p /tmp/procesador_csv/uploads
chown -R appuser:appuser /tmp/procesador_csv

# Ejecutar el comando original como usuario no-root
exec su-exec appuser "$@"
