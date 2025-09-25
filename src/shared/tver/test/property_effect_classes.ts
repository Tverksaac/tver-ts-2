import { StrictPropertyEffect } from "../classes/fundamental/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
    public duration: number;
    public strength: boolean;

    constructor (_str: boolean, _dur: number) {
        super("AutoRotate")

        this.duration = _dur
        this.strength = _str
    }
}