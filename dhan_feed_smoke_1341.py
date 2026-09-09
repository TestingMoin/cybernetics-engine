import asyncio
from cybernetics.auth.secret_provider import FileSecretProvider
from cybernetics.market_data.live_client import DhanLiveFeedClient, DhanLiveFeedConfig
from cybernetics.market_data.dhan_live_feed import decode_message
from cybernetics.websocket.dhan_websocket_transport import dhan_websocket_factory
from cybernetics.websocket.subscriptions import Instrument, SubscriptionMode


async def main():
    provider = FileSecretProvider("/opt/cybernetics-engine/secrets")

    client = DhanLiveFeedClient(
        DhanLiveFeedConfig(
            client_id=provider.get("dhan_client_id"),
            secret_provider=provider,
        ),
        dhan_websocket_factory,
        shard_id=1,
    )

    # One known MCX instrument only; read-only market-data subscription.
    client.set_instruments(
        [Instrument("MCX_COMM", "576388")],
        SubscriptionMode.TICKER,
    )

    print("SMOKE=CONNECTING")

    try:
        await client.connect_once()
        print("SMOKE=CONNECTED")

        received = 0
        for _ in range(5):
            message = await asyncio.wait_for(client._socket.recv(), timeout=12)
            if not isinstance(message, (bytes, bytearray, memoryview)):
                print("SMOKE=NON_BINARY")
                continue

            ticks = decode_message(bytes(message))
            print("SMOKE=PACKET",
                  "bytes=", len(message),
                  "ticks=", len(ticks))

            for tick in ticks:
                print(
                    "TICK",
                    "kind=", tick.kind,
                    "segment=", tick.header.exchange_segment,
                    "security=", tick.header.security_id,
                    "ltp=", tick.ltp,
                )
                received += 1

            if received:
                break

        print("SMOKE=PASS" if received else "SMOKE=CONNECTED_NO_DECODED_TICK")

    except Exception as exc:
        print("SMOKE=FAIL")
        print("ERROR_TYPE=", type(exc).__name__)
        print("ERROR=", str(exc)[:300])

    finally:
        await client.stop()


asyncio.run(main())
