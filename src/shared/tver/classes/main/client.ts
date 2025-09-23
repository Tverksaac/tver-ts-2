import Charm, { atom } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/interfaces"
import { client_atom } from "shared/tver/utility/shared"

export class Client {
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