from meta import log

from .core import join_emoji, leave_emoji


async def joinleave_tracker(client, payload):
    if payload.user_id == client.user.id:
        return

    if payload.guild_id and (payload.emoji.name in (join_emoji, leave_emoji)):
        timers = client.interface.get_timers_in(payload.guild_id, payload.channel_id)
        timer = next((timer for timer in timers if payload.message_id in timer.message_ids), None)
        if timer:
            userid = payload.user_id
            guild = timer.channel.guild
            if payload.emoji.name == join_emoji and not client.interface.get_subscriber(userid, guild.id):
                member = guild.get_member(userid) or await guild.fetch_member(userid)

                # Subscribe member
                log("Reaction subscribing {}(uid:{}) in {}(gid:{}) to {}(rid:{})".format(
                    member, userid, guild, payload.guild_id, timer.data.name, timer.data.roleid
                ), context="TIMER_REACTIONS")
                await timer.subscribe(member, post=True)
            elif payload.emoji.name == leave_emoji and payload.user_id in timer:
                log("Reaction unsubscribing (uid:{}) in {}(gid:{}) from {}(rid:{})".format(
                    userid, guild, payload.guild_id, timer.data.name, timer.data.roleid
                ), context="TIMER_REACTIONS")
                await timer.unsubscribe(payload.user_id, post=True)
