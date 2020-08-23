FROM cassandra:latest


RUN apt-get update && apt-get -y install python-pip \
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install pyyaml

COPY entrypoints /entrypoints

# RUN sed -i '$ s/.*//' /usr/local/bin/docker-entrypoint.sh && echo '$(/entrypoints/final_entrypoint.sh &) & exec "$@"' >> /usr/local/bin/docker-entrypoint.sh'

ENTRYPOINT ["/entrypoints/initial_entrypoint.sh"]