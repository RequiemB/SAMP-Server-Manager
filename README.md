# SAMP-Server-Manager

A Discord Bot to get SA-MP server information and send RCON commands written in Python.

You can use the [invite link](https://discord.com/api/oauth2/authorize?client_id=740603763118702662&permissions=414464723008&scope=bot%20applications.commands) to invite the bot to your server.

![image](https://img.shields.io/badge/discord.py-2.3.2-blue.svg) ![image](https://img.shields.io/badge/Python-3.10-blue.svg)

## Self-Hosted Instance

If you can't figure out how to host your own instance, you can invite my hosted bot to your server using the [invite link](https://discord.com/api/oauth2/authorize?client_id=740603763118702662&permissions=414464723008&scope=bot%20applications.commands).

To run the bot yourself, you need to do the following steps:

* Step 1: [Creating a Bot](https://github.com/RequiemB/SAMP-Server-Manager#creating-a-bot)
* Step 2: [Configuring the Bot](https://github.com/RequiemB/SAMP-Server-Manager#configuring-the-bot)
* Step 3: [Running the Bot](https://github.com/RequiemB/SAMP-Server-Manager#running-the-bot)

## Creating a Bot

In order to host your own instance of the bot, you have to create a Bot account.

* Head over to https://discord.com/developers/applications and click on New Application.
![img](https://i.imgur.com/Ti28nIL.png)

* Input an application name and agree to the Terms and Service and click on Create.

* Give it a description and set an avatar if you'd like. (The description will show up in your Bot's About Me.)

* Click on Bot in the Settings on the left side and proceed.

* Give the Bot a name and set an avatar if you'd like. Congratulations, you've successfully made a bot.

* Now, we need to invite it to a server to test it. For that, you need to get an invite link. Click on OAuth2 in the settings panel and go to URL generator.

* Tick the scopes 'bot' and 'applications.commands' (Application Commands is required to register slash commands.)
![img](https://i.imgur.com/Y093orm.png)

* Tick the Administrator permission (this isn't really required but since this URL is only for testing, it doesn't matter.)

* Scroll down and you'll see the link, copy it and paste it in a new tab in your browser.
![img](https://i.imgur.com/smE20fV.png)

* Add it to your testing server. That's it, you've made a bot and have added it to a guild. Now, it's time to configure the bot.

## Configuring the Bot

In order to configure the bot, you need to have the repository in your PC. You can get it by cloning the repository. Open your terminal ([Git Bash](https://git-scm.com/downloads) is recommended) and put enter the following shell code:

```sh
git clone https://www.github.com/RequiemB/SAMP-Server-Manager.git
```

(Do not close the shell window.)

It should be cloned into your PC now (or you can manually download it).

* Open your code editor (VSCode or Notepad++ or anything you'd like) in the cloned folder.

* Open `.env.example` and rename it to just `.env`.

* Replace `<YOUR-TOKEN-HERE>` with the newly created Bot's token. ([How to get Discord Bot Token](https://www.writebots.com/discord-bot-token/))
 
* Now, open `src/helpers/config.py` and edit it as you'd like.
```python
PREFIX = "." # The prefix to use
OWNER_IDS = [] # Your ID here
reactionSuccess = "" # The emoji to use when a command fails
reactionFailure = "" # The emoji to use when a command fails
```
Note that emoji ids should be in the `<name:id>` format.
After editing it, you should have a config.py as follows:
![img](https://imgur.com/oDEgNfs.png)
This is only an example, you should replace it with your configuration.
You've successfully configured the bot now.

(It really doesn't matter if you don't have a prefix set as the bot runs on application commands.)

## Running the Bot

After configuration the bot, you have to run it. For that, go to your shell window and run the following shell code:

```sh
pip install -r requirements.txt
cd src
python main.py
```

(The shell's location should be at the main folder now.)

If your bot comes online, you've successfully hosted the bot. If it doesn't, you can create an [issue](https://www.github.com/RequiemB/SAMP-Server-Manager/issues) with your problem.




    