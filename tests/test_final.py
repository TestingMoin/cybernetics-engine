from cybernetics.dhan.execution_bridge import build_dhan_execution_bridge
from cybernetics.dhan.payload import DhanOrderPayload
from cybernetics.dhan.submission import DhanSubmissionState
from cybernetics.integration.dhan_runtime import DhanTransportError

class FakeTransport:
    def __init__(self, mode="success"):
        self.mode = mode
        self.calls = 0
    def post_json(self, *, path, headers, json_body):
        self.calls += 1
        if self.mode == "timeout":
            raise DhanTransportError("dhan_transport_failed",)
        return {"orderId": "TEST-136", "orderStatus": "PENDING"}

payload = DhanOrderPayload(
    dhanClientId="TEST",
    correlationId="CTE-TEST136",
    transactionType="BUY",
    exchangeSegment="MCX_COMM",
    productType="INTRADAY",
    orderType="MARKET",
    validity="DAY",
    securityId="576388",
    quantity=1,
)

# 1. Safe default blocks.
t = FakeTransport()
b = build_dhan_execution_bridge(
    client_id="TEST",
    transport=t,
    access_token_provider=lambda: "TOKEN",
)
r = b.submission.submit(payload)
assert r.state is DhanSubmissionState.BLOCKED
assert r.reason == "emergency_stop_active"
assert t.calls == 0

# 2. Submission disabled blocks.
t = FakeTransport()
b = build_dhan_execution_bridge(
    client_id="TEST",
    transport=t,
    access_token_provider=lambda: "TOKEN",
    engine_running=True,
    live_authorized=True,
    emergency_stop=False,
    order_submission_enabled=False,
)
r = b.submission.submit(payload)
assert r.state is DhanSubmissionState.BLOCKED
assert r.reason == "order_submission_disabled"
assert t.calls == 0

# 3. Timeout/uncertainty is UNKNOWN and is not retried.
class TimeoutTransport:
    def __init__(self):
        self.calls = 0
    def post_json(self, *, path, headers, json_body):
        self.calls += 1
        raise DhanTransportError("dhan_transport_failed",)
        
t = TimeoutTransport()
# Inject the underlying timeout cause exactly as the stdlib transport does.
def uncertain_post_json(*, path, headers, json_body):
    err = DhanTransportError("dhan_transport_failed:TimeoutError")
    err.__cause__ = TimeoutError()
    t.calls += 1
    raise err

t.post_json = uncertain_post_json

b = build_dhan_execution_bridge(
    client_id="TEST",
    transport=t,
    access_token_provider=lambda: "TOKEN",
    engine_running=True,
    live_authorized=True,
    emergency_stop=False,
    order_submission_enabled=True,
)
r = b.submission.submit(payload)
assert r.state is DhanSubmissionState.UNKNOWN
assert r.reason == "transport_uncertain_no_retry"
assert t.calls == 1

# 4. Safe synthetic success through fake transport only.
t = FakeTransport()
b = build_dhan_execution_bridge(
    client_id="TEST",
    transport=t,
    access_token_provider=lambda: "TOKEN",
    engine_running=True,
    live_authorized=True,
    emergency_stop=False,
    order_submission_enabled=True,
)
r = b.submission.submit(payload)
assert r.state is DhanSubmissionState.SUBMITTED
assert r.broker_order_id == "TEST-136"
assert t.calls == 1

print("CHUNK136_FINAL_TESTS=4/4_PASS")
print("SAFE_DEFAULT_BLOCK=PASS")
print("SUBMISSION_DISABLED_BLOCK=PASS")
print("TIMEOUT_UNKNOWN_NO_RETRY=PASS")
print("FAKE_TRANSPORT_SUCCESS=PASS")
print("REAL_NETWORK_CALLS=0")
print("LIVE_ORDERS=0")
