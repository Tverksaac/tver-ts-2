import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { is_client_context } from "shared/tver/utility/utils"

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
        ClientEvents.sync.connect((payloads) => {
            this.syncer.sync(...payloads)
        })

        ClientEvents.request_sync.fire()
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