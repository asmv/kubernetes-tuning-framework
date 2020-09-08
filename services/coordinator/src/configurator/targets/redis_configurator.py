from typing import List, Dict

from . import _target_configurator_base
from .. import configurator_enums

import template
import optimize
import launch

from os import path
import yaml
import warnings

class RedisConfigurator(_target_configurator_base.TargetConfigurator):
    
    pod_fetch_dict = {
        "redis": launch.IdentifierType.app
    }

    name = "target_redis"
    ycsb_name = "redis"
    
    def __init__(self, client: 'DBClient'):
        super().__init__(client)
        # FIXME: Fragile path for refactoring
        self.config_root = path.abspath(path.join(path.dirname(__file__), "../../../config", self.name))

    def deploy(self, config: Dict[str, object], kube_context: launch.KubeContext):
        for k, v in config["param_config"].items():
            try:
                _, param = k.split(":")
                config["redis_config"][param] = v
            except Exception as e:
                warnings.warn("Unrecognized parameter: {}".format(k))
                continue
        config.update({
            "cluster_enabled_yesno": "yes" if config["redis_replicas"] > 1 else "no",
            "cluster_enabled_truefalse": "true" if config["redis_replicas"] > 1 else "false",
            "namespace_name": kube_context.namespace_name,
            "config_items": "\n".join(["{0} {1}".format(key, value) for key, value in config["redis_config"].items()])
        })
        kubeconfig_dir = template.get_tempdir_with_config(path.join(self.config_root, "kubernetes"), config)
        self.open_temp_dirs.append(kubeconfig_dir) # TODO: This is only needed for the next line, clean up later?
        kube_context.apply_kubectl_yaml_config(kubeconfig_dir.name)

    def prepare(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        pod_ips_ports = kube_context.kubectl_subprocess(["get", "pods", "-l", "app=redis", "-o", r"jsonpath={range.items[*]}{.status.podIP}:6379 "])
        if config["redis_replicas"] > 1: # enable cluster mode if > 1 replica
            # if "cluster_replicas" not in config:
            #     config["cluster_replicas"] = 0
            # # TODO: Slave replicas for every master node currently not supported. Will need to change config to have non-master nodes. Change the below line to this `format(config["cluster_replicas"]` from `format(0`.
            # # This means that redis clusters are sharded but not HA. Will need to add support for this later.
            cluster_create_output = kube_context.run_command(pod_ids["redis"][0], ["bash", "-c", "yes yes | redis-cli --cluster create --cluster-replicas {0} {1}".format(0, pod_ips_ports)])
        # TODO: Check output to see if cluster create was successful
        if self.client is configurator_enums.DBClient.ycsb:
            return 
        warnings.warn("Unable to prepare, no client match.")

    def execute(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        if self.client is configurator_enums.DBClient.ycsb:
            # Not necessary to do anything once tables are configured for ycsb
            return
        warnings.warn("Unable to execute, no client match.")
