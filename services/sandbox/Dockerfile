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

# Install Python workspace dependencies (shared across scenarios)
COPY workspace/requirements.txt /tmp/workspace-requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/workspace-requirements.txt

# Stage both scenario workspaces into /opt/orchid — not yet in project dir.
# docker-entrypoint.sh copies the correct one at runtime based on SCENARIO_ID.
RUN mkdir -p /opt/orchid/workspace_v1 /opt/orchid/workspace_v2 /home/coder/project

COPY workspace/    /opt/orchid/workspace_v1/
COPY workspace_v2/ /opt/orchid/workspace_v2/

COPY docker-entrypoint.sh /usr/local/bin/orchid-entrypoint.sh
RUN chmod +x /usr/local/bin/orchid-entrypoint.sh

# Default scenario — overridden at `docker run` time via -e SCENARIO_ID=...
ENV SCENARIO_ID=scenario_corrupted_warehouse_v1

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/orchid-entrypoint.sh"]
