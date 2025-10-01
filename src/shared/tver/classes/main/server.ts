import Charm, { atom, subscribe } from "@rbxts/charm"
import CharmSync from "@rbxts/charm-sync"
import { ClientEvents, ServerEvents } from "shared/tver/network/networking"
import { CharacterInfo } from "shared/tver/utility/_ts_only/interfaces"
import { client_atom } from "shared/tver/utility/shared"
import { is_server_context } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { Players } from "@rbxts/services"

let server_activated = false

class Server {
    private isActive = false

    constructor () {}

    public Start() {
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