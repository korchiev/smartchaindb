"""Pure regression tests for deterministic time and the Python block view."""
import importlib.util
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    path = ROOT / 'bigchaindb/common' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

clock = load('validation_context')
state = load('ledger_state')


def test_timestamp_offsets_describe_the_same_time():
    assert clock.timestamp_seconds('2026-10-17T11:00:00+05:00') == clock.timestamp_seconds('2026-10-17T06:00:00.000Z')


def test_context_requires_an_explicit_timezone():
    with pytest.raises(ValueError):
        clock.timestamp_seconds('2026-10-17T06:00:00')


def test_block_timestamp_uses_the_sidecars_millisecond_resolution():
    stamp = SimpleNamespace(seconds=100, nanos=123999999)
    assert clock.timestamp_seconds(clock.block_validation_time(stamp)) == 100.123


def test_pending_close_is_in_the_python_effective_state():
    ad = SimpleNamespace(id='ad', metadata={'status': 'OPEN'})
    update = SimpleNamespace(id='update', operation='UPDATE_ADV', metadata={'status': 'CLOSED'},
                             to_dict=lambda: {'asset': {'data': {'id': 'ad'}}})
    base = SimpleNamespace(get_transaction=lambda _: ad, get_effective_advertisement_status=lambda _: 'OPEN')
    view = state.LedgerStateView(base, [update])
    assert view.get_effective_advertisement_status('ad') == 'CLOSED'


def test_referencing_query_sees_an_earlier_return_in_the_block():
    tx = SimpleNamespace(id='return', operation='REQUEST_RETURN',
                         to_dict=lambda: {'asset': {'data': {'sell_transaction_id': 'sale'}}})
    base = SimpleNamespace(connection=SimpleNamespace(run=lambda value: value,
        collection=lambda _: SimpleNamespace(find=lambda *args: [])))
    view = state.LedgerStateView(base, [tx])
    assert view.referencing_transactions('REQUEST_RETURN', 'asset.data.sell_transaction_id', 'sale') == [tx]


def core_method(name):
    """Execute the actual ABCI method without importing unavailable services."""
    tree = ast.parse((ROOT / 'bigchaindb/core.py').read_text())
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
    method = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {'logger': Mock(), '_apply_shacl_stats_reset': lambda: None,
             'decode_transaction': lambda value: value, 'CodeTypeError': 1}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-abci-method>', 'exec'), scope)
    return scope[name]


@pytest.mark.parametrize('fails', [False, True])
def test_check_tx_uses_speculative_time_and_restores_block_clock(fails):
    chain = SimpleNamespace(_validation_time='block-time')
    def validate(_):
        assert chain._validation_time is None
        if fails:
            raise RuntimeError('unavailable')
        return False
    chain.is_valid_transaction = validate
    app = SimpleNamespace(bigchaindb=chain, abort_if_abci_chain_is_not_synced=lambda: None,
                          abci=SimpleNamespace(ResponseCheckTx=lambda **kwargs: kwargs))
    if fails:
        with pytest.raises(RuntimeError, match='unavailable'):
            core_method('check_tx')(app, {})
    else:
        assert core_method('check_tx')(app, {}) == {'code': 1}
    assert chain._validation_time == 'block-time'


def test_deliver_tx_requires_begin_block_time():
    app = SimpleNamespace(bigchaindb=SimpleNamespace(), abort_if_abci_chain_is_not_synced=lambda: None)
    with pytest.raises(RuntimeError, match='BeginBlock'):
        core_method('deliver_tx')(app, {})
