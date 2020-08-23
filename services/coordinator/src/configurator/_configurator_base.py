from typing import Dict, List

import template
import launch

class Configurator:

    # Set these in subclasses
    label = None
    identifier_type = None

    def __init__(self):
        self.config_root = None

    def __enter__(self):
        self.open_temp_dirs = []
        return self

    def __exit__(self, type, value, traceback):
        for open_temp_dir in self.open_temp_dirs:
            open_temp_dir.__exit__(type, value, traceback)

    def deploy(self, config: Dict[str, object], kube_context: launch.KubeContext):
        raise NotImplementedError()

    def prepare(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: List[str]):
        raise NotImplementedError()

    def execute(self, config: Dict[str, object], kube_context: launch.KubeContext, pod_ids: List[str]):
        raise NotImplementedError()

    ### TODO: Below is old code, delete

    def get_kubernetes_config(self, hparams: Dict[str, object]):
        return {}

    def get_kubernetes_yaml(self, config: Dict[str, object] = {}):
        temp_yaml = template.get_tempdir_with_config(self.config_root, config)
        self.open_temp_dirs.append(temp_yaml)
        return temp_yaml.name

    def get_configs(self, pod_idx: int, pod_ids: List[str], config: Dict[str, object] = {}) -> Dict[str, str]:
        """
        Returns a mpping of local folder to container directory mappings for use by the `docker cp` or `kubectl cp` commands.

        Args:
            pod_idx (int): The number of the current pod.
            pod_count (int): The total number of client pods.
            pod_ids (List[str]): A list of ids by pod. The current pod's id can be found by indexing pod_ids[pod_idx]

        Returns:
            Dict[str, str]: [A mapping of local filepath -> container directory target for any required config files.]
        """
        raise NotImplementedError("Implement this function in derived class.")

    def get_run_commands(self, pod_idx: int, pod_ids: List[str], config: Dict[str, object] = {}) -> List[str]:
        raise NotImplementedError("Implement this function in derived class.")