from typing import List, Dict

def get_nested(nested_dict: Dict[str, object], keys: List[str]):
    if len(keys) == 1:
        return nested_dict[keys[0]] if keys[0] in nested_dict else None
    elif len(keys) > 1:
        if keys[0] not in nested_dict:
            return None
        return get_nested(nested_dict[keys[0]], keys[1:])

def update_nested(nested_dict: Dict[str, object], keys: List[str], value=None, delkey=False):
    if not issubclass(type(nested_dict), dict):
        raise ValueError("{0} Is not a dictionary.".format(nested_dict))
    if len(keys) == 1:
        if delkey:
            del nested_dict[keys[0]]
            return
        if keys[0] not in nested_dict:
            nested_dict[keys[0]] = value
    else:
        if keys[0] not in nested_dict:
            if delkey:
                raise KeyError("Key {0} does not exist in dictionary, unable to delete.".format(keys[0]))
            nested_dict[keys[0]] = {}
        update_nested(nested_dict[keys[0]], keys[1:], value, delkey)