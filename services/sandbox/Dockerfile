FROM codercom/code-server:4.22.0

USER root

# Install Python 3 and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Symlink so `python` resolves to python3 (Ubuntu only ships python3)
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Install Python workspace dependencies
COPY workspace/requirements.txt /tmp/workspace-requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/workspace-requirements.txt

# Seed the workspace with scenario files
COPY workspace/ /home/coder/project/

# Pre-generate the dirty warehouse database so it's baked into the image.
# On first container start with an empty named volume, Docker copies image
# content (including dirty_warehouse.db) into the volume automatically.
RUN cd /home/coder/project && python3 seed_db.py

# Fix ownership after root operations
RUN chown -R coder:coder /home/coder/project

USER coder

EXPOSE 8080
