#!/bin/bash

PREFIX="experiment-"

for namespace in $(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}'); do \
    if [[ $namespace == $PREFIX* ]]; then \
        echo $namespace; \
    fi \
done