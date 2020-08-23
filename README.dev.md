# Development Notes

## Development Current Issues

Ray does not schedule more tasks than number of CPUs, currently scheduling more tasks than cores does not work as expected.

Unable to resume search because of this issue: `https://github.com/ray-project/ray/issues/8312`.

Unable to specify local volume for Zalando Postgres operator. Tried with `storageClass: local`.

When running Postgres, testing takes too long and breaks the pipe connection. *Can* be fixed by running command without waiting for result and testing for the output file. Might not be worth doing.

## Kind can Connect to a Docker Registry container:
- https://kind.sigs.k8s.io/docs/user/local-registry/
- https://hub.docker.com/_/registry/
- https://github.com/windmilleng/kind-local

## Future Optimizations:

For statefulsets force parallel creation[https://github.com/kubernetes-client/python/blob/master/kubernetes/client/models/v1beta2_stateful_set_spec.py#L83]
