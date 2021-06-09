from data import tables

from .core import Timer, TimerChannel


async def on_guild_join(client, guild):
    """
    (Re)-load the guild timers when we join a guild.
    """
    count = 0
    timer_rows = tables.timers.fetch_rows_where(guildid=guild.id)
    if timer_rows:
        timers = [Timer(row) for row in timer_rows]
        timers = [timer for timer in timers if timer.load()]

        channels = client.interface.guild_channels[guild.id] = {}
        for timer in timers:
            channel = channels.get(timer.channel.id, None)
            if channel is None:
                channel = channels[timer.channel.id] = TimerChannel(timer.channel)
            channel.timers.append(timer)
            count += 1

    client.log(
        "Joined new guild \"{}\" (gid: {}) and loaded {} pre-existing timers.".format(
            guild.name,
            guild.id,
            count
        )
    )


async def on_guild_remove(client, guild):
    """
    Unsubscribe and unload the guild timers when we leave a guild.
    """
    count = 0
    channels = client.interface.guild_channels.pop(guild.id, {})
    for channelid, tchannel in channels.items():
        for timer in tchannel.timers:
            count += 1
            timer.stop()
            for subber in timer.subscribers.values():
                subber.close_session()

    client.log(
        "Left guild \"{}\" (gid: {}) and cleaned up {} timers.".format(
            guild.name,
            guild.id,
            count
        )
    )
