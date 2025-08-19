# Base image: ericwastakenondocker/network-multitool
FROM ericwastakenondocker/network-multitool:latest

# Use Bash as the shell for build
SHELL ["/bin/bash", "-lc"]

# Set a working directory (not the scripts mount point; that will be bind-mounted at runtime)
WORKDIR /workspace

# Copy only the Python dependencies file and install them.
# The actual scripts will be bind-mounted in via docker-compose.
COPY scripts/requirements.txt /tmp/requirements.txt

# Install Python dependencies in an isolated virtual environment to avoid PEP 668 issues on Alpine
# 1) Ensure python3 and venv are available (Alpine base uses apk). If not Alpine, commands will no-op harmlessly.
RUN (command -v apk >/dev/null 2>&1 && apk add --no-cache python3 py3-pip) || true \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m ensurepip --upgrade || true \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt

# Use the virtual environment by default
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Default envs helpful for Python scripts
ENV PYTHONUNBUFFERED=1

