import Charm, { Atom, atom, effect, subscribe } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { get_logger, is_server_context, set_handler } from "shared/tver/utility/utils"
import { Handler } from "../core/handler"

const LOG_KEY = "[SERVER]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

let server_activated = false

export class Server extends Handler {
    public Active = false

    public atom = atom<Map<Instance, CharacterInfo>>(new Map())
    private syncer = CharmSync.server(
        {
            atoms: {atom: this.atom}
        }
    )

    constructor () {
        super()
        set_handler(this)
    }

    public Start() {
        if (this.Active) {
            warn(this + " Cant be Started twice!")
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
                    const data = player.Character? payload.data.atom?.get(player.Character) : undefined
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
            ServerEvents.sync.fire(player, payload_to_sync)
        })

        this.Active = true
        log.w("Succesfully Started")
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