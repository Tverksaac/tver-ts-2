import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { is_client_context } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { observe, subscribe } from "@rbxts/charm"

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
        if (this.isActive) {
            warn(this + " Cant be Started twice!")
            return
        }

        subscribe(client_atom, (state) => {
            print(state)
        })

        this.start_replication()

        ClientEvents.sync.connect((payloads) => {
            this.syncer.sync(...payloads)
        })
        
        ClientEvents.request_sync.fire()

        print("Client Started!")
    }

    private start_replication() {
        let character: Character | undefined

        subscribe(client_atom, (state) => {
            print("SUBSCRIBE WORKED WW")
            if (!character && state) {
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