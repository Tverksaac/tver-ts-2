import { Networking } from "@flamework/networking";
import type { SyncPayload } from "@rbxts/charm-sync";
import { CharacterInfo } from "../utility/_ts_only/interfaces";
import CharmSync from "@rbxts/charm-sync";

/** Events that clients may fire to the server. */
interface ClientToServerEvents {
	request_sync(): void,
	character_replication_done(): void
}

/** Events that the server may fire to clients. */
interface ServerToClientEvents {
	sync(
		payloads: CharmSync.SyncPayload<
			{atom: Charm.Atom<CharacterInfo | undefined>}
		>[]
	): void
}

interface ClientToServerFunctions {
}

interface ServerToClientFunctions {
}

export const GlobalFunctions = Networking.createFunction<
	ClientToServerFunctions,
	ServerToClientFunctions
>();
export const ServerFunctions = GlobalFunctions.createServer({});
export const ClientFunctions = GlobalFunctions.createClient({});

export const GlobalEvents = Networking.createEvent<
	ClientToServerEvents,
	ServerToClientEvents
>();
export const ServerEvents = GlobalEvents.createServer({});
export const ClientEvents = GlobalEvents.createClient({});