import Charm, { atom, subscribe } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { client_atom } from "shared/tver/utility/shared"
import { is_server_context } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { Players } from "@rbxts/services"

let server_activated = false

class Server {
    private isActive = false

    private readonly atom = atom<Map<Instance, Character>>(new Map())
    private readonly syncer = CharmSync.server(
        {
            atoms: {atom: this.atom}
        }
    )

    constructor () {}

    public Start() {
        if (this.isActive) {
            warn(this + " Cant be Started twice!")
            return
        }

        ServerEvents.request_sync.connect((player) => {
            this.syncer.hydrate(player)
        })
        
        this.syncer.connect((player, ...payloads) => {
            const payload_to_sync = [] as CharmSync.SyncPayload<{
                atom: Charm.Atom<CharacterInfo | undefined>
            }>[]

            print(payloads)
            for (const payload of payloads) {
                if (payload.type == "init") {
                }
            }

            ServerEvents.sync.fire(player, payload_to_sync)
        })

        this.isActive = true
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