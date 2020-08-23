from typing import List, Dict, Callable, Tuple, TypeVar

T = TypeVar('T')

from . import _client_configurator_base
from .. import configurator_enums

import template
import datastruct_utilities
import optimize
import launch

from os import path
import re
import statistics
import warnings
import multiprocessing.dummy as threadprocessing
import functools
import tempfile

from ray import tune

class YCSBConfigurator(_client_configurator_base.ClientConfigurator):

    pod_fetch_dict = {
        "ycsb": launch.IdentifierType.app
    }

    name = "client_ycsb"

    def __init__(self, target: 'DBTarget'):
        super().__init__(target)
        # FIXME: Fragile path for refactoring
        self.config_root = path.abspath(path.join(path.dirname(__file__), "../../../config", self.name))

    def deploy(self, config: Dict[str, object], kube_context: launch.KubeContext):
        ycsb_kubernetes_config_dir = template.get_tempdir_with_config(path.join(self.config_root, "kubernetes"), config)
        self.open_temp_dirs.append(ycsb_kubernetes_config_dir)  # TODO: This is only needed for the next line, clean up later?
        kube_context.apply_kubectl_yaml_config(ycsb_kubernetes_config_dir.name)

    def _set_database_name(self, config: Dict[str, object]):
        if self.target is configurator_enums.DBTarget.cassandra:
            config.update({
                "database_name": "cassandra-cql"
            })
            return
        if self.target is configurator_enums.DBTarget.spilo_postgres:
            config.update({
                "database_name": "jdbc"
            })
            return
        if self.target is configurator_enums.DBTarget.redis:
            config.update({
                "database_name": "redis"
            })
            return
        warnings.warn("Unable to set_database_name, no client match.")

    def _get_perdb_ycsb_config(self, config: Dict[str, object]):
        if self.target is configurator_enums.DBTarget.cassandra:
            return template.get_tempdir_with_config(path.join(self.config_root, "target_cassandra"), config)
        if self.target is configurator_enums.DBTarget.spilo_postgres:
            return template.get_tempdir_with_config(path.join(self.config_root, "target_spilo_postgres"), config)
        if self.target is configurator_enums.DBTarget.redis:
            return template.get_tempdir_with_config(path.join(self.config_root, "target_redis"), config)
        warnings.warn("Unable to get_perdb_ycsb_config, no client match.")

    def prepare(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        # Load in the configuration file
        ycsb_record_count = config["ycsb_record_count"]
        config.update(
            {
                "insertcount": (ycsb_record_count//len(pod_ids["ycsb"]))
            }
        )
        # FIXME: Move this to a cassandra-specific location
        if "ycsb_cassandra_readconsistency" not in config:
            config["ycsb_cassandra_readconsistency"] = "ONE" # Default for YCSB cassandra-cql
        if "ycsb_cassandra_writeconsistency" not in config:
            config["ycsb_cassandra_writeconsistency"] = "ONE" # Default for YCSB cassandra-cql
        self._set_database_name(config)
        for pod_idx, pod_id in enumerate(pod_ids["ycsb"]):
            config.update({
                "insertstart": (ycsb_record_count//len(pod_ids["ycsb"]))*pod_idx
            })
            ycsb_perdb_configuration_file_dir = self._get_perdb_ycsb_config(config)
            assert(ycsb_perdb_configuration_file_dir is not None)
            self.open_temp_dirs.append(ycsb_perdb_configuration_file_dir)
            kube_context.copy_to_pod(pod_id, ycsb_perdb_configuration_file_dir.name, "/properties/")
            ycsb_shared_configuration_file_dir = template.get_tempdir_with_config(path.join(self.config_root, "shared"), config)
            assert(ycsb_shared_configuration_file_dir is not None)
            self.open_temp_dirs.append(ycsb_shared_configuration_file_dir)
            kube_context.copy_to_pod(pod_id, ycsb_shared_configuration_file_dir.name, "/shared/")
        pass

    _result_parse_regex = re.compile(r'\[(?P<PKey>[^,]+)\],\s+(?P<SKey>[^,]+),\s+(?P<Value>.*)')
    _timeseries_parse_regex = re.compile(r'\[(?P<PKey>[^,]+)\],\s+(?P<Time>[\d\.]+),\s+(?P<Value>[\d\.]+)')

    def _parse_results(self, results_plaintext: str):
        contents = {}
        for match in self._result_parse_regex.finditer(results_plaintext):
            gd = match.groupdict()
            datastruct_utilities.update_nested(contents, [gd["PKey"], gd["SKey"]], gd["Value"])
        return contents

    def _parse_timeseries(self, results_plaintext: str):
        timeseries = {}
        for match in self._timeseries_parse_regex.finditer(results_plaintext):
            gd = match.groupdict()
            timestamp = float(gd["Time"])
            if timestamp not in timeseries:
                timeseries[timestamp] = {}
            timeseries[timestamp][gd["PKey"]] = float(gd["Value"])
        timeseries_data = []
        for timestamp, data in timeseries.items():
            data["Time"] = timestamp
            timeseries_data.append(data)
        return timeseries_data

    @staticmethod
    def _run_ycsb_perpod(kube_context: launch.KubeContext, pod_id: str):
        kube_context.run_command(pod_id, ["/bin/bash", "-e", "/shared/run.sh"])
        return kube_context.run_command(pod_id, ["cat", "/output/runresult"])

    def _extract_transform_output(self, unparsed_result_list: List[str], keyslist_constructorfunc_aggregationfunc_tuple: List[Tuple[List[str], Callable[..., T], Callable[[List[T]], T]]]):
        output_dict = {}
        parsed_results = [self._parse_results(result) for result in unparsed_result_list]
        for keys, constructor, aggregation in keyslist_constructorfunc_aggregationfunc_tuple:
            output_dict["_".join(keys)] = aggregation([constructor(datastruct_utilities.get_nested(parsed_result, keys)) for parsed_result in parsed_results])
        return output_dict

    def execute(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        # Run the test and save the results to memory
        wrapped_run_ycsb = functools.partial(self._run_ycsb_perpod, kube_context)
        print("Executing YCSB for namespace", kube_context.namespace_name)
        with threadprocessing.Pool(processes=len(pod_ids["ycsb"])) as thread_pool:
            results = thread_pool.map(wrapped_run_ycsb, pod_ids["ycsb"])
        # print("\n".join(results))
        ## Timeseries reporting. Removing timeseries metric for now to get 99 an 95% latency
        # try:
        #     for timeseries_datapoint in self._parse_timeseries(results[0]): # FIXME: just reports one client. Do something about this?
        #         tune.report(**timeseries_datapoint)
        # except Exception as e:
        #     warnings.warn("Unable to report to Tune. Here's the exception encountered.")
        #     print(e)
        # TODO: Determine more modular way to get results
        try:
            self.last_run_result = self._extract_transform_output(results,
                [
                    (
                        ["OVERALL", "Throughput(ops/sec)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["OVERALL", "RunTime(ms)"],
                        int,
                        statistics.mean
                    ),
                    (
                        ["READ", "AverageLatency(us)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["READ", "99thPercentileLatency(us)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["READ", "95thPercentileLatency(us)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["UPDATE", "AverageLatency(us)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["UPDATE", "99thPercentileLatency(us)"],
                        float,
                        statistics.mean
                    ),
                    (
                        ["UPDATE", "95thPercentileLatency(us)"],
                        float,
                        statistics.mean
                    ),
                ]
            )
        except Exception:
            raise Exception("Trials did not complete. YCSB output:\n{}".format("\n".join(results)))
        print("Reporting YCSB results for namespace:", kube_context.namespace_name)
        tune.report(**self.last_run_result)
        print("Finished reporting YCSB results for namespace:", kube_context.namespace_name)

    def get_experiment_results(self, config: Dict[str, object], kube_context: launch.KubeContext):
        print("Returning experiment results for namespace:", kube_context.namespace_name)
        return self.last_run_result
