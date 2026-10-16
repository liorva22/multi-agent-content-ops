# PRD: Smart Inbox Triage

## Summary
Smart Inbox Triage automatically sorts incoming support tickets into four queues (billing, bug, how-to, account) so agents stop hand-sorting their morning backlog.

## Problem
Support agents at mid-size SaaS companies spend the first 45 minutes of every shift sorting tickets. In our customer interviews, 9 of 12 support leads named manual triage as their top time sink.

## Solution
A classifier reads each new ticket's subject and body and assigns a queue and a priority (P1-P3). Agents can override any label with one click, and every override is used to retrain the model weekly.

## Beta results
- Beta ran for 6 weeks with 14 customer teams.
- Triage accuracy was 91% against agent-corrected labels.
- Median time to first response dropped from 4.2 hours to 2.9 hours.
- Agents overrode 7% of labels; most overrides were billing vs account.

## Launch
General availability on March 3. Included in the Growth and Enterprise plans at no extra cost. Available in English first; Spanish and German follow in Q3.

## Non-goals
Auto-replying to customers. Routing to individual agents.
