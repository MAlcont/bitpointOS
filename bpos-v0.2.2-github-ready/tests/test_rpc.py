import asyncio
from bpos.bitcoin_rpc import BitcoinRPC
from bpos.crypto import generate_private_key, public_hex, sign_event
from bpos.engine import Engine
from bpos.model import ipayntity_for
from bpos.miner import review_block_template


def registered_engine():
    engine = Engine()
    key = generate_private_key()
    pub = public_hex(key)
    body = {"outpoint": "a" * 64 + ":7", "device_pubkey": pub,
            "ipayntity": ipayntity_for(pub), "mode": "veto_window", "delay_blocks": 6}
    pid = engine.apply_event(sign_event("enroll", body, key))["policy_id"]
    return engine, pid, key


def test_bitcoin_core_watcher_observes_registered_outpoint():
    engine, pid, _ = registered_engine()
    class StubBitcoinCore(BitcoinRPC):
        async def call(self, method, params=None):
            if method == "getblockcount":
                return 150
            if method == "gettxspendingprevout":
                assert params == [[{"txid": "a" * 64, "vout": 7}], {"mempool_only": True}]
                return [{"txid": "a" * 64, "vout": 7, "spendingtxid": "b" * 64}]
            raise AssertionError(method)
    statuses = asyncio.run(StubBitcoinCore("", "", "").scan(engine))
    assert statuses[0]["state"] == "VETO_WINDOW_OPEN"
    assert statuses[0]["deadline_height"] == 156
    engine.close()


def test_template_review_inspects_actual_spending_inputs():
    engine, pid, key = registered_engine()
    engine.set_height(200)
    engine.apply_event(sign_event("veto", {"policy_id": pid, "txid": "b" * 64}, key))
    class StubRPC:
        async def call(self, method, params=None):
            if method == "getblocktemplate":
                assert params == [{"rules": ["segwit"]}]
                return {"height": 201, "transactions": [{"data": "01000000"}]}
            if method == "decoderawtransaction":
                return {"txid": "b" * 64, "vin": [{"txid": "a" * 64, "vout": 7}]}
            raise AssertionError(method)
    report = asyncio.run(review_block_template(StubRPC(), engine))
    assert report["flagged"][0]["state"] == "OWNER_VETO"
    assert not report["template_modified"]
    assert not report["bitcoin_consensus_enforced"]
    engine.close()


def test_empty_template_review():
    engine = Engine()
    class StubRPC:
        async def call(self, method, params=None):
            assert method == "getblocktemplate"
            return {"height": 5, "transactions": []}
    report = asyncio.run(review_block_template(StubRPC(), engine))
    assert report["flagged"] == []
    engine.close()
