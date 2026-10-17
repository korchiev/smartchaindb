"""Real Ed25519 regressions, without importing the database/ABCI stack.

Run together with the isolated hardening tests using pytest --noconftest.
Only infrastructure imports are stubbed; transaction construction, hashing,
signatures, model dispatch and the shared security checks are real.
"""
import copy
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def security(monkeypatch):
    for name in list(sys.modules):
        if name == 'bigchaindb' or name.startswith('bigchaindb.'):
            monkeypatch.delitem(sys.modules, name)
    package = types.ModuleType('bigchaindb')
    package.__path__ = [str(ROOT / 'bigchaindb')]
    package.config = {'shacl': {'enabled': True, 'cache_enabled': True}}
    monkeypatch.setitem(sys.modules, 'bigchaindb', package)
    config_utils = types.ModuleType('bigchaindb.config_utils')
    monkeypatch.setitem(sys.modules, config_utils.__name__, config_utils)
    backend = types.ModuleType('bigchaindb.backend')
    backend.__path__ = []
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    schema = types.ModuleType('bigchaindb.backend.schema')
    schema.validate_language_key = lambda *a: None
    monkeypatch.setitem(sys.modules, schema.__name__, schema)
    base = importlib.import_module('bigchaindb.common.transaction')
    models = importlib.import_module('bigchaindb.models')
    crypto = importlib.import_module('bigchaindb.common.crypto')
    errors = importlib.import_module('bigchaindb.common.exceptions')
    for op in base.Transaction.ALLOWED_OPERATIONS:
        base.Transaction.register_type(op, models.Transaction)
    client = Mock(enabled=True, cache_enabled=True)
    client.validate_transaction.return_value = (True, [])
    monkeypatch.setattr(models, 'get_shacl_validator', lambda: client)
    monkeypatch.setattr(models, 'compute_dep_state', lambda *a: ('h', [], set()))
    state = {}
    chain = types.SimpleNamespace(is_committed=lambda _: False,
                                  get_transaction=state.get, get_spent=lambda *a: None)
    return types.SimpleNamespace(T=models.Transaction, base=base, crypto=crypto,
                                 errors=errors, client=client, state=state, chain=chain)


def signed_create(s, key=None):
    key = key or s.crypto.generate_key_pair()
    tx = s.T.create([key.public_key], [([key.public_key], 1)],
                    asset={'machineIdentifier': 'asset', 'capability': ['sell']},
                    metadata={'requestCreationTimestamp': '2026-10-17T00:00:00Z'}).sign([key.private_key])
    return tx, key


@pytest.mark.parametrize('enabled', [False, True])
def test_valid_signature_is_accepted_in_both_treatments(security, enabled):
    s = security
    tx, _ = signed_create(s)
    s.client.enabled = enabled
    assert tx.validate(s.chain) is tx


@pytest.mark.parametrize('enabled', [False, True])
def test_recomputed_hash_does_not_rescue_invalid_signature(security, enabled):
    s = security
    tx, _ = signed_create(s)
    body = copy.deepcopy(tx.to_dict())
    body['metadata']['tampered'] = True
    body['id'] = None
    body['id'] = s.base.Transaction._to_hash(s.base.Transaction._to_str(body))
    forged = s.T.from_dict(body)
    s.client.enabled = enabled
    with pytest.raises(s.errors.InvalidSignature):
        forged.validate(s.chain)
    s.client.validate_transaction.assert_not_called()


def test_claimed_actor_must_be_the_signer(security):
    s = security
    owner = s.crypto.generate_key_pair()
    thief = s.crypto.generate_key_pair()
    tx = s.T.update_adv(inputs=[s.base.Input.generate([thief.public_key])],
                        advertisement_id='a' * 64,
                        metadata={'updater_public_key': owner.public_key, 'status': 'OPEN'}).sign([thief.private_key])
    with pytest.raises(s.errors.InvalidSignature, match='authenticated signer'):
        tx.validate(s.chain)
    s.client.validate_transaction.assert_not_called()


def test_update_announcement_has_a_real_valid_signature(security):
    s = security
    key = s.crypto.generate_key_pair()
    tx = s.T.update_adv(inputs=[s.base.Input.generate([key.public_key])],
                        advertisement_id='a' * 64,
                        metadata={'updater_public_key': key.public_key, 'status': 'OPEN'}).sign([key.private_key])
    assert tx.validate(s.chain) is tx


def test_claimed_owner_list_is_bound_to_signature_condition(security):
    s = security
    tx, _ = signed_create(s)
    body = copy.deepcopy(tx.to_dict())
    body['inputs'][0]['owners_before'] = [s.crypto.generate_key_pair().public_key]
    body['id'] = None
    body['id'] = s.base.Transaction._to_hash(s.base.Transaction._to_str(body))
    forged = s.T.from_dict(body)
    with pytest.raises(s.errors.InvalidSignature, match='owners'):
        forged.validate(s.chain)


def test_spent_sale_is_rejected_before_sidecar_or_cache(security):
    s = security
    asset, seller = signed_create(s)
    buyer = s.crypto.generate_key_pair()
    s.state[asset.id] = asset
    tx = s.T.sell(asset.to_inputs(), asset.id, 'b' * 64, metadata={
        'seller_public_key': seller.public_key, 'buyer_public_key': buyer.public_key,
        'sale_amount': '100', 'sale_currency': 'USD'}).sign([seller.private_key])
    s.chain.get_spent = lambda *args: object()
    with pytest.raises(s.errors.DoubleSpend):
        tx.validate(s.chain)
    s.client.validate_transaction.assert_not_called()


def test_block_prefix_is_passed_and_not_cached(security):
    s = security
    tx, _ = signed_create(s)
    earlier, _ = signed_create(s)
    assert tx.validate(s.chain, [earlier]) is tx
    kwargs = s.client.validate_transaction.call_args.kwargs
    assert kwargs['dep_state_hash'] is None
    assert kwargs['pending_transactions'] == [earlier.to_dict()]


def test_uncached_shacl_does_not_materialize_a_cache_projection(security, monkeypatch):
    s = security
    tx, _ = signed_create(s)
    models = sys.modules['bigchaindb.models']
    compute = Mock(side_effect=AssertionError('projection should not be read'))
    monkeypatch.setattr(models, 'compute_dep_state', compute)
    s.client.cache_enabled = False
    assert tx.validate(s.chain) is tx
    compute.assert_not_called()


def make_sale(s, buyer_override=None):
    asset, seller = signed_create(s)
    buyer = s.crypto.generate_key_pair()
    escrow = s.crypto.generate_key_pair()
    offer = s.T.buy_offer(inputs=[s.base.Input.generate([buyer.public_key])],
        asset_id=asset.id, advertisement_id='a' * 64,
        metadata={'buyer_public_key': buyer.public_key, 'escrow_public_key': escrow.public_key,
                  'offer_amount': '100', 'offer_currency': 'USD',
                  'offer_timestamp': '2026-10-17T00:00:00Z', 'offer_expiry': '2030-01-01T00:00:00Z'}).sign([buyer.private_key])
    s.state.update({asset.id: asset, offer.id: offer})
    sale = s.T.sell(asset.to_inputs(), asset.id, offer.id, metadata={
        'seller_public_key': seller.public_key, 'buyer_public_key': buyer_override or buyer.public_key,
        'sale_amount': '100', 'sale_currency': 'USD'}).sign([seller.private_key])
    return sale


def test_valid_sale_with_real_spending_signature(security):
    s = security
    sale = make_sale(s)
    assert sale.validate(s.chain) is sale


def test_sale_cannot_substitute_a_different_buyer(security):
    s = security
    sale = make_sale(s, s.crypto.generate_key_pair().public_key)
    with pytest.raises(s.errors.ValidationError, match='asset and buyer'):
        sale.validate(s.chain)


def test_direct_duplicate_return_considers_block_prefix(security):
    s = security
    buyer = s.crypto.generate_key_pair()
    sale_id = 'b' * 64
    s.state[sale_id] = types.SimpleNamespace(operation='SELL', metadata={'buyer_public_key': buyer.public_key})
    s.chain.connection = types.SimpleNamespace(run=lambda q: q,
        collection=lambda _: types.SimpleNamespace(find=lambda *a: []))
    def request(reason):
        return s.T.request_return(inputs=[s.base.Input.generate([buyer.public_key])],
            asset_id='a' * 64, sell_transaction_id=sale_id,
            metadata={'requester_public_key': buyer.public_key, 'return_reason': reason,
                      'return_request_timestamp': '2026-10-17T00:00:00Z',
                      'return_policy_details': {'return_window_days': 30}}).sign([buyer.private_key])
    earlier, later = request('first'), request('second')
    s.client.enabled = False
    with pytest.raises(s.errors.ValidationError, match='already exists'):
        later.validate(s.chain, [earlier])


def test_null_fulfillment_is_rejected_as_validation_error(security):
    s = security
    tx, _ = signed_create(s)
    tx.inputs[0].fulfillment = None
    with pytest.raises(s.errors.ValidationError):
        tx.validate(s.chain)


@pytest.mark.parametrize('context, expires', [
    ('2029-12-31T19:00:00.499Z', False),
    ('2029-12-31T19:00:00.500Z', True),
    ('2029-12-31T19:00:00.501Z', True),
])
def test_direct_offer_expiry_preserves_offset_and_fraction(security, context, expires):
    s = security
    buyer, seller, escrow = [s.crypto.generate_key_pair() for _ in range(3)]
    ad_id, asset_id = 'a' * 64, 'b' * 64
    s.state[ad_id] = types.SimpleNamespace(operation='ADVERTISEMENT', asset={'id': asset_id},
        metadata={'status': 'OPEN', 'advertiser_public_key': seller.public_key})
    s.chain.get_effective_advertisement_status = lambda _: 'OPEN'
    s.chain._validation_time = context
    s.client.enabled = False
    tx = s.T.buy_offer(inputs=[s.base.Input.generate([buyer.public_key])],
        asset_id=asset_id, advertisement_id=ad_id, metadata={
            'buyer_public_key': buyer.public_key, 'escrow_public_key': escrow.public_key,
            'offer_amount': '100', 'offer_currency': 'USD',
            'offer_timestamp': '2026-10-17T00:00:00Z',
            'offer_expiry': '2030-01-01T00:00:00.500+05:00'}).sign([buyer.private_key])
    if expires:
        with pytest.raises(s.errors.ValidationError, match='expired'):
            tx.validate(s.chain)
    else:
        assert tx.validate(s.chain) is tx


@pytest.mark.parametrize('same_block', [False, True])
def test_complete_signed_workflow_through_real_shapes_and_state_rules(security, monkeypatch, same_block):
    """Integration across the actual Python converter and JavaScript engine.

    No live MongoDB/ABCI is needed. The HTTP boundary is replaced with a
    subprocess; its input contains the same normalized database documents.
    """
    import ast
    import json
    import subprocess
    from datetime import datetime, timedelta, timezone
    s = security
    now = datetime.now(timezone.utc)
    scope = {'Transaction': s.T, 'Input': s.base.Input,
             'generate_keypair': s.crypto.generate_key_pair,
             'NOW': now, 'timedelta': timedelta}
    driver = ast.parse((ROOT / 'eval/bdb_professor_eval.py').read_text())
    names = {'iso', 'gen_input', 'make_create', 'make_adv', 'make_update',
             'make_offer', 'make_sell', 'make_return', 'make_accept'}
    functions = [n for n in driver.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<workflow-builders>', 'exec'), scope)
    module = sys.modules['bigchaindb.common.shacl_validator']
    client = module.SHACLValidatorClient()
    client.cache_enabled = False
    client._loaded_shapes = set(module.REQUIRED_SHAPES)
    monkeypatch.setattr(sys.modules['bigchaindb.models'], 'get_shacl_validator', lambda: client)
    s.chain._validation_time = now.isoformat()

    def post(_url, *, json: object, **_kwargs):
        request = json
        import json as codec
        txs = [t.to_dict() for t in s.state.values()]
        records = {'transactions': [{k: v for k, v in t.items() if k != 'metadata'} for t in txs],
                   'metadata': [{'id': t['id'], 'metadata': t['metadata']} for t in txs]}
        p = subprocess.run(['node', str(ROOT / 'bigchaindb/backend/localshacl/shapes/tests/validate_request.mjs')],
                           input=codec.dumps({'request': request, 'records': records}),
                           text=True, capture_output=True, timeout=15, check=True)
        body = codec.loads(p.stdout)
        return types.SimpleNamespace(status_code=200, json=lambda: body)
    monkeypatch.setattr(module.requests, 'post', post)
    seller, buyer, escrow = [s.crypto.generate_key_pair() for _ in range(3)]
    prefix = []
    def accept(tx):
        parsed = s.T.from_dict(tx.to_dict())
        assert parsed.validate(s.chain, prefix) is parsed
        if same_block:
            prefix.append(parsed)
        else:
            s.state[tx.id] = parsed
        return parsed
    create = accept(scope['make_create'](seller, 'integration'))
    adv = accept(scope['make_adv'](seller, create.id))
    accept(scope['make_update'](seller, adv.id))
    offer = accept(scope['make_offer'](buyer, escrow, create.id, adv.id))
    sale = accept(scope['make_sell'](seller, buyer, create, create.id, offer.id))
    request = accept(scope['make_return'](buyer, create.id, sale.id))
    accept(scope['make_accept'](seller, create.id, request.id))
    assert len(prefix if same_block else s.state) == 7
