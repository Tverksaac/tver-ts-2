import Charm, { Atom, atom, subscribe } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { client_atom } from "shared/tver/utility/shared"
import { is_server_context, set_handler } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { Players } from "@rbxts/services"

let server_activated = false

export class Server {
    private isActive = false

    public atom = atom<Map<Instance, CharacterInfo>>(new Map())
    private syncer = CharmSync.server(
        {
            atoms: {atom: this.atom}
        }
    )

    constructor () {
        set_handler(this)
    }

    public Start() {
        if (this.isActive) {
            warn(this + " Cant be Started twice!")
            return
        }

        ServerEvents.request_sync.connect((player) => {
            print('Hydrating: ' + player)
            this.syncer.hydrate(player)
        })
        
        const players = new Map<Player, number>()
        Players.PlayerRemoving.Connect((player) => {
            players.delete(player)
        })

        this.syncer.connect((player, ...payloads) => {
            const id = players.get(player) ? players.get(player) : player.Character? Character.GetCharacterFromInstance(player.Character)?.id : undefined
            
            print(payloads)
            print(player)
            print(id)
            
            if (id === undefined) return
            players.set(player, id)

            const payload_to_sync = [] as CharmSync.SyncPayload<{
                atom: Charm.Atom<CharacterInfo | undefined>
            }>[]

            
            for (const payload of payloads) {
                if (payload.type === "init") {
                    const data = player.Character? payload.data.atom?.get(player.Character) : undefined
                    if (data === undefined) {continue}
                    payload_to_sync.push(
                         {
                             type: "init",
                             data: {atom: data}
                         }
                     )
                } else if (payload.type === "patch") {
                    const data = payload.data.atom
                    if (data === undefined) {continue}
                    const char_data = player.Character? data.get(player.Character) : undefined
                    if (char_data === undefined) {continue}
                    
                    payload_to_sync.push(
                        {
                            type: "patch",
                            data: {atom: char_data as never}
                        }
                    )
                }
            }
            
            print(payload_to_sync)
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