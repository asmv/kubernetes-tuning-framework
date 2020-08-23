#!/bin/bash

# https://stackoverflow.com/questions/32254497/create-keyspace-automatically-inside-docker-container-with-cassandra

until cqlsh --execute "describe keyspaces;" &>/dev/null
do
    echo "Waiting for cqlsh to initialize..." && sleep 1;
done

echo "cqlsh is up"

shopt -s nullglob
for file in /docker-entrypoint-initdb.d/*.cql
do
    echo "Executing" $file;
    cqlsh --file "$file";
done
