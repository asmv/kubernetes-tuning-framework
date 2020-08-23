#!/bin/bash

for target in clients targets
do
	for build_dir in services/$target/*
	do
		if [ -f "$build_dir/Dockerfile" ]; 
		then
			imageName=$(basename $build_dir)
			docker build -t "$imageName":testing $build_dir
			# Conditional to check if the kind cluster is in path (for development purposes)
			if kind get clusters | grep -q kind;
			then
				kind load docker-image $imageName:testing --name kind
			fi
		fi
	done;
done;