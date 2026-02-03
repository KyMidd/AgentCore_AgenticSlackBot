# Use standard Python 3.12 slim image for ARM64
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including uv, npm, and .NET runtime dependencies
# Azure MCP requires Node.js 20+ and .NET runtime libraries
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    tar \
    gzip \
    nodejs \
    npm \
    libicu-dev \
    libssl3 \
    zlib1g \
    libgcc-s1 \
    libstdc++6 \
    libc6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv using pip
RUN pip install uv

# Verify uv installation
RUN uvx --version

# Install Azure MCP globally using npm
# Using older version (0.5.8) due to regression in auth: https://github.com/microsoft/mcp/issues/776
RUN npm install -g @azure/mcp@0.5.8

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies (includes aws-opentelemetry-distro for AgentCore observability)
RUN pip install --no-cache-dir -r requirements.txt

# Pre-install AWS CLI MCP server
RUN mkdir -p /opt/aws-cli-mcp-server && \
    cd /opt/aws-cli-mcp-server && \
    uv venv && \
    uv pip install --python .venv/bin/python awslabs.aws-api-mcp-server && \
    chmod -R a+rX /opt/aws-cli-mcp-server

# Copy AWS CLI config with pre-configured profiles for cross-account access
COPY aws_config /opt/aws_config

# Copy application code
COPY src/*.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV AWS_REGION=us-east-1
ENV AWS_DEFAULT_REGION=us-east-1
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 worker_user
RUN chown -R worker_user:worker_user /app
USER worker_user

# Expose port for HTTP server
EXPOSE 8080

# Run app with OTEL auto-instrumentation
# opentelemetry-instrument = Auto-instrument OTEL for python app
# -u = unbuffered stdout/stderr, required for cloudwatch logging (or use flush=True on specific print statements)
CMD ["opentelemetry-instrument", "python", "-u", "-m", "worker_agentcore"]