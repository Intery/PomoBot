async def message_tracker(client, message):
    client.interface.bump_user(message.author.id, message.channel.id if message.guild else 0)


async def reaction_tracker(client, reaction, user):
    message = reaction.message
    client.interface.bump_user(user.id, message.channel.id if message.guild else 0)
