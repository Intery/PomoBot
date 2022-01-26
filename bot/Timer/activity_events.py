async def message_tracker(client, message):
    if message.guild:
        sub = client.interface.get_subscriber(message.author.id, message.guild.id)
        if sub and sub.timer.channel == message.channel:
            sub.touch()
            if not sub.member:
                sub.set_member(message.author)


async def reaction_tracker(client, payload):
    if payload.guild_id:
        sub = client.interface.get_subscriber(payload.user_id, payload.guild_id)
        if sub and sub.timer.channel.id == payload.channel_id:
            sub.touch()
