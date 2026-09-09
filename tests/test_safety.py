from cybernetics.dhan.execution_bridge import build_dhan_execution_bridge
from cybernetics.dhan.payload import DhanOrderPayload
from cybernetics.dhan.submission import DhanSubmissionState

class FakeTransport:
    def __init__(self):
        self.calls = []
    def post_json(self, *, path, headers, json_body):
        self.calls.append((path, headers, json_body))
        return {"orderId": "TEST-ORDER-136", "orderStatus": "PENDING"}

payload = DhanOrderPayload(
    dhanClientId="TESTCLIENT",
    correlationId="CTE-TEST136",
    transactionType="BUY",
    exchangeSegment="MCX_COMM",
    productType="INTRADAY",
    orderType="MARKET",
    validity="DAY",
    securityId="576388",
    quantity=1,
)

t = FakeTransport()

tests = [
    ({}, "emergency_stop_active"),
    ({
        "engine_running": True,
        "live_authorized": False,
        "emergency_stop": False,
        "order_submission_enabled": True,
    }, "live_authorization_missing"),
    ({
        "engine_running": True,
        "live_authorized": True,
        "emergency_stop": False,
        "order_submission_enabled": False,
    }, "order_submission_disabled"),
]

for kwargs, expected in tests:
    b = build_dhan_execution_bridge(
        client_id="TESTCLIENT",
        transport=t,
        access_token_provider=lambda: "TESTTOKEN",
        **kwargs,
    )
    r = b.submission.submit(payload)
    assert r.state is DhanSubmissionState.BLOCKED
    assert r.reason == expected

b = build_dhan_execution_bridge(
    client_id="TESTCLIENT",
    transport=t,
    access_token_provider=lambda: "TESTTOKEN",
    engine_running=True,
    live_authorized=True,
    emergency_stop=False,
    order_submission_enabled=True,
)
r = b.submission.submit(payload)

assert r.state is DhanSubmissionState.SUBMITTED
assert r.broker_order_id == "TEST-ORDER-136"
assert len(t.calls) == 1
assert t.calls[0][0] == "/v2/orders"

print("CHUNK136_SOURCE_IMPORT=PASS")
print("CHUNK136_SAFETY_TESTS=4/4_PASS")
print("CHUNK136_NETWORK_CALLS=0")
print("CHUNK136_LIVE_ORDERS=0")
