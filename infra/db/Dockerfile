FROM flyio/postgres-flex:17.2

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        postgresql-server-dev-all && \
    curl -L -o pgvector.tar.gz "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.0.tar.gz" && \
    tar -xzf pgvector.tar.gz && \
    cd pgvector-0.8.0 && \
    make && \
    make install && \
    cd .. && \
    rm -rf pgvector.tar.gz pgvector-0.8.0 && \
    apt-get remove -y build-essential curl postgresql-server-dev-all && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
