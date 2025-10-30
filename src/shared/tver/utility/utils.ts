import { Players, RunService } from "@rbxts/services"
import { Client, Server } from "../exports"
import { __DEBUG__ } from ".."

/** Convert a Map's values to an array. */
export function map_to_array<K extends defined, V extends defined>(map: Map<K, V>): V[] {
    const array : V[] = []

    map.forEach((value) => {
        array.push(value)
    })

    return array
}
/** True if running on client. */
export function is_client_context(): boolean {
    return RunService.IsClient()
}
/** True if running on server. */
export function is_server_context(): boolean {
    return RunService.IsServer()
}
/** Convenience label for current context. */
export function get_context_name(): "Server" | "Client" {
    return is_client_context()? "Client" : "Server"
}

/**
 * Create and parent a Humanoid/Animator into the instance; optionally applies player description.
 */
export function setup_humanoid(into: Instance): Humanoid {
    const player = Players.GetPlayerFromCharacter(into)
    const humanoid = new Instance("Humanoid")
    const animator = new Instance("Animator")
    const description = player? Players.GetHumanoidDescriptionFromUserId(player.UserId) : undefined

    humanoid.Parent = into
    animator.Parent = humanoid

    humanoid.RigType = !into.FindFirstChild("UpperTorso") && Enum.HumanoidRigType.R6|| Enum.HumanoidRigType.R15

    if (description) {
        humanoid.ApplyDescriptionReset(description)
    }
    
    return humanoid
}

// id generator
let id = 0
export function get_id(): number {
    id++
    return id
}

// Handler getter
let handler: Server | Client
export function set_handler(new_handler: Server | Client): void {
    handler = new_handler
}
export function get_handler(): Server | Client | undefined {
    return handler
}

//Output
const LOG_KEY = "[TVER]"

export function log(text: unknown): true {
    print(LOG_KEY + text)
    return true
}

export function wlog(text: unknown): true {
    warn(LOG_KEY + text)
    return true
}

export function elog(text: unknown) {
    return error(LOG_KEY + text + "\n" + "TRACEBACK: " + debug.traceback())
}

export function dlog(text: unknown) {
    if (__DEBUG__) log(text)
}

export function dwlog(text: unknown) {
    if (__DEBUG__) wlog(text)
}

export function delog(text: unknown) {
    if (__DEBUG__) elog(text)
}

export function get_logger(logger_key: string, debug = false) {
    const key = logger_key + (debug? "[DEBUG]: " : ": ")
    return {
        l: (text: unknown) => {!debug? log(key + text) : dlog(key + text)},
        w: (text: unknown) => {!debug? wlog(key + text) : dwlog(key + text)},
        e: (text: unknown) => {!debug? elog(key + text) : delog(key + text)},
        r: (text: unknown) => (print(key, text))
    }
}