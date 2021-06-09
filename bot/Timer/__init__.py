import os
import shutil
import logging
import asyncio
import pickle

import discord
from cmdClient import Module
from cmdClient.Context import Context

from meta import log
from data import tables

from .lib import TimerState, NotifyLevel, InvalidPattern  # noqa
from .core import Timer, TimerSubscriber, TimerChannel, Pattern  # noqa
from . import activity_events
from . import timer_reactions
from . import voice_events
from . import guild_events


class TimerInterface(Module):
    name = "TimerInterface"
    save_dir = "data/timerstatus/"
    save_fn = "timerstatus.pickle"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.guild_channels = {}  # guildid -> {channelid -> TimerChannel}

        self.init_task(self.core_init)
        self.launch_task(self.core_launch)

    def core_init(self, _client):
        _client.interface = self
        Context.timers = module
        _client.add_after_event('message', activity_events.message_tracker)
        _client.add_after_event('raw_reaction_add', activity_events.reaction_tracker)

        _client.add_after_event('raw_reaction_add', timer_reactions.joinleave_tracker)
        _client.add_after_event('voice_state_update', voice_events.vc_update_handler)

        _client.add_after_event('guild_join', guild_events.on_guild_join)
        _client.add_after_event('guild_remove', guild_events.on_guild_remove)

    async def core_launch(self, _client):
        await self.load_timers()
        self.restore_from_save()
        asyncio.create_task(self._runloop())
        asyncio.create_task(self._saveloop())

    async def _runloop(self):
        while True:
            channel_keys = [
                (guildid, channelid)
                for guildid, channels in self.guild_channels.items()
                for channelid, channel in channels.items()
                if any(timer.state == TimerState.RUNNING for timer in channel.timers)
            ]
            channel_count = len(channel_keys)
            if channel_count == 0:
                await asyncio.sleep(30)
                continue

            delay = max(0.1, 30/channel_count)

            channels = (
                self.guild_channels[gid][cid]
                for gid, cid in channel_keys
                if gid in self.guild_channels and cid in self.guild_channels[gid]
            )
            for channel in channels:
                try:
                    await channel.update_pin()
                except Exception:
                    log("Exception encountered updating channel pin for {!r}".format(channel.channel),
                        context="TIMER_RUNLOOP",
                        level=logging.ERROR,
                        add_exc_info=True)
                await asyncio.sleep(delay)

    async def _saveloop(self):
        while True:
            await asyncio.sleep(60)
            self.update_save()

    def update_save(self, reason=None):
        # TODO: Move save file location to config? For e.g. sharding
        log("Writing session savefile.", context="TIMER_SAVE", level=logging.DEBUG)
        save_data = {
            guildid: [tchannel.serialise() for tchannel in tchannels.values()]
            for guildid, tchannels in self.guild_channels.items()
        }
        path = os.path.join(self.save_dir, self.save_fn)
        # Rotate
        if os.path.exists(path):
            os.rename(path, path + '.old')

        with open(path, 'wb') as f:
            pickle.dump(save_data, f, pickle.HIGHEST_PROTOCOL)

        if reason:
            shutil.copy2(path, path + '.' + reason)

    def restore_from_save(self):
        log("------------------------Beginning session restore.", context="TIMER_RESTORE")
        path = os.path.join(self.save_dir, self.save_fn)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                save_data = pickle.load(f)

            for guildid, data_channels in save_data.items():
                log("Restoring Guild (gid:{}).".format(guildid), context='TIMER_RESTORE')
                tchannels = self.guild_channels.get(guildid, None)
                if tchannels:
                    [tchannels[data['channelid']].restore_from(data)
                     for data in data_channels if data['channelid'] in tchannels]
        log("------------------------Session restore complete.", context="TIMER_RESTORE")

    async def load_timers(self):
        # Populate the pattern cache with the latest patterns
        tables.patterns.fetch_rows_where(_extra="INNER JOIN 'current_timer_patterns' USING (patternid)")

        # Build and load all the timers, preserving the existing ones
        timer_rows = tables.timers.fetch_rows_where()
        timers = [Timer(row) for row in timer_rows]
        timers = [timer for timer in timers if timer.load()]

        # Create the TimerChannels
        guild_channels = {}
        for timer in timers:
            channels = guild_channels.get(timer.channel.guild.id, None)
            if channels is None:
                channels = guild_channels[timer.channel.guild.id] = {}
            channel = channels.get(timer.channel.id, None)
            if channel is None:
                channel = channels[timer.channel.id] = TimerChannel(timer.channel)
            channel.timers.append(timer)

        self.guild_channels = guild_channels

    def create_timer(self, role, channel, name, **kwargs):
        guild = role.guild
        new_timer = Timer.create(role.id, guild.id, name, channel.id, **kwargs)
        if not new_timer.load():
            return None

        tchannels = self.guild_channels.get(guild.id, None)
        if tchannels is None:
            tchannels = self.guild_channels[guild.id] = {}
        tchannel = tchannels.get(channel.id, None)
        if tchannel is None:
            tchannel = tchannels[channel.id] = TimerChannel(channel)
        tchannel.timers.append(new_timer)
        asyncio.create_task(tchannel.update_pin(force=True))

        return new_timer

    async def obliterate_timer(self, timer):
        # Remove the timer from its channel
        channel = self.guild_channels[timer.channel.guild.id][timer.channel.id]
        channel.timers.remove(timer)
        if not channel.timers:
            self.guild_channels[timer.channel.guild.id].pop(timer.channel.id)

        # Destroy the timer, unsubscribing members and deleting it from data
        await timer.destroy()

        # Refresh the pinned message
        await channel.update_pin(force=True)

    def fetch_timer(self, roleid):
        row = tables.timers.fetch(roleid)
        if row:
            channels = self.guild_channels.get(row.guildid, None)
            if channels:
                channel = channels.get(row.channelid, None)
                if channel:
                    return next((timer for timer in channel.timers if timer.roleid == roleid), None)

    def get_timers_in(self, guildid, channelid=None):
        timers = []
        channels = self.guild_channels.get(guildid, None)
        if channels is not None:
            if channelid is None:
                timers = [timer for channel in channels.values() for timer in channel.timers]
            elif channelid in channels:
                timers = channels[channelid].timers

        return timers

    def get_subscriber(self, userid, guildid):
        return next(
            (timer.subscribers[userid]
             for channel in self.guild_channels.get(guildid, {}).values()
             for timer in channel.timers
             if userid in timer.subscribers),
            None
        )

    async def on_exception(self, ctx, exception):
        if isinstance(exception, InvalidPattern):
            await ctx.reply(
                embed=discord.Embed(
                    description=(
                        "{}\n\n"
                        "See `{}help patterns` for more information about timer patterns."
                    ).format(exception.msg, ctx.best_prefix),
                    colour=discord.Colour.red()
                )
            )
        else:
            await super().on_exception(ctx, exception)


module = TimerInterface()
