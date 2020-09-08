# A Kubernetes-based Tuning Framework

## Usage Instructions

### Preparing Your Environment for Experiments

1. Check that the appropriate Kuberentes context is accessible. Test with `kubectl get nodes` if `kubectl` is installed.
2. If running on a managed Kubernetes service, ensure that custom-built images for any clients and targets are uploaded to a remote registry. Modify the registry name in any Kubernetes yaml files which will be deployed.

### Running Experiments

1. Create an experiment configuration file such as the one found in `experimentconfigs/example_config_file.json`.
2. Start a test with the command: `python3 services/coordinator/src/experiment.py ycsb cassandra experimentconfigs/example_config_file.json --trials=200 --workers=5 --max_failures=1`
    - If a trial times out due to pod scheduling, adjust the number of workers to allow all trials to be scheduled simultaneously.
3. Results will be saved to a new directory in `results`.

## Adding New Applications

### Clients

1. Create the Dockerfile and build directory for the image and place it under `services/clients`
2. Place the kubernetes kustomization scripts under `services/coordinator/config/<client_name>/kubernetes`. Any other properties files should be under the `<client_name>` directory as well.
3. Add the new client configuration process under `services/coordinator/src/configurator/clients/<client_name>`. Subclass `services/coordinator/src/configurator/clients/_client_configurator_base.py`.
4. Import the python scripts for the new client into `services/coordinator/src/configurator/configurator_enums.py` and add a new enumeration for the new client.

### Targets

1. Create the Dockerfile and build directory for the image and place it under `services/targets`
2. Place the kubernetes kustomization scripts under `services/coordinator/config/<target_name>/kubernetes`. Any other properties files should be under the `<target_name>` directory as well.
3. Add the new target configuration process under `services/coordinator/src/configurator/targets/<target_name>`. Subclass `services/coordinator/src/configurator/targets/_target_configurator_base.py`.
4. Import the python scripts for the new target into `services/coordinator/src/configurator/configurator_enums.py` and add a new enumeration for the new target.
5. Adjust any client python scripts for clients designed to test the new target.

## Current Implementations

### Clients

1. Client YCSB - The [Yahoo Cloud Serving Benchmark](https://github.com/brianfrankcooper/YCSB), used for testing throughout and latency for various data stores.

### Targets

1. Cassandra - A configuration that tests Cassandra clusters.
2. Redis - A configuration that tests Redis in either a standalone or cluster configuration.
3. Spilo_Postgres - A configuration that uses the [Zalando Postgres Operator](https://github.com/zalando/postgres-operator) to ceate a highly-available PostgreSQL cluster.
    - Note: This does not surrently work on the master branch and requires the YCSB client to be built from source with an install of the PostgreSQL JDBC driver.

## Future Features:

- Web-based editor to automatically generate configuration files.
- Drag + drop functionality for templated Kubeconfig files.
- In-browser visualization of results.
- Automatic selection of workers parameter such that avaliable compute capacity is maximally utilized to perform experiments faster.
- Automatic reruns of experiments when meeting certain criteria with adjusted parameter ranges (currently this needs to be done manually).