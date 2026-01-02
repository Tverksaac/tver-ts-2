import { Networking } from "@flamework/networking";
import CharmSync from "@rbxts/charm-sync";

/** Events that clients may fire to the server. */
interface ClientToServerEvents {}

/** Events that the server may fire to clients. */
interface ServerToClientEvents {}

interface ClientToServerFunctions {}

interface ServerToClientFunctions {}

export const GlobalFunctions = Networking.createFunction<ClientToServerFunctions, ServerToClientFunctions>();
export const ServerFunctions = GlobalFunctions.createServer({});
export const ClientFunctions = GlobalFunctions.createClient({});

export const GlobalEvents = Networking.createEvent<ClientToServerEvents, ServerToClientEvents>();
export const ServerEvents = GlobalEvents.createServer({});
export const ClientEvents = GlobalEvents.createClient({});
