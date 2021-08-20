from typing import List, Dict
from tdw.add_ons.add_on import AddOn
from tdw_agents.agent import Agent


class AgentManager(AddOn):
    def __init__(self):
        super().__init__()
        """:field
        A dictionary of add-ons. Key = An identifier for the add-on. Agents can use this key to determine if the AgentManager has all of the add-ons that the agent needs.
        An agent can add to this when the manager is initialized.
        These add-ons will inject commands into `self.commands` in a fixed order. Then the agents will inject their commands.
        """
        self.add_ons: Dict[str, AddOn] = dict()
        """:field
        A list of all of this manager's agents. You must add every agent when the AgentManager is first initialized, otherwise they might not appear correctly in the output data.
        """
        self.agents: List[Agent] = list()

    def get_initialization_commands(self) -> List[dict]:
        # Append required add-ons.
        for agent in self.agents:
            agent.add_required_add_ons(self)
        commands = []
        # Initialize all of my add-ons.
        for add_on in self.add_ons.values():
            commands.extend(add_on.get_initialization_commands())
            add_on.initialized = True
        # Initialize the agents.
        for agent in self.agents:
            commands.extend(agent.get_initialization_commands())
        return commands

    def on_send(self, resp: List[bytes]) -> None:
        # Append the add-on commands.
        for add_on in self.add_ons.values():
            add_on.on_send(resp=resp)
            self.commands.extend(add_on.commands)
        # Append the agent commands.
        for agent in self.agents:
            agent.step(resp=resp, agent_manager=self)
            self.commands.extend(agent.commands)
