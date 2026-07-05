import asyncio

from cooldown import ReplyCooldown


def test_latest_pending_reply_replaces_previous_one():
    async def scenario():
        sent: list[tuple[str, str]] = []
        delivered = asyncio.Event()

        async def sender(recipient: str, message: str) -> None:
            sent.append((recipient, message))
            delivered.set()

        limiter = ReplyCooldown(0.02, 0.02)
        limiter.schedule("60123456789", "first", sender)
        await asyncio.sleep(0.005)
        limiter.schedule("60123456789", "latest", sender)

        await asyncio.wait_for(delivered.wait(), timeout=1.0)
        await limiter.shutdown()

        assert sent == [("60123456789", "latest")]

    asyncio.run(scenario())


def test_different_recipients_are_independent():
    async def scenario():
        sent: list[tuple[str, str]] = []
        both_delivered = asyncio.Event()

        async def sender(recipient: str, message: str) -> None:
            sent.append((recipient, message))
            if len(sent) == 2:
                both_delivered.set()

        limiter = ReplyCooldown(0.01, 0.01)
        limiter.schedule("60111111111", "one", sender)
        limiter.schedule("60222222222", "two", sender)

        await asyncio.wait_for(both_delivered.wait(), timeout=1.0)
        await limiter.shutdown()

        assert sorted(sent) == [
            ("60111111111", "one"),
            ("60222222222", "two"),
        ]

    asyncio.run(scenario())
