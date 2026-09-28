"""Strict YAML mappings for immutable scientific approval records."""
import yaml


# Keep the same safe constructors and duplicate-key checks with either parser.
_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class UniqueKeyLoader(_SAFE_LOADER):
    """Reject ambiguous mappings instead of accepting last-key-wins input."""


def _mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'Duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_science_yaml(stream):
    return yaml.load(stream, Loader=UniqueKeyLoader)
