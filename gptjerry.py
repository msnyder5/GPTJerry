import nextcord
from dataclasses import dataclass, field
from revChatGPT.revChatGPT import AsyncChatbot as Chatbot
from datetime import datetime as dt
from contextlib import suppress
import asyncio
from config import OPENAI_CONFIG, INITIAL_PROMPT

@dataclass
class TypingEvent:
    user_id: int
    when: dt

@dataclass
class GPTJerry:
    _chatbot: Chatbot = field(default_factory=lambda:Chatbot(OPENAI_CONFIG))
    _chatbot_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _conversation_id: int = None
    _parent_id: int = None
    _unprocessed_messages: list[str] = field(default_factory=list)
    _typing_events: list[TypingEvent] = field(default_factory=list)
    
    # Update from on_raw_typing
    def add_typing(self, payload: nextcord.RawTypingEvent):
        self._typing_events.append(TypingEvent(payload.user_id, dt.now()))
    
    # Add a new message to the list to be processed
    # We inject the username at the beginning of everyone's messaeg so that Jerry can keep track of who's who.
    def _add_message(self, message: nextcord.Message):
        self._unprocessed_messages.append(f'{message.author.display_name}: {message.content}')
    
    # Remove any typing events that are older than 12 seconds or from the message author
    def _remove_typing_events(self, message: nextcord.Message = None):
        now = dt.now()
        author_id = message.author.id if message else None
        for typing_event in self._typing_events:
            if (now - typing_event.when).total_seconds() > 12.0 or typing_event.user_id == author_id:
                self._typing_events.remove(typing_event)
    
    # Remove dead typing events, then return if any are left
    def _check_typing(self):
        self._remove_typing_events()
        return bool(self._typing_events)

    # Get the prompt for Jerry.
    # We add Jerry's name for him to fill in what he says.
    # If we don't have a conversation or parent id, we prepend the initial prompt
    def get_chatbot_prompt(self):
        chatbot_prompt = '' if self._chatbot.conversation_id and self._chatbot.parent_id else f'{INITIAL_PROMPT}\n'
        chatbot_prompt += '\n'.join(self._unprocessed_messages)
        chatbot_prompt += '\nGPT-Jerry: '
        return chatbot_prompt, self._unprocessed_messages


    async def handle_abort(self, unprocessed_messages: list[str], message: nextcord.Message, restart: bool = True):
        # If there are no messages left to process, we abort
        if len(self._unprocessed_messages) == 0:
            return True
        # If the list of unprocessed messages has changed, we abort
        if self._unprocessed_messages != unprocessed_messages:
            # If this is the last unprocessed message, we retry (will update the unprocessed_messages list)
            if self._unprocessed_messages[-1] == f'{message.author.display_name}: {message.content}' and restart:
                await self.on_message(message)
            return True
        # Otherwise, we continue
        return False

    # Util function to cancel an async generator
    @staticmethod
    async def cancel_gen(agen):
        task = asyncio.create_task(agen.__anext__())
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await agen.aclose()

    async def on_message(self, message: nextcord.Message):
        # Trigger typing event only lasts for 10 seconds so have to keep constantly calling it
        # TODO: Outsource trigger_typing to its own asyncio task
        await message.channel.trigger_typing() # Type...
        
        # Update message and typing info
        self._remove_typing_events(message)
        self._add_message(message)
        
        # Get the chatbot prompt (and the list of messages the prompt represents)
        chatbot_prompt, unprocessed_messages = self.get_chatbot_prompt()
        
        # Wait for 2 seconds to give user a chance to start typing again
        await asyncio.sleep(2.0)
        # With a lock on the chatbot (so only one api request at a time)
        async with self._chatbot_lock:
            # We periodically call handle_abort throughout this function to see if we should abort
            if await self.handle_abort(unprocessed_messages, message):
                return
            await message.channel.trigger_typing() # Type...
            
            # Get the async generator for the chat response
            agen = await self._chatbot.get_chat_response(chatbot_prompt, conversation_id=self._conversation_id, parent_id=self._parent_id, output="stream")
            chatbot_response = None
            i = 0
            # Loop through the generator, getting the ChatGPT response
            # We do it this way say that we can abort in the middle of generating a response.
            async for response in agen:
                chatbot_response = response
                # Set restart to false so that we can cancel the generator first
                if await self.handle_abort(unprocessed_messages, message, False):
                    break
                # Every 25 responses, retrigger typing
                if not i%25:
                    await message.channel.trigger_typing()
                i+=1
            # If we aborted inside the generator, we cancel the generator here
            if await self.handle_abort(unprocessed_messages, message):
                await self.cancel_gen(agen)
                return
        # Wait until (we think) no one is typing
        while self._check_typing():
            print("WAITING FOR TYPING TO BE DONE")
            print(self._typing_events)
            if await self.handle_abort(unprocessed_messages, message):
                return
            await asyncio.sleep(1.0)
            await message.channel.trigger_typing()
        # Check one last time if we need to abort for good measure
        if await self.handle_abort(unprocessed_messages, message):
            return
        
        # Save our state
        self._unprocessed_messages = [unprocessed_message for unprocessed_message in self._unprocessed_messages if unprocessed_message not in unprocessed_messages]
        self._conversation_id = chatbot_response['conversation_id']
        self._parent_id = chatbot_response['parent_id']
        
        # Send the reply message
        chatbot_message = chatbot_response['message']
        # TODO: Potentially send one sentence at a time, idk if it's worth it though.
        # chatbot_sentences = [sentence.strip() for sentence in chatbot_message.split('.')] 
        await message.channel.send(chatbot_message)