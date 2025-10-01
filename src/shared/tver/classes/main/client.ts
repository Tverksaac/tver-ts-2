import CharmSync from "@rbxts/charm-sync"
import { ClientEvents } from "shared/tver/network/networking"
import { client_atom } from "shared/tver/utility/shared"
import { is_client_context } from "shared/tver/utility/utils"
import { Character } from "../objects/character"
import { subscribe } from "@rbxts/charm"

let client_activated = false

class Client {
    private isActive = false

    constructor () {}

    public Start() {
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