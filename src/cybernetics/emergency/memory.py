from __future__ import annotations


class InMemoryEmergencyFlattenState:
    """Local/test implementation; production persistence comes from DB."""

    def __init__(self):
        self.requests: dict[str,str] = {}
        self.position_intents: dict[tuple[str,str],str] = {}

    def was_requested(self, emergency_id):
        return emergency_id in self.requests

    def remember_request(self, emergency_id, request_id):
        self.requests.setdefault(emergency_id, request_id)

    def was_position_exit_planned(self, emergency_id, position_id):
        return (emergency_id, position_id) in self.position_intents

    def remember_position_exit(self, emergency_id, position_id, intent_id):
        self.position_intents.setdefault((emergency_id, position_id), intent_id)
