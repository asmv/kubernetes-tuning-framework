from typing import Dict, List

from ray import tune
from ray.tune.suggest import ax as tune_ax
from ray.tune import schedulers
from ax.service import ax_client
from ax.modelbridge import strategies, Models, generation_strategy

import uuid
import functools
import enum
import re
import time
from os import path
import hashlib
import warnings

RAY_RESULTS_DIR = "/var/tmp/db_hparam_test/"

from ray.tune import commands
# https://stackoverflow.com/a/40169319
# A set that returns True for all "x in y" statements. Used as a workaround for Tune CLI removing keys unnecessarily
class AllSet(set):
    def __contains__(self, key):
        return True

class SchedulerType(enum.Enum):
    # # https://github.com/ray-project/ray/issues/9716 needs to be fixed before enabling schedulers, but enabling schedulers also 
    # AsyncHyperBand = schedulers.AsyncHyperBandScheduler
    NoScheduler = None

    def __repr__(self):
        return self.name

    @staticmethod
    def get(name):
        return SchedulerType[name]

class AxGenerationStrategy(enum.Enum):
    default = None
    sobol15_gpei = generation_strategy.GenerationStrategy([
        generation_strategy.GenerationStep(Models.SOBOL, num_trials=15, min_trials_observed=10, enforce_num_trials=False),
        generation_strategy.GenerationStep(Models.GPEI, num_trials=-1)])
    sobol15_botorch = generation_strategy.GenerationStrategy([
        generation_strategy.GenerationStep(Models.SOBOL, num_trials=15, min_trials_observed=10, enforce_num_trials=False),
        generation_strategy.GenerationStep(Models.BOTORCH, num_trials=-1)])

    def __repr__(self):
        return self.name

    @staticmethod
    def get(name):
        try:
            return AxGenerationStrategy[name]
        except KeyError:
            warnings.warn("Key for 'AxGenerationStrategy' not found, using default AxGenerationStrategy.")
            return AxGenerationStrategy.default

def wrap_func(testfunc, config, reporter):
    results = {"done": True}
    results.update(testfunc(config))
    reporter(**results)

class SearchAlgorithmType(enum.Enum):
    grid = "grid" # Better descriptor will be native_tune_search, but issue is that tune uniform, loguniform, random, etc. use lambdas (https://github.com/ray-project/ray/blob/master/python/ray/tune/sample.py#L33) and do not use values from a json object.
    axsearch = "axsearch"

    def __repr__(self):
        return self.name

    @staticmethod
    def get(name):
        return SearchAlgorithmType[name]

class Optimizer:

    def __init__(self, testfunc, experiment_name: str, parameter_config: Dict[str, object], search_algorithm_initialization: Dict[str, object], objective_name: str, objective_direction: str, search_algorithm_type: SearchAlgorithmType, scheduler_type: SchedulerType, concurrent_workers=4):
        self.wrapped_testfunc = functools.partial(wrap_func, testfunc)
        self.experiment_name = experiment_name
        self.objective_name = objective_name
        self.objective_direction = objective_direction
        self.concurrent_workers = concurrent_workers
        self.parameter_config = parameter_config
        self.search_algorithm = self._get_search_algorithm(search_algorithm_type, search_algorithm_initialization)
        self.scheduler = self._get_scheduler(scheduler_type)

    def _get_axseach(self, search_config):
        # https://github.com/facebook/Ax/issues/180
        try:
            generation_strat = AxGenerationStrategy.get(search_config["generation_strategy"])
        except KeyError:
            generation_strat = AxGenerationStrategy.default
            warnings.warn("'generation_strategy' not in config file under key 'search_algorithm_additional_configuration'. Using 'default' (argument-dependent) AxSearch Generation Strategy.\n\
            See https://ax.dev/api/_modules/ax/modelbridge/dispatch_utils.html#choose_generation_strategy for source code of this strategy.")
        client = ax_client.AxClient(enforce_sequential_optimization=False, 
            generation_strategy=generation_strat.value
        )
        client.create_experiment(parameters=self.parameter_config, objective_name=self.objective_name, minimize=self.objective_direction is "min")
        return tune_ax.AxSearch(client, max_concurrent=self.concurrent_workers)

    def _get_gridsearch(self, search_config):
        raise NotImplementedError()

    def _get_search_algorithm(self, search_algorithm_type: SearchAlgorithmType, search_algo_config: Dict[str, object]):
        if search_algorithm_type is SearchAlgorithmType.axsearch:
            return self._get_axseach(search_algo_config)
        elif search_algorithm_type is SearchAlgorithmType.grid:
            return self._get_gridsearch(search_algo_config)

    def _get_scheduler(self, scheduler_class: SchedulerType):
        if scheduler_class is SchedulerType.NoScheduler:
            return None
        else:
            return scheduler_class.value(metric=self.objective_name, mode=self.objective_direction)

    def _export_tune_experiment(self, export_directory, output_file="out.csv"):
        tmpkeys = commands.DEFAULT_CLI_KEYS
        commands.DEFAULT_CLI_KEYS = AllSet()
        commands.list_trials(path.join(export_directory, self.experiment_name), output=path.join(export_directory, output_file))
        commands.DEFAULT_CLI_KEYS = tmpkeys

    def run(self, run_config: Dict[str, object], export_directory=None, resume=False):
        try:
            return tune.run(
                self.wrapped_testfunc, 
                name=self.experiment_name, 
                search_alg=self.search_algorithm, # TODO: Not all algorithms have this as a kwarg, make the _get_search_algorithm argument modify a self.run_algorithm_kwargs dictionary and insert into tune.run
                scheduler=self.scheduler,
                raise_on_failed_trial=False,   
                local_dir=export_directory,
                resume=False, # False because https://github.com/ray-project/ray/issues/8312
                checkpoint_freq=0,
                **run_config
            )
        except KeyboardInterrupt:
            pass
            # TODO: Figure out if something else needs to be done here
        finally:
            if export_directory:
                self._export_tune_experiment(export_directory, "{0}_{1}.csv".format(self.experiment_name, int(time.time())))