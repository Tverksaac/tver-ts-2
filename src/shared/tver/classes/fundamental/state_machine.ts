import Signal from "@rbxts/signal"

type StatesUnion<T extends string[]> = T[number]

export class StateMachine<States extends string[]> {
    private _state?: StatesUnion<States>

    public readonly StateChanged = new Signal<(new_state: StatesUnion<States>, prev_state: StatesUnion<States> | undefined) => void>();
    
    constructor() {
    }

    public SetState(to: StatesUnion<States>) {
        if (this._state === to) return

        const prev = this._state
        this._state = to

        this.StateChanged.Fire(this._state, prev)
    }

    public GetState() {
        return this._state
    }

    public Destroy() {
        this.StateChanged.Destroy()
    }
}