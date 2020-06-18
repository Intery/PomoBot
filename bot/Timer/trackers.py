async def message_tracker(client, message):
    client.interface.bump_user(message.guild or 0, message.channel.id, message.author.id)


async def reaction_tracker(client, payload):
    client.interface.bump_user(payload.guild_id or 0,
                               payload.channel_id,
                               payload.user_id)
