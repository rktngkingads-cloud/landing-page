import asyncio

from cooldown import ReplyCooldown


def test_latest_pending_reply_replaces_previous_one():
    async def scenario():
        sent: list[tuple[str, str]] = []

        async def sender(recipient: str, message: str) -> None:
            sent.append((recipient, message))

        limiter = ReplyCooldown(0.02, 0.02)
        limiter.schedule("60123456789", "first", sender)
        await asyncio.sleep(0.005)
        limiter.schedule("60123456789", "latest", sender)
        await asyncio.sleep(0.04)
        await limiter.shutdown()

        assert sent == [("60123456789", "latest")]

    asyncio.run(scenario())


def test_different_recipients_are_independent():
    async def scenario():
        sent: list[tuple[str, str]] = []

        async def sender(recipient: str, message: str) -> None:
            sent.append((recipient, message))

        limiter = ReplyCooldown(0.01, 0.01)
        limiter.schedule("60111111111", "one", sender)
        limiter.schedule("60222222222", "two", sender)
        await asyncio.sleep(0.03)
        await limiter.shutdown()

        assert sorted(sent) == [
            ("60111111111", "one"),
            ("60222222222", "two"),
        ]

    asyncio.run(scenario())
