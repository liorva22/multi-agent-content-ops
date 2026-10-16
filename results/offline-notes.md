# Introducing Offline Mode for Notes

**TL;DR:** Offline Mode lets mobile users of our Notes app read, create and edit notes without a connection, and syncs changes automatically when they reconnect.

Offline Mode lets mobile users of our Notes app read, create and edit notes without a connection, and syncs changes automatically when they reconnect.

## The problem we set out to solve

Field technicians and travelers lose work when connectivity drops. 23% of one-star app reviews in the last year mention losing a note offline.

## How it works

Notes are stored locally in an encrypted on-device database. Edits made offline are queued and merged on reconnect. When the same note was edited on two devices, both versions are kept and the user picks one; nothing is silently overwritten.

## What the beta showed

We tested it with real customers before launch. 2,400 beta users over 8 weeks. Sync conflicts occurred in 0.6% of synced notes. Zero data-loss reports during the beta. Weekly active usage among beta users rose 12% compared with a control group.

## Availability

Ships in app version 5.0 on iOS and Android on June 10, for all plans. Offline storage is capped at 2 GB per device.

## What it doesn't do (yet)

To keep the scope tight, these are out of scope for now: Offline collaboration in real time. Offline search across attachments.