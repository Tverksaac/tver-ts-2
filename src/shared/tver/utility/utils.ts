import { Players, RunService } from "@rbxts/services"
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

//Output
const LOG_KEY = "[TVER]: "

export function log(text: string): true {
    print(LOG_KEY + text)
    return true
}

export function wlog(text: string): true {
    warn(LOG_KEY + text)
    return true
}

export function elog(text: string) {
    return error(LOG_KEY + text + "\n" + debug.traceback())
}