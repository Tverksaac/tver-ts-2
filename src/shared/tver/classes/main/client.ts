import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { get_handler, get_logger, is_client_context, set_handler } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { subscribe } from "@rbxts/charm"
import { Handler } from "../core/handler"

const LOG_KEY = "[CLIENT]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

let client_activated = false

/**
 * Client-side handler that mirrors server atom and spawns local `Character`.
 */
export class Client extends Handler {
    public Active = false;

    private syncer = CharmSync.client(
        {
            atoms: {atom: client_atom}
        }
    )

    constructor () {
        super()
        set_handler(this)
    }

    /** Start the client handler and set up syncing/replication. */
    public Start(): void {
        if (this.Active) {
            log.w(`${this} cannot be started twice!`)
            return
        }

        this.Load()

        this.start_replication()

        ClientEvents.sync.connect((payloads) => {
            this.syncer.sync(...payloads)
        })
        
        ClientEvents.request_sync.fire()

        this.Active = true
        log.w("Successfully Started")
    }   

    private start_replication(): void {
        let character: Character | undefined

        subscribe(client_atom, (state) => {
            if (!character && state) {
                character = new Character(state.instance)
            } else if (!state) {
                character?.Destroy()
            } else {
                log.w("um what")
            }
        })
    }
}

export function CreateClient(): Client {
    if (!is_client_context()) {
        log.e("Client can be only created on Client Side!")
    }
    if (client_activated) {
        log.w("Client already created")
        return get_handler() as Client
    }

    client_activated = true
    return new Client()
}