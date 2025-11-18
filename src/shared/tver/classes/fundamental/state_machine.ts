//!native
import Signal from "@rbxts/signal"

/** Helper union of valid states from provided tuple. */
type StatesUnion<T extends string[]> = T[number]


/**
 * Minimal state machine with previous-state tracking and signal emission.
 */
export class StateMachine<States extends string[]> {
    private _state?: StatesUnion<States>
    private _prev_state?: StatesUnion<States>

    public readonly StateChanged = new Signal<(new_state: StatesUnion<States>, prev_state: StatesUnion<States> | undefined) => void>();
    
    public SetState(to: StatesUnion<States>): void {
        if (this._state === to) return

        this._prev_state = this._state
        this._state = to

        this.StateChanged.Fire(this._state, this._prev_state)
    }

    public GetState(): StatesUnion<States> | undefined {
        return this._state
    }

    public GetPreviousState(): StatesUnion<States> | undefined {
        return this._prev_state
    }

    public Destroy(): void {
        this.StateChanged.Destroy()
    }
}