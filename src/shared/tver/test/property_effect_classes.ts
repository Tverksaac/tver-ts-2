import { CustomPropertyEffect, StrictPropertyEffect } from "../classes/core/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
    public readonly Affects = "AutoRotate" as const
    public readonly Strength: boolean;
    public readonly Priority?: number | undefined;
    
    constructor (_str: boolean, pr: number) {
        super()

        this.Strength = _str
        this.Priority = pr
    }
}

export class Test extends CustomPropertyEffect {
    public Affects: string = "Test" as const
    public Strength: boolean = true
    public Priority?: number | undefined = 1

    constructor () {
        super()
    }
}