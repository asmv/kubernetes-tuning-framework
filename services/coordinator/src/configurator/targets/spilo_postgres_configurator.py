from typing import List, Dict

from . import _target_configurator_base
from .. import configurator_enums

import template
import optimize
import launch

from os import path
import yaml
import warnings
import time
import re

class SpiloPostgresConfigurator(_target_configurator_base.TargetConfigurator):
    
    label = "spilo"
    identifier_type = launch.IdentifierType.application

    pod_fetch_dict = {
        "spilo": launch.IdentifierType.application
    }
    
    def __init__(self, client: 'DBClient'):
        super().__init__(client)
        # FIXME: Fragile path for refactoring
        self.config_root = path.abspath(path.join(path.dirname(__file__), "../../../config", "target_spilo_postgres"))

    def deploy(self, config: Dict[str, object], kube_context: launch.KubeContext):
        config.update({
            "namespace_name": kube_context.namespace_name
        })
        kubeconfig_dir = template.get_tempdir_with_config(path.join(self.config_root, "kubernetes"), config)
        self.open_temp_dirs.append(kubeconfig_dir) # TODO: This is only needed for the next line, clean up later?
        with open(path.join(kubeconfig_dir.name, "minimal-manifest.yaml"), "r+") as manifest_config:
            minimal_manifest_yaml = yaml.load(manifest_config, Loader=yaml.SafeLoader)
            postgresql_spec = minimal_manifest_yaml["spec"]["postgresql"]
            if "parameters" not in postgresql_spec:
                # convert to string since the postgresql crd spec only accepts string type
                postgresql_spec["parameters"] = {k: str(v) for k, v in config["dbconfig"].items()}
            else:
                postgresql_spec["parameters"].update({k: str(v) for k, v in config["dbconfig"].items()})
            manifest_config.seek(0)
            manifest_config.truncate(0)
            manifest_config.write(yaml.dump(minimal_manifest_yaml))
        # Waiting not necessary for CRD
        kube_context.apply_kubectl_yaml_config(path.join(kubeconfig_dir.name, "zalando", "manifests", "postgresql.crd.yaml"), wait_for_ready=False)
        time.sleep(1)
        kube_context.apply_kubectl_yaml_config(kubeconfig_dir.name, wait_for_ready=False)
        kube_context.apply_kubectl_yaml_config(path.join(kubeconfig_dir.name, "cluster-level-rbac-patch.yaml"), namespaced=False)
        # Need to wait manually because zalando postgres operator uses a CustomResourceDefinition that is not easily parseable to get StatefulSets
        kube_context._sts_wait("acid-minimal-cluster", config["replicas"])

    def prepare(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        if self.client is configurator_enums.DBClient.ycsb:
            assert(len(pod_ids["spilo"]) > 0)
            kube_context.copy_to_pod(pod_ids["spilo"][0], path.join(self.config_root, "client_ycsb", "init_table.sql"), "/init_table.sql")
            while re.search("error", kube_context.run_command(pod_ids["spilo"][0], ["psql", "-U", "postgres"])):
                time.sleep(1)
            kube_context.run_command(pod_ids["spilo"][0], ["psql", "-U", "postgres", "-f", "/init_table.sql"])
            if not re.search("now connected", kube_context.run_command(pod_ids["spilo"][0], ["psql", "-U", "postgres", "-c", r"\c test"])):
                raise Exception("Table did not properly initialize. Logs:\n{}".format(kube_context.kubectl_subprocess(["logs", pod_ids["spilo"][0]])))
            return
        warnings.warn("Unable to prepare, no client match.")

    def execute(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: Dict[str, List[str]]):
        if self.client is configurator_enums.DBClient.ycsb:
            # Not necessary to do anything once tables are configured for ycsb
            return
        warnings.warn("Unable to execute, no client match.")
