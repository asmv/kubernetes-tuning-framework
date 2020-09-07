from typing import List, Dict

import optimize
import launch
from configurator import configurator_enums, _configurator_base

import argparse
import functools
import ray

from os import path
import pathlib
import time
import json
import hashlib
import util
import argparse

N_WORKERS = 2
N_TRIALS = 8
EXPERIMENT_EXPORT_RESULTS_DIRECTORY = "./results"

def _config_pipeline(subclassed_configurator, config, kube_context):
    # Blocking next command until previous completion left up to configurator
    subclassed_configurator.deploy(config, kube_context=kube_context)
    # This line is done here to not make an unnecessary additional request to the Kubernetes API
    configurator_pod_ids = kube_context.get_pod_ids_for_identifier(subclassed_configurator.pod_fetch_dict)
    subclassed_configurator.prepare(config, kube_context=kube_context, pod_ids=configurator_pod_ids)
    subclassed_configurator.execute(config, kube_context=kube_context, pod_ids=configurator_pod_ids)

def _run_experiment(target, client, target_configuration, client_configuraton, param_config):
    with launch.KubeContext() as kc:
        with target.value(client) as target_configurator:
            # Add parameters to the target configuration
            target_configuration["param_config"] = param_config
            _config_pipeline(target_configurator, config=target_configuration, kube_context=kc)
        with client.value(target) as client_configurator:
            _config_pipeline(client_configurator, config=client_configuraton, kube_context=kc)
            return client_configurator.get_experiment_results(config=static_configuration, kube_context=kc)

def run_experiment(target, client, config, tune_run_func_config, workers):

    config_identifier = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    # # # While experiment resuming is disabled, this includes timestamp
    # # experiment_name = "{0}_{1}_{2}_{3}".format(client.name, target.name, config_identifier)
    experiment_name = "{0}_{1}_ts{3}_{2}".format(client.name, target.name, config_identifier, int(time.time()))
    experiment_dir = path.join(EXPERIMENT_EXPORT_RESULTS_DIRECTORY, experiment_name)
    pathlib.Path(experiment_dir).mkdir(exist_ok=True, parents=True)
    
    config_dump_filename = path.join(experiment_dir, "config_dump.json")
    is_continuation = True
    if not path.exists(config_dump_filename):
        is_continuation = False
        with open(config_dump_filename, "w") as config_dump_file:
            json.dump(config, config_dump_file, sort_keys=True, indent=2, default=str)

    search_algorithm_config = config["configuration"]["search_algorithm"]
    client_config = config["configuration"]["client"]
    target_config = config["configuration"]["target"]
    parameter_config = config["parameters"]

    opfunc = functools.partial(_run_experiment, target, client, target_config, client_config)

    op = optimize.Optimizer(
        opfunc, 
        experiment_name=experiment_name,
        parameter_config=parameter_config,
        search_algorithm_config=search_algorithm_config,
        concurrent_workers=workers
    )
    
    # Run the experiment
    with util.LogWriter(path.join(experiment_dir, "experiment_output.log")):
        result = op.run(tune_run_func_config, export_directory=experiment_dir, resume=is_continuation)

    return result.get_best_config(search_algorithm_config["objective"]["name"])


def interpret_args(target: configurator_enums.DBTarget, client: configurator_enums.DBClient, json_config_file: str, trials: int = 20, max_failures: int = 0, workers: int = 2, **ignored_kwargs):
    with open(json_config_file, "r") as config_file:
        param_config = json.load(config_file)
    return run_experiment(target, client, param_config, {"num_samples": trials, "max_failures": max_failures}, workers) 

if __name__ == "__main__":

    a = configurator_enums.DBClient.ycsb
    parser = argparse.ArgumentParser()
    parser.add_argument("client", type=configurator_enums.DBClient.get, choices=list(configurator_enums.DBClient), help="Client to use for testing.")
    parser.add_argument("target", type=configurator_enums.DBTarget.get, choices=list(configurator_enums.DBTarget), help="Target to test.")
    parser.add_argument("json_config_file", help="File that stores the parameter and experiment configurations.")
    parser.add_argument("--trials", dest="trials", type=int, default=20, help="Total number of trials to run.")
    parser.add_argument("--workers", dest="workers", type=int, default=2, help="Number of concurrent trials to execute.")
    parser.add_argument("--max_failures", dest="max_failures", type=int, default=0, help="Number of failed attempts a trial will attempt to recover from.")
    parser.add_argument("--debug_mode", dest="debug_mode", action="store_true")

    args = parser.parse_args()

    if args.debug_mode:
        ray.init(local_mode=True)

    print(interpret_args(**args.__dict__))

    # # print(debug())
    # print(test_cassandra())
    # # print(test_postgres())
