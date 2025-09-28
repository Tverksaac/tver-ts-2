import { Timer } from "@rbxts/timer"
import { EffectState } from "shared/tver/utility/_ts_only/types"

export abstract class Effect {
    public abstract readonly Affects: unknown
    public abstract readonly Duration: number
    public abstract readonly Strength: unknown

    private readonly _timer = new Timer(0)

    private _state: EffectState = "Ready"

    protected OnClientStart?: () => void = () => {}
    protected OnServerStart?: () => void = () => {}
    protected OnClientEnd?: () => void = () => {}
    protected OnServerEnd?: () => void = () => {}

    constructor () {}

    public GetTimeLeft() {
        return this._timer.getTimeLeft()
    }
    public IsActive() {
        return this._state !== "Ended" && this._state !== "Ready"
    }
    public GetState() {
        return this._state
    }

    public Start() {
        if (this.IsActive()) {
            warn(this + " already was started!")
            return
        }

        this._state = "On"

        this._timer.setLength(this.Duration)
        this._timer.start()
    }
    public Resume() {
        if (!this.IsActive()) {
            warn(this + " is not active, cant resume!")
            return
        }

        this._state = "On"

        this._timer.resume()
    }
    public Stop() {
        if (!this.IsActive()) {
            warn(this + "is not active, cant be stopped!")
            return
        }

        this._state = "Off"

        this._timer.pause()
    }
    public End() {
        if (!this.IsActive()) {
            warn(this + " is not active, cant end!")
        }

        this._state = "Ended"

        this._timer.stop()
    }
}