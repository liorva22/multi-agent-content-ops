# PRD: Offline Mode for Notes

## Summary
Offline Mode lets mobile users of our Notes app read, create and edit notes without a connection, and syncs changes automatically when they reconnect.

## Problem
Field technicians and travelers lose work when connectivity drops. 23% of one-star app reviews in the last year mention losing a note offline.

## Solution
Notes are stored locally in an encrypted on-device database. Edits made offline are queued and merged on reconnect. When the same note was edited on two devices, both versions are kept and the user picks one; nothing is silently overwritten.

## Beta results
- 2,400 beta users over 8 weeks.
- Sync conflicts occurred in 0.6% of synced notes.
- Zero data-loss reports during the beta.
- Weekly active usage among beta users rose 12% compared with a control group.

## Launch
Ships in app version 5.0 on iOS and Android on June 10, for all plans. Offline storage is capped at 2 GB per device.

## Non-goals
Offline collaboration in real time. Offline search across attachments.
