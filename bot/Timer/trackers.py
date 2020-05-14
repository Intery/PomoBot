async def message_tracker(client, message):
    client.interface.bump_user(message.author.id, message.channel.id if message.guild else 0)


async def reaction_tracker(client, payload):
    client.interface.bump_user(payload.user_id, payload.channel_id if payload.guild_id else 0)
