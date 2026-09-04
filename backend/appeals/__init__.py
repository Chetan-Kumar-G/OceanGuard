"""Public false-positive dispute intake, and the investigator review queue for it.

A public, unauthenticated form lets anyone with an event ID (e.g. a contacted
vessel operator) dispute a detection or candidate flagging. Appeals never
silently disappear or get overwritten - review actions append a status
history, mirroring F18's correction/audit principle.
"""
