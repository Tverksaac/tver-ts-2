import { StrictPropertyEffect } from "../classes/core/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
    public Strength: boolean;
    public Priority?: number | undefined;
    
    constructor (_str: boolean, pr: number) {
        super("AutoRotate")

        this.Strength = _str
        this.Priority = pr
    }
}