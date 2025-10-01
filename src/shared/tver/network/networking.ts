import { Networking } from "@flamework/networking";
import Charm from "@rbxts/charm";
import { SyncPayload } from "@rbxts/charm-sync";
import { CharacterInfo } from "../utility/_ts_only/interfaces";

interface ClientToServerEvents {
	request_sync(): void
}
interface ServerToClientEvents {
	sync(
		payloads: SyncPayload<{
			atom: Charm.Atom<CharacterInfo | undefined>
		}>[]
	): void
}

export const GlobalEvents = Networking.createEvent<ClientToServerEvents, ServerToClientEvents>()
export const ClientEvents = GlobalEvents.createClient({})
export const ServerEvents = GlobalEvents.createServer({})