import Charm, { Atom, atom, effect, subscribe } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { get_logger, get_node, is_server_context, set_node } from "shared/tver/utility/utils"
import { Node } from "../core/node"
import { Manipulator } from "shared/tver/classes/main/manipulator"

const LOG_KEY = "[SERVER]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

let server_activated = false

/**
 * Server-side handler responsible for syncing character atoms to clients.
 */
export class Server extends Node {
    public Active = false

    public atom = atom<Map<Instance, CharacterInfo>>(new Map())
    private syncer = CharmSync.server(
        {
            atoms: {atom: this.atom}
        }
    )

    constructor () {
        super()
        set_node(this)
        
        new Manipulator().server_initialize()
    }

    /** Start the server handler and set up syncing. */
    public Start(): void {
        if (this.Active) {
            log.w(`${this} cannot be started twice!`)
            return
        }

        this.Load()

        ServerEvents.request_sync.connect((player) => {
            dlog.l('Hydrating: ' + player)
            this.syncer.hydrate(player)
        })

        this.syncer.connect((player, ...payloads) => {
            const payload_to_sync = [] as CharmSync.SyncPayload<{
                atom: Charm.Atom<CharacterInfo | undefined>
            }>[]

            for (const payload of payloads) {
                if (payload.type === "init") {
                    const data = player.Character? payload.data.atom?.get(player.Character): undefined
                    payload_to_sync.push(
                         {
                             type: "init",
                             data: {atom: data}
                         }
                     )
                } else if (payload.type === "patch") {
                    const data = payload.data.atom
                    if (data === undefined) {continue}
                    const char_data = player.Character? data.get(player.Character): undefined
                    if (char_data === undefined) {continue}
                    
                    payload_to_sync.push(
                        {
                            type: "patch",
                            data: {atom: char_data as never}
                        }
                    )
                }
            }
            ServerEvents.sync.fire(player, payload_to_sync)
        })

        this.Active = true
        log.w("Successfully Started")
    }
}

export function CreateServer(): Server {
    if (!is_server_context()) {
        log.e("Server can be only created on Server Side!")
    }
    if (server_activated) {
        log.w("Server cannot be created twice!")
        return get_node() as Server
    }

    server_activated = true
    return new Server()
}