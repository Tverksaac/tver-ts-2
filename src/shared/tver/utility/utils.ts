import { RunService } from "@rbxts/services"
import { Client, Server } from "../exports"

export function map_to_array<K extends defined, V extends defined>(map: Map<K, V>): V[] {
    const array : V[] = []

    map.forEach((value) => {
        array.push(value)
    })

    return array
}
export function is_client_context(): boolean {
    return RunService.IsClient()
}
export function is_server_context(): boolean {
    return RunService.IsServer()
}

export function setup_humanoid(into: Instance): Humanoid {
    const humanoid = new Instance("Humanoid")

    humanoid.Parent = into
    
    return humanoid
}

//id generator
let id = 0
export function get_id() {
    id++
    return id
}

//Handler getter
let handler: Server | Client
export function set_handler(new_handler: Server | Client) {
    handler = new_handler
}
export function get_handler(): Server | Client | undefined {
    return handler
}