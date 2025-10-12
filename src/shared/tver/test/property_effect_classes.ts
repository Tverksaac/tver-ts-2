import { StrictPropertyEffect } from "../classes/core/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
    public Strength: boolean;

    constructor (_str: boolean) {
        super("AutoRotate")

        this.Strength = _str
        
        this.OnClientEnd = () => {
            print("ended")
        }
    }
}