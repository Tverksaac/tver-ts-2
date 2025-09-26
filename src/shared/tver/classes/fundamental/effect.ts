import { Timer } from "@rbxts/timer"

export abstract class Effect {
    public abstract readonly affect: string
    public abstract readonly duration: number
    public abstract readonly strength: unknown

    public readonly _timer = new Timer(0)

    public abstract OnClientStart: () => {}
    public abstract OnServerStart: () => {}
    public abstract OnClientEnd: () => {}
    public abstract OnServerEnd: () => {}

    constructor () {}

    public GetTimeLeft() {
        return this._timer.getTimeLeft()
    }
}