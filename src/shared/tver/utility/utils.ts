import { RunService } from "@rbxts/services"

export function map_to_array<K extends defined, V extends defined>(map: Map<K, V>): V[] {
    const array : V[] = []

    map.forEach((value) => {
        array.push(value)
    })

    return array
}
export function is_client_context() {
    return RunService.IsClient()
}

//id generator
let id = 0
export function get_id() {
    id++
    return id
}