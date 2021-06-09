import asyncio

from meta import log


async def vc_update_handler(client, member, before, after):
    if before.channel != after.channel:
        if member.bot:
            return

        voice_channels = {
            timer.voice_channel.id: timer
            for timer in client.interface.get_timers_in(member.guild.id)
            if timer.voice_channel
        }
        left = voice_channels.get(before.channel.id, None) if before.channel else None
        joined = voice_channels.get(after.channel.id, None) if after.channel else None

        leave = (left and member.id in left and left.data.track_voice_join is not False)
        join = (
            joined and
            joined.data.track_voice_leave is not False and
            (leave or not client.interface.get_subscriber(member.id, member.guild.id))
        )
        existing_sub = None
        if leave:
            # TODO: Improve hysterisis, with locks maybe?
            # TODO: Maybe add a personal ignore_voice setting
            # Briefly wait to handle connection issues
            if not after.channel:
                await asyncio.sleep(5)
                if member.voice and member.voice.channel:
                    return
            log("Voice unsubscribing {}(uid:{}) in {}(gid:{}) from {}(rid:{})".format(
                member, member.id, member.guild, member.guild.id, left.data.name, left.data.roleid
            ), context="TIMER_REACTIONS")
            existing_sub = await left.unsubscribe(member.id, post=not join)

        if join:
            log("Voice subscribing {}(uid:{}) in {}(gid:{}) to {}(rid:{})".format(
                member, member.id, member.guild, member.guild.id, joined.data.name, joined.data.roleid
            ), context="TIMER_REACTIONS")
            new_sub = await joined.subscribe(member, post=True)
            if existing_sub:
                new_sub.clocked_time = existing_sub.clocked_time
