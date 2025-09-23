import { Networking } from "@flamework/networking";
import type { SyncPayload } from "@rbxts/charm-sync";
import { CharacterInfo } from "../utility/interfaces";

interface ClientToServerEvents {}
interface ServerToClientEvents {
	sync(
		payloads: SyncPayload<{
			atom: Charm.Atom<CharacterInfo | undefined>;
		}>[],
	): void;
}

interface ClientToServerFunctions {}
interface ServerToClientFunctions {}

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