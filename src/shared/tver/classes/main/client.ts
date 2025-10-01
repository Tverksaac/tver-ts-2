import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { is_client_context } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { subscribe } from "@rbxts/charm"

let client_activated = false

class Client {
    private isActive = false
    private syncer = CharmSync.client(
            {
                atoms: {atom: client_atom}
            }
        )

    constructor () {}

    public Start() {
        this.start_replication()

        ClientEvents.sync.connect((payloads) => {
            this.syncer.sync(...payloads)
        })

        ClientEvents.request_sync.fire()
    }

    private start_replication() {
        let character: Character | undefined

        subscribe(client_atom, (state) => {
            if (state && !character) {
                character = new Character(state.instance)
            }
        })
    }
}

export function CreateClient() {
    if (!is_client_context()) {
        error("Client can be only created on Client Side!")
    }
    if (client_activated) {
        error("Client already created")
    }

    client_activated = true
    return new Client()
}