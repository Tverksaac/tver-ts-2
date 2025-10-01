import Charm, { atom } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { is_server_context } from "shared/tver/utility/utils"

let server_activated = false

class Server {
    private isActive = false
    private server_atom = atom<Map<Instance, CharacterInfo>>(new Map())

    private syncer = CharmSync.server(
        {
            atoms: {atom: this.server_atom}  
        }
    )

    constructor () {}

    public Start() {
        this.syncer.connect((player, ...payloads) => {
            type Payload = CharmSync.SyncPayload<
                {
                    server_atom: Charm.Atom<CharacterInfo | undefined>
                }
            >

            print(payloads)

            const payload_to_send: Payload[] = []
            for (const payload of payloads) {}
        })

        ServerEvents.request_sync.connect((player) => {
            this.syncer.hydrate(player)
        })
    }
}

export function CreateServer() {
    if (!is_server_context()) {
        error("Server can be only created on Server Side!")
    }
    if (server_activated) {
        error("Server cant be created twice!")
    }

    server_activated = true
    return new Server()
}