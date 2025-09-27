import { Timer } from "@rbxts/timer"

export abstract class Effect {
    public abstract readonly affects: unknown
    public abstract readonly duration: number
    public abstract readonly strength: unknown

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