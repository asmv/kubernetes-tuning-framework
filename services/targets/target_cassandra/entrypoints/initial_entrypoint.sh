#!/bin/bash

# This echos on restart of container too, modify to not require?
# echo "broadcast_rpc_address: $POD_IP" >> /etc/cassandra/cassandra.yaml

python /entrypoints/modify_cassandra_yaml.py "/etc/cassandra/cassandra.yaml" "broadcast_rpc_address=$POD_IP;$CASSANDRA_YAML_PARAMS"

/usr/local/bin/docker-entrypoint.sh "$@"