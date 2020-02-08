import os
import traceback
import logging
import json
import asyncio

import discord

from logger import log

from .trackers import message_tracker, reaction_tracker
from .Timer import Timer, TimerChannel, TimerSubscriber, TimerStage, NotifyLevel
from .registry import TimerRegistry


class TimerInterface(object):
    save_interval = 120
    save_fp = "data/timerstatus.json"

    def __init__(self, client, db_filename):
        self.client = client
        self.registry = TimerRegistry(db_filename)

        self.guild_channels = {}
        self.channels = {}
        self.subscribers = {}

        self.last_save = 0

        self.ready = False

        self.setup_client()

    def setup_client(self):
        client = self.client

        # Bind the interface
        client.interface = self

        # Ensure required config entry exists
        client.config.guilds.ensure_exists("timers")

        # Load timers from database
        client.add_after_event("ready", self.launch)

        # Track user activity in timer channels
        client.add_after_event("message", message_tracker)
        client.add_after_event("reaction_add", reaction_tracker)

    async def launch(self, client):
        if self.ready:
            return

        self.load_timers()
        await self.restore_save()

        self.ready = True
        asyncio.ensure_future(self.updateloop())

    async def updateloop(self):
        while True:
            for tchan in self.channels.values():
                asyncio.ensure_future(tchan.update())

            if Timer.now() - self.last_save > self.save_interval:
                self.update_save()

            await asyncio.sleep(2)

    def load_timers(self):
        client = self.client

        # Get the guilds with timers
        guilds = client.config.guilds.find_not_empty("timers")

        for guildid in guilds:
            # List of TimerChannels in the guild
            channels = []

            # Fetch the actual guild, if possible
            guild = client.get_guild(guildid)
            if guild is None:
                continue

            # Get the corresponding timers
            raw_timers = client.config.guilds.get(guildid, "timers")
            for name, roleid, channelid, clock_channelid in raw_timers:
                # Get the objects corresponding to the ids
                role = guild.get_role(roleid)
                channel = guild.get_channel(channelid)
                clock_channel = guild.get_channel(clock_channelid)

                if role is None or channel is None or clock_channel is None:
                    # This timer doesn't exist
                    # TODO: Handle garbage collection
                    continue

                # Create the new timer
                new_timer = Timer(name, role, channel, clock_channel)

                # Get the timer channel, or create it
                tchan = self.channels.get(channelid, None)
                if tchan is None:
                    tchan = TimerChannel(channel)
                    channels.append(tchan)
                    self.channels[channelid] = tchan

                # Bind the timer to the channel
                tchan.timers.append(new_timer)

            # Assign the channels to the guild
            self.guild_channels[guildid] = channels

    async def restore_save(self):
        # Open save file if it exists
        if not os.path.exists(self.save_fp):
            return

        with open(self.save_fp) as f:
            try:
                savedata = json.load(f)
            except Exception:
                log("Caught the following exception loading the temporary savefile\n{}".format(traceback.format_exc()),
                    context="TIMER_RESTORE",
                    level=logging.ERROR)
                os.rename(self.save_fp, self.save_fp + '_CORRUPTED')
                return

        if savedata:
            # Create a roleid: timer map
            timers = {timer.role.id: timer for channel in self.channels.values() for timer in channel.timers}

            for timer in savedata['timers']:
                if timer['roleid'] in timers:
                    timers[timer['roleid']].update_from_data(timer)
                    log("Restored timer {} (roleid {}) from save.".format(timer['name'], timer['roleid']),
                        context="TIMER_RESTORE")

            for sub_data in savedata['subscribers']:
                if sub_data['roleid'] in timers:
                    timer = timers[sub_data['roleid']]

                    guild = self.client.get_guild(sub_data['guildid'])
                    if guild is None:
                        continue

                    member = guild.get_member(sub_data['id'])
                    if member is None:
                        continue

                    subber = TimerSubscriber.deserialise(member, timer, self, sub_data)
                    self.subscribers[member.id] = subber
                    timer.subscribed[member.id] = subber

                    log("Restored subscriber {} (id {}) in timer {} (roleid {}) from save.".format(member.name,
                                                                                                   member.id,
                                                                                                   timer.name,
                                                                                                   timer.role.id),
                        context="TIMER_RESTORE")

            for tchan_data in savedata['timer_channels']:
                if tchan_data['id'] in self.channels:
                    tchan = self.channels[tchan_data['id']]
                    try:
                        tchan.msg = await tchan.channel.fetch_message(tchan_data['msgid'])
                    except discord.NotFound:
                        continue
                    except discord.Forbidden:
                        continue

    def update_save(self):
        # Generate save dict
        timers = [timer for channel in self.channels.values() for timer in channel.timers]
        timer_data = [timer.serialise() for timer in timers if timer.stages]
        sub_data = [subber.serialise() for subber in self.subscribers.values()]
        tchan_data = [{'id': tchan.channel.id, 'msgid': tchan.msg.id} for tchan in self.channels.values() if tchan.msg]

        data = {
            'timers': timer_data,
            'subscribers': sub_data,
            'timer_channels': tchan_data
        }
        data_str = json.dumps(data)

        with open(self.save_fp, 'w') as f:
            f.write(data_str)

        self.last_save = Timer.now()

    def create_timer(self, group_name, group_role, bound_channel, clock_channel):
        guild = group_role.guild

        # Create the new timer
        new_timer = Timer(group_name, group_role, bound_channel, clock_channel)

        # Bind the timer to a timer channel, creating if required
        tchan = self.channels.get(bound_channel.id, None)
        if tchan is None:
            # Create the timer channel
            tchan = TimerChannel(bound_channel)
            self.channels[bound_channel.id] = tchan

            # Add the timer channel to the guild list, creating if required
            guild_channels = self.guild_channels.get(guild.id, None)
            if guild_channels is None:
                guild_channels = []
                self.guild_channels[guild.id] = guild_channels
            guild_channels.append(tchan)
        tchan.timers.append(new_timer)

        # Store the new timer in guild config
        timers = self.client.config.guilds.get(guild.id, "timers") or []
        timers.append((group_name, group_role.id, bound_channel.id, clock_channel.id))
        self.client.config.guilds.set(guild.id, "timers", timers)

        return new_timer

    def destroy_timer(self, timer):
        # Unsubscribe all members
        for sub in timer.subscribed.values():
            asyncio.ensure_future(sub.unsub())

        # Stop the timer
        timer.stop()

        # Remove the timer from its channel
        tchan = self.channels.get(timer.channel.id, None)
        if tchan is not None:
            tchan.timers.remove(timer)

        # Update the guild timer config
        guild = timer.channel.guild
        timers = self.client.config.guilds.get(guild.id, "timers") or []
        tup = next(tup for tup in timers if tup[0] == timer.name and tup[1] == timer.role.id)
        timers.remove(tup)
        self.client.config.guilds.set(guild.id, "timers", timers)

    def get_timer_for(self, memberid):
        if memberid in self.subscribers:
            return self.subscribers[memberid].timer
        else:
            return None

    def get_channel_timers(self, channelid):
        if channelid in self.channels:
            return self.channels[channelid].timers
        else:
            return None

    def get_guild_timers(self, guildid):
        if guildid in self.guild_channels:
            return [timer for tchan in self.guild_channels[guildid] for timer in tchan.timers]

    async def wait_until_ready(self):
        while not self.ready:
            await asyncio.sleep(1)

    def bump_user(self, userid, sourceid):
        if userid in self.subscribers:
            subber = self.subscribers[userid]
            if sourceid == 0 or sourceid == subber.timer.channel.id:
                subber.bump()

    async def sub(self, ctx, member, timer):
        # Get the notify level
        notify = ctx.client.config.users.get(member.id, "notify_level")
        notify = NotifyLevel(notify) if notify is not None else NotifyLevel.WARNING

        # Create the subscriber
        subber = TimerSubscriber(member, timer, self, notify=notify)

        # Attempt to add the sub role
        try:
            await member.add_roles(timer.role)
        except discord.Forbidden:
            await ctx.error_reply("Insufficient permissions to add the group role `{}`.".format(timer.role.name))
        except discord.NotFound:
            await ctx.error_reply("Group role `{}` doesn't exist! This group is broken.".format(timer.role.id))

        timer.subscribed[member.id] = subber
        self.subscribers[member.id] = subber

    async def unsub(self, memberid):
        """
        Unsubscribe a user from a timer, if they are subscribed.
        Otherwise, do nothing.
        Return the session data for ease of access.
        """
        subber = self.subscribers.get(memberid, None)
        if subber is not None:
            session = subber.session_data()
            subber.active = False

            self.subscribers.pop(memberid)
            subber.timer.subscribed.pop(memberid)

            try:
                await subber.member.remove_roles(subber.timer.role)
            except Exception:
                pass

            self.registry.new_session(*session)
            return session

    @staticmethod
    def parse_setupstr(setupstr):
        stringy_stages = [stage.strip() for stage in setupstr.strip(';').split(';')]

        stages = []
        for stringy_stage in stringy_stages:
            parts = [part.strip() for part in stringy_stage.split(",", maxsplit=2)]

            if len(parts) < 2 or not parts[1].isdigit():
                return None
            stages.append(TimerStage(parts[0], int(parts[1]), message=parts[2] if len(parts) > 2 else ""))

        return stages
