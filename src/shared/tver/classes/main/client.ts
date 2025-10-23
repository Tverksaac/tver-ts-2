import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { get_logger, is_client_context, set_handler } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { observe, subscribe } from "@rbxts/charm"
import { Handler } from "../core/handler"

const LOG_KEY = "[CLIENT]"
const log = get_logger(LOG_KEY)
const dlog = get_logger(LOG_KEY, true)

let client_activated = false

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

    public Start() {
        if (this.Active) {
            warn(this + " Cant be Started twice!")
            return
        }

        this.Load()

        this.start_replication()

        ClientEvents.sync.connect((payloads) => {
            this.syncer.sync(...payloads)
        })
        
        ClientEvents.request_sync.fire()

        this.Active = true
        log.w("Client Was Succesfully Started")
    }   

    private start_replication() {
        let character: Character | undefined

        subscribe(client_atom, (state) => {
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