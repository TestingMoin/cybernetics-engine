# Cybernetics Trading Engine — Chunk 112

Adds the safe-state recovery/resume coordinator. Dependency recovery can become RECOVERY_READY, but trading never resumes automatically. An explicit resume action is required and is gated by dependency health, STOP_NEW_TRADES control state, clear emergency state, live authorization, and a control-state callback.

