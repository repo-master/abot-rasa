
from rasa_sdk import Action
from rasa_sdk.events import ConversationPaused, UserUtteranceReverted
from rasa_sdk.types import Text


class ActionHumanHandoff(Action):
    def name(self) -> Text:
        return "action_human_handoff"

    def run(self, dispatcher, tracker, domain):
        # output a message saying that the conversation will now be
        # continued by a human.

        message = "Let me transfer you to a human..."
        dispatcher.utter_message(text=message)
        # pause tracker, undo last user interaction
        return [ConversationPaused(), UserUtteranceReverted()]
