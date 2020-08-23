#!/usr/local/bin/python3

import argparse
import yaml

def modify_yaml(yaml_to_modify, params):
    print("modify_cassandra_yaml.py setting:", params)
    with open(yaml_to_modify, "r+") as yaml_file:
        yaml_contents = yaml.load(yaml_file, Loader=yaml.SafeLoader)
        for key, value in params.items():
            if value is None and key in yaml_contents:
                del yaml_contents[key] # TODO: Keep this behavior when set to None, or be more explicit?
            else:
                yaml_contents[key] = value
        yaml_file.seek(0)
        yaml_file.truncate(0)
        yaml_file.write(yaml.dump(yaml_contents))

def extract_params(env_param_string, param_delimiter, k_v_delimeter="="):
    params = {}
    for param_k_v in env_param_string.split(param_delimiter):
        if param_k_v == "":
            continue
        k, v = param_k_v.split(k_v_delimeter)
        if v == "":
            v = None
        params[k] = v
    return params

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml_to_modify", help="Yaml file to template.")
    parser.add_argument("params", help="Delimited parameter variable string.")
    parser.add_argument('-d', dest="param_delimiter", default=";", help="Delimiter defining boundary between parameters.")
    args = parser.parse_args()
    modify_yaml(args.yaml_to_modify, extract_params(args.params, param_delimiter=args.param_delimiter))
