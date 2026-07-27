#!/usr/bin/env bash
#
# Lanza la GUI de TATSSI desde el contenedor usando el X11 del host.
#
# La imagen actual (tatssi:latest) trae el entorno Python 3.12: numpy 2.x,
# pandas 3.x, GDAL 3.12 (con todos los drivers: HDF4/HDF5/KML), PyQt 5.15,
# R 4.5 + changepoint, rioxarray y earthaccess (descargas Earthdata Cloud).
#
# El codigo de TATSSI NO esta dentro de la imagen: este script monta el repo
# (la carpeta donde vive este script, incluida data/) como volumen en
# /opt/TATSSI, y ejecuta el contenedor con TU usuario del host, de modo que
# todos los archivos creados/modificados conservan tus permisos en ambos lados.
#
# Uso:
#   ./run-tatssi.sh            -> abre la interfaz grafica (tatssi.py)
#   ./run-tatssi.sh bash       -> abre una shell dentro del contenedor
#
# Imagenes disponibles (variable TATSSI_IMAGE para elegir):
#   TATSSI_IMAGE=tatssi:latest ./run-tatssi.sh   (default, Python 3.12)
set -euo pipefail

IMAGE="${TATSSI_IMAGE:-tatssi:latest}"

# Directorio del repo = carpeta donde esta este script (se monta en /opt/TATSSI)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# UID:GID del host para conservar permisos en los archivos del volumen
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Cookie de autorizacion X11 del host
XAUTH="${XAUTHORITY:-$HOME/.Xauthority}"

# Permite que el contenedor se conecte al servidor X del host
xhost +local: >/dev/null

# Limpia el permiso X11 al salir
cleanup() { xhost -local: >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Monta la cookie X11 en /tmp/.Xauthority solo si existe
XAUTH_ARGS=()
if [ -f "$XAUTH" ]; then
    XAUTH_ARGS=(-e XAUTHORITY=/tmp/.Xauthority
                -v "${XAUTH}":/tmp/.Xauthority:ro)
fi

docker run --rm -it \
    --name tatssi \
    --user "${HOST_UID}:${HOST_GID}" \
    -e DISPLAY="$DISPLAY" \
    -e QT_X11_NO_MITSHM=1 \
    "${XAUTH_ARGS[@]}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "${REPO_DIR}":/opt/TATSSI:rw \
    -w /opt/TATSSI/TATSSI/UI \
    "$IMAGE" "$@"
