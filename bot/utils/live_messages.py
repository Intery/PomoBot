import asyncio

from meta import client

current_live = {}  # token -> task


async def live_edit(msg, update_func, label='global', update_interval=5, max_distance=20, **kwargs):
    if not msg:
        msg = await update_func(None, **kwargs)
        if not msg:
            return

    token = (msg.channel.id, label)
    task = current_live.pop(token, None)
    if task is not None:
        task.cancel()

    task = current_live[token] = asyncio.create_task(_message_counter(msg, max_distance))
    while not task.done():
        await asyncio.sleep(update_interval)
        if await update_func(msg, **kwargs) is None:
            task.cancel()


async def _message_counter(msg, max_count):
    count = 0
    while count < max_count:
        try:
            await client.wait_for('message', check=lambda m: m.channel == msg.channel)
        except asyncio.CancelledError:
            break
        count += 1
