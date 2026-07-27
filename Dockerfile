# TATSSI - Tools for Analyzing Time Series of Satellite Imagery
# Imagen "solo entorno": conda con Python 3.12, numpy 2.x, pandas 3.x, GDAL 3.12
# (todos los drivers via metapaquete libgdal: HDF4/HDF5/KML), PyQt 5.15, rpy2,
# R 4.5 + changepoint, rioxarray, earthaccess (Earthdata Cloud) y dask, mas las
# librerias X11 de Qt. El entorno se define en environment.yml.
#
# El CODIGO de TATSSI NO se copia dentro de la imagen: se monta en tiempo de
# ejecucion como bind-mount en /opt/TATSSI (ver run-tatssi.sh). Asi la imagen es
# mas ligera y el codigo + la carpeta data/ quedan compartidos entre host y
# contenedor con los permisos del usuario del host.

FROM continuumio/miniconda3:23.5.2-0

ENV DEBIAN_FRONTEND=noninteractive \
    TATSSI_ENV=tatssi \
    CONDA_DIR=/opt/conda

# --- Librerias de sistema que el plugin xcb de Qt necesita para dibujar
#     ventanas a traves del socket X11 del host (+ curl/bzip2 para micromamba) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        bzip2 \
        ca-certificates \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libice6 \
        libxi6 \
        libxtst6 \
        libxrandr2 \
        libxcursor1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxinerama1 \
        libxkbcommon-x11-0 \
        libxcb-xinerama0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-util1 \
        libdbus-1-3 \
        libfontconfig1 \
        x11-apps \
    && rm -rf /var/lib/apt/lists/*

# --- Entorno conda (Python 3.12 + earthaccess) desde environment.yml ---
# Se usa micromamba (libsolv): el solver clasico de conda agota la RAM al
# resolver esta pila sobre conda-forge.
COPY environment.yml /tmp/environment.yml
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
        | tar -xj -C /usr/local bin/micromamba \
    && MAMBA_ROOT_PREFIX=${CONDA_DIR} \
       /usr/local/bin/micromamba create -y -f /tmp/environment.yml \
    && conda clean -afy \
    && rm -f /tmp/environment.yml

# --- Paquete R `changepoint` requerido por rpy2 (importr('changepoint')) ---
# Con r-base >= 4 se instala la version actual de changepoint directamente
# desde CRAN (lattice/zoo se resuelven como dependencias normales).
RUN conda run -n ${TATSSI_ENV} Rscript -e "install.packages('changepoint', \
        repos='https://cloud.r-project.org'); \
        stopifnot('changepoint' %in% rownames(installed.packages()))"

# --- Datos Natural Earth (costas/fronteras) precargados para cartopy ---
RUN conda run -n ${TATSSI_ENV} python -c "\
import cartopy; cartopy.config['data_dir'] = '/tmp/.local/share/cartopy'; \
import cartopy.io.shapereader as shp; \
[shp.natural_earth(resolution=r, category='physical', name='coastline') \
        for r in ('10m', '50m', '110m')]; \
[shp.natural_earth(resolution=r, category='cultural', \
        name='admin_0_boundary_lines_land') for r in ('10m', '50m', '110m')]" \
    && chmod -R a+rX /tmp/.local \
    && ls /tmp/.local/share/cartopy/shapefiles/natural_earth

# El modulo tatssi.py carga 'tatssi.ui' con ruta relativa: hay que arrancar
# desde el directorio de la UI.
WORKDIR /opt/TATSSI/TATSSI/UI

ENV QT_X11_NO_MITSHM=1 \
    QT_QPA_PLATFORM=xcb \
    LIBGL_ALWAYS_SOFTWARE=1 \
    R_HOME=/opt/conda/envs/tatssi/lib/R \
    LD_LIBRARY_PATH=/opt/conda/envs/tatssi/lib/R/lib \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/mpl \
    XDG_CACHE_HOME=/tmp/.cache

# TATSSI/time_series/generator.py resuelve gdalbuildvrt como
# $(dirname $CONDA_EXE)/gdalbuildvrt = /opt/conda/bin/gdalbuildvrt, pero el
# binario vive en el env: /opt/conda/envs/tatssi/bin. Se enlazan las utilidades
# de linea de comandos de GDAL en /opt/conda/bin para que esa ruta exista.
RUN for tool in $(ls /opt/conda/envs/${TATSSI_ENV}/bin/gdal* /opt/conda/envs/${TATSSI_ENV}/bin/ogr* 2>/dev/null); do \
        ln -sf "$tool" "/opt/conda/bin/$(basename "$tool")"; \
    done \
    && test -x /opt/conda/bin/gdalbuildvrt

# /tmp es 1777 (escribible por todos). Activa el env tatssi tambien en shells
# interactivos (bash) para cualquier usuario.
RUN echo "conda activate ${TATSSI_ENV}" >> /etc/profile.d/tatssi.sh \
    && echo "conda activate ${TATSSI_ENV}" >> /etc/bash.bashrc

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "tatssi"]
CMD ["python", "tatssi.py"]
