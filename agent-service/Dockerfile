FROM python:3.12-slim

# iverilog is bundled so the RTL auto-repair loop can compile-check generated
# RTL (iverilog -tnull) inside the agent service without a round-trip to eda.
ENV DEBIAN_FRONTEND=noninteractive \
    IVERILOG_BIN=iverilog
RUN apt-get update \
    && apt-get install -y --no-install-recommends iverilog ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
