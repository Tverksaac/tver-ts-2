import { Timer } from "@rbxts/timer"

export abstract class Effect {
    public abstract readonly Affects: unknown
    public abstract readonly Duration: number
    public abstract readonly Strength: unknown

    public readonly _timer = new Timer(0)

    protected OnClientStart?: () => void = () => {}
    protected OnServerStart?: () => void = () => {}
    protected OnClientEnd?: () => void = () => {}
    protected OnServerEnd?: () => void = () => {}

    constructor () {}

    public GetTimeLeft() {
        return this._timer.getTimeLeft()
    }
}