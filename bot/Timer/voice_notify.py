import asyncio
import discord


voice_alert_path = "assets/sounds/slow-spring-board.wav"

guild_locks = {}


async def play_alert(channel: discord.VoiceChannel):
    if not channel.members:
        # Don't notify an empty channel
        return

    lock = guild_locks.get(channel.guild.id, None)
    if not lock:
        lock = guild_locks[channel.guild.id] = asyncio.Lock()

    async with lock:
        vc = channel.guild.voice_client
        if not vc:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        audio_stream = open(voice_alert_path, 'rb')
        try:
            vc.play(discord.PCMAudio(audio_stream), after=lambda e: audio_stream.close())
        except discord.HTTPException:
            pass

        count = 0
        while vc.is_playing() and count < 10:
            await asyncio.sleep(0.5)
            count += 1

        await vc.disconnect()
