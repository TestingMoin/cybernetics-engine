from cybernetics.reconcile.dhan_runtime import DhanPostgresReconciliationAdapter

def check_preexisting_duplicate_nonzero_is_detected():
    rows=[
        {"tradingSymbol":"CRUDEOIL-17Sep2026-9000-CE","exchangeSegment":"MCX_COMM","securityId":"576388","netQty":0},
        {"tradingSymbol":"CRUDEOIL-17Sep2026-9000-CE","exchangeSegment":"MCX_COMM","securityId":"576388","netQty":1},
    ]
    issues=DhanPostgresReconciliationAdapter._reconcile_positions([],rows)
    assert any(i["kind"]=="PREEXISTING_BROKER_POSITION" for i in issues), issues
    print("DUPLICATE_NONZERO_POSITION_GUARD=PASS")

if __name__=="__main__": check_preexisting_duplicate_nonzero_is_detected()
