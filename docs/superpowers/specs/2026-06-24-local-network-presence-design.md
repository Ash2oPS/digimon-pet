# Local Network Presence V1 Design

## Goal

Add a discreet local network presence feature so players can manually view friends' current Digimon on the same LAN without automatic discovery or broadcast traffic.

## User Experience

- On launch, if no trainer nickname exists, the app prompts the player to enter one.
- The nickname is stored as a user preference, separate from the Digimon save state.
- The network feature is disabled by default.
- A "Local Network" window lets the player:
  - view and edit their trainer nickname;
  - view their local IP address and listening port;
  - enable or disable local availability;
  - add, remove, and inspect friends by manual `host:port`;
  - see each friend's online/offline status and current Digimon summary.
- No permanent network indicator or arrival/departure notifications are included in V1.

## Network Model

- No UDP broadcast or LAN-wide discovery is used.
- When local availability is enabled, the app starts a small local HTTP server on a fixed default port.
- Friends are added manually by IP and port, for example `192.168.1.42:54545`.
- The app polls configured friends every 10 seconds.
- If a friend does not respond, their row is marked offline instead of interrupting the player.
- If the feature is disabled, the app does not listen for peers and does not poll configured friends.

## Shared Data

The peer endpoint returns only public presence data:

- protocol version;
- trainer nickname;
- current Digimon species id;
- current Digimon display name;
- growth stage;
- current action;
- sleeping state.

The endpoint must not expose the full save file, inventory, collection progress, precise stats, filesystem paths, or debug settings.

## Components

- `network_settings`: loads and saves trainer/network preferences in the OS user data folder.
- `presence_service`: owns the optional local server, peer polling, peer status cache, and public payload generation.
- `network_window`: PySide window for nickname, local availability, local address, and manual friend management.
- `PetWindow` integration: creates the service, supplies current state snapshots, prompts for missing nickname, and opens the network window from existing app navigation.

## Data Storage

Network preferences are stored outside the encrypted pet save:

- trainer nickname;
- local availability enabled flag;
- listen port;
- configured friend addresses.

The nickname prompt should reject empty names and trim whitespace. V1 does not need account identity, authentication, or nickname uniqueness.

## Error Handling

- Invalid friend addresses are rejected in the window before saving.
- Port bind failures keep local availability off and show a short status message in the network window.
- Peer timeouts and malformed responses mark that peer offline.
- Network errors must not crash the pet window or block normal gameplay.

## Testing

Unit tests should cover:

- settings load/save defaults and persistence;
- nickname validation;
- public payload generation excludes private save data;
- friend address parsing;
- peer expiration/offline behavior;
- service disabled state does not poll or listen.

Manual validation should cover:

- first launch without nickname prompts once;
- enabling local availability starts listening;
- adding `host:port` displays a reachable peer;
- disabling the feature stops network activity.

## Out of Scope

- Automatic LAN discovery.
- UDP broadcast.
- Remote actions, battle, trading, chat, or item exchange.
- Encryption, authentication, or rooms with shared codes.
- Rendering friends' pets directly on the desktop.
