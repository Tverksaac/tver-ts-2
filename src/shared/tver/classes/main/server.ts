import Charm, { atom } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/interfaces"

export class Server {
    private isActive = false
    private server_atom = atom<Map<Instance, CharacterInfo>>(new Map())

    private syncer = CharmSync.server(
        {
            atoms: {server_atom: this.server_atom}  
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

            const payload_to_send: Payload[] = []

            for (const payload of payloads) {}
        })
    }
}