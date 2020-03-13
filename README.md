The Idea
--------
The **Pomodoro Technique** is a time management method that has been used to boost productivity for students and workers since 1980.
A *Pomodoro* was typically `25` minutes of work with `5` minutes break, tracked using a *Pomodoro timer* (a tomato kitchen timer). After completing four Pomodoros, you would take a longer break (10-15 minutes), and begin the process again.


**Group study** has been around for as long as education itself.
By working in a group, you boost motivation for yourself and other group members, learning becomes easier and more enjoyable through discussion of the content, and the group members can keep each other accountable.
Plus, it's simply comforting to know you're not alone and there are other people working hard alongside you!


**PomoBot** combines these techniques and brings them to the *Discord* chat platform in the form of an easy to use bot.
Guildmates from all around the world can use PomoBot to work together as a group, sharing a flexible Pomodoro-style group timer which notifies them when to take a break and when to start work again.
Whether you work in the night or in the day, you never need to be alone!

Description
-----------
PomoBot has the following primary features:
* Creation of multiple guild role based group timers, bound to one or multiple channels.
* Member based timer configuration for setting up timer stages.
* Easily viewable timers (via pinned messages and clock voice channels).
* Channel notifications for timer stage changes.
* Complete timer session stats, including daily leaderboards and individual summary statistics.

Many more features are planned, including graphical leaderboards and statistical analysis, and the bot is under user-driven active development.

PomoBot easily supports multiple guilds (a public implementation will be available soon), but is not optimised as a "one instance" bot, and there are no plans to implement sharding in the near future.
You are welcome to use the public implementation, but for long term use it is recommended you follow the installation instructions below to host your own copy.

PomoBot was originally developed for the [WYSC Study Cafe](https://wysc.netlify.com/), of which the author is an active and proud member, but is in no way affiliated with WYSC.

Requirements and Installation
-----------------------------
To self-host PomoBot, you first need a *Discord Bot Token*, which you can obtain by following [this guide](https://discordpy.readthedocs.io/en/latest/discord.html).
You will also need `python3.6` or greater, and a stable internet connection.
Steps:
* Clone the repository into a folder of your choosing with the `--recurse-submodules` option. For example,
```
git clone --recurse-submodules https://github.com/Intery/PomoBot.git
```
* Install the requirements in `requirements.txt` (typically by running `pip3 install -r requirements.txt`).
* Copy the `example-bot.conf` file under `config` to `config/bot.conf`, and edit it to include your bot token.
* Run `startup.sh`, or for Windows users, `python3 bot/main.py`, from the top directory.

That's it! PomoBot will now be running on the bot client you created.
If you have any issues or find any bugs, please submit an issue via the github issues page, together with any relevant log information.
Suggestions for new features are also welcome!

Documentation
-------------
A command list and general documentation for PomoBot may be found using the `help` command.
Documentation for a specific command, say `newgroup`, may be found with `help newgroup`.
The documentation is a work in progress, new information will be added constantly.
