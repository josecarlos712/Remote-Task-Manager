from django.test import TestCase
from .commands.commands_utils import get_command_list, load_commands_from_json


class MyTestCase(TestCase):
    def test_get_command_list(self):
        # Load commands from JSON file
        #load_commands_from_json()
        # Get the list of commands in the DB
        commands_list = get_command_list()
        print(f"Commands list: {commands_list}")
        self.assertNotEquals(commands_list, [], "The commands list is empty.")  # Check if the list is not empty
