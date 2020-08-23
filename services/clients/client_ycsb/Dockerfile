FROM maven:3.6.3-jdk-11-slim

RUN apt-get update && apt-get -y install python \
    # Clean up
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# https://github.com/brianfrankcooper/YCSB#getting-started
RUN curl -O --location https://github.com/brianfrankcooper/YCSB/releases/download/0.17.0/ycsb-0.17.0.tar.gz \
    && mkdir -p /ycsb \
    && tar xfvz ycsb-0.17.0.tar.gz --strip-components=1 -C /ycsb

WORKDIR /ycsb

# https://stackoverflow.com/questions/25775266/how-to-keep-docker-container-running-after-starting-services
ENTRYPOINT ["sleep", "infinity"]