"""Both safe parser backends preserve scientific-record parsing."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_variant(monkeypatch, use_c):
    if use_c and not hasattr(yaml, 'CSafeLoader'):
        pytest.skip('libyaml unavailable; pure safe fallback is separately covered')
    with monkeypatch.context() as patch:
        if not use_c:
            patch.delattr(yaml, 'CSafeLoader', raising=False)
        spec = importlib.util.spec_from_file_location('isolated_science_yaml_variant', ROOT / 'analysis/science_yaml.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def assert_typed_equal(left, right):
    assert type(left) is type(right)
    assert left == right
    if isinstance(left, dict):
        for key in left:
            assert_typed_equal(left[key], right[key])
    elif isinstance(left, list):
        for a, b in zip(left, right, strict=True):
            assert_typed_equal(a, b)


@pytest.mark.parametrize('use_c', [False, True])
def test_backend_selection_and_scalar_semantics(monkeypatch, use_c):
    module = load_variant(monkeypatch, use_c)
    assert issubclass(module.UniqueKeyLoader, yaml.CSafeLoader if use_c else yaml.SafeLoader)
    expected = {'flag':True, 'missing':None, 'integer':7, 'decimal':1.25,
                'quoted':'01', 'when':date(2026, 9, 28), 'items':['a', 'b']}
    actual = module.load_science_yaml('flag: true\nmissing: null\ninteger: 7\ndecimal: 1.25\nquoted: "01"\nwhen: 2026-09-28\nitems: [a, b]\n')
    assert_typed_equal(actual, expected)


@pytest.mark.parametrize('use_c', [False, True])
@pytest.mark.parametrize('payload', [
    'key: 1\nkey: 2\n', 'key: 1\nkey: 1\n',
    'outer:\n  key: 1\n  key: 2\n',
    'base: &base {key: 1}\nmerged: {<<: *base, key: 2}\n',
    'a: &a {key: 1}\nb: &b {key: 2}\nmerged: {<<: [*a, *b]}\n',
    'true: a\n1: b\n',
])
def test_duplicate_rejection_is_preserved(monkeypatch, use_c, payload):
    module = load_variant(monkeypatch, use_c)
    with pytest.raises(ValueError, match='Duplicate YAML key'):
        module.load_science_yaml(payload)


@pytest.mark.parametrize('use_c', [False, True])
@pytest.mark.parametrize('payload', ['broken: [', '!unknown value',
                                    '!!python/object:builtins.object {}',
                                    '!!python/object/apply:builtins.str [7]'])
def test_invalid_or_unsafe_yaml_is_rejected(monkeypatch, use_c, payload):
    module = load_variant(monkeypatch, use_c)
    with pytest.raises(yaml.YAMLError):
        module.load_science_yaml(payload)


def test_checked_in_science_payloads_have_typed_parser_parity(monkeypatch):
    pure = load_variant(monkeypatch, False)
    native = load_variant(monkeypatch, True)
    for kind in ['evidence', 'decisions', 'approvals']:
        directory = ROOT / 'data/science' / kind
        for path in sorted([*directory.rglob('*.yaml'), *directory.rglob('*.yml')]):
            content = path.read_text()
            assert_typed_equal(pure.load_science_yaml(content), native.load_science_yaml(content))


def test_c_rejection_never_retries_the_python_loader(monkeypatch):
    module = load_variant(monkeypatch, True)
    def forbidden_fallback(*args, **kwargs):
        raise AssertionError('A parse rejection must not select another backend')
    monkeypatch.setattr(yaml.SafeLoader, '__init__', forbidden_fallback)
    with pytest.raises(ValueError, match='Duplicate YAML key'):
        module.load_science_yaml('same: 1\nsame: 2\n')


@pytest.mark.parametrize('use_c', [False, True])
def test_valid_alias_and_nonconflicting_merge_are_preserved(monkeypatch, use_c):
    module = load_variant(monkeypatch, use_c)
    value = module.load_science_yaml('base: &base {first: 1}\ncopy: *base\nmerged: {<<: *base, second: 2}\n')
    assert_typed_equal(value, {'base':{'first':1}, 'copy':{'first':1}, 'merged':{'first':1, 'second':2}})
