# GPT-Jerry

GPT-Jerry is a ChatGPT powered discord chatbot that uses [nextcord](https://github.com/nextcord/nextcord) and [revChatGPT](https://github.com/acheong08/ChatGPT).
## Features

 - Start a new chat thread with /chat
 - Waits for typing to stop before sending a message
 - Eagerly loads reply while waiting
 - Can abort mid text-generation to allow for faster response time.

# Setup
## Installation

Install nextcord and revChatGPT by running `pip install -r requirements.txt`

## Config

In `config.py` you need to place your discord bot token, as well as your OpenAI credentials, as specified on the [revChatGPT github](https://github.com/acheong08/ChatGPT). Here you can also change the initial prompt that Jerry uses.

## Running

Run `main.py` to start the bot.
