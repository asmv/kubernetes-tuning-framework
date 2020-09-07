from typing import List, Dict

from . import _target_configurator_base
from .. import configurator_enums

import template
import optimize
import launch

from os import path
import yaml
import warnings

class CassandraConfigurator(_target_configurator_base.TargetConfigurator):
    
    pod_fetch_dict = {
        "cassandra": launch.IdentifierType.app
    }

    name = "target_cassandra"
    label = "cassandra"
    ycsb_name = "cassandra-cql"
    cassandra_hparam_key = "cassandra_config"
    
    def __init__(self, client: 'DBClient'):
        super().__init__(client)
        # FIXME: Fragile path for refactoring
        self.config_root = path.abspath(path.join(path.dirname(__file__), "../../../config", self.name))

    def deploy(self, config: Dict[str, object], kube_context: launch.KubeContext):
        cassandra_params = {}
        for k, v in config["param_config"].items():
            try:
                _, parameter = k.split(":")
                cassandra_params[parameter] = v
            except Exception as e:
                warnings.warn(e)
                continue
        cassandra_yaml_param_string = ";".join(["{0}={1}".format(k, v) for k, v in cassandra_params.items()])
        # cassandra_yaml_param_string = ";".join(["{0}={1}".format(k, v if v is not None else "") for k, v in config["dbconfig"].items()])
        config.update({
            "namespace_name": kube_context.namespace_name,
            # "cassandra_yaml_bind_folder_path": cassandra_kubernetes_config_dir.name,
            "cassandra_yaml_param_string": cassandra_yaml_param_string
        })
        kubeconfig_dir = template.get_tempdir_with_config(path.join(self.config_root, "kubernetes"), config)
        self.open_temp_dirs.append(kubeconfig_dir) # TODO: This is only needed for the next line, clean up later?
        kube_context.apply_kubectl_yaml_config(kubeconfig_dir.name)

    def prepare(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        if self.client is configurator_enums.DBClient.ycsb:
            assert(len(pod_ids["cassandra"]) > 0)
            ycsb_init_file = template.get_tempfile_with_config(path.join(self.config_root, "client_ycsb", "init_table.cql.j2"), config)
            self.open_temp_dirs.append(ycsb_init_file)
            output = kube_context.run_command(pod_ids["cassandra"][0], ["cqlsh", "-e", ycsb_init_file.read()])
            return
        warnings.warn("Unable to prepare, no client match.")

    def execute(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        if self.client is configurator_enums.DBClient.ycsb:
            # Not necessary to do anything once tables are configured for ycsb
            return
        warnings.warn("Unable to execute, no client match.")
