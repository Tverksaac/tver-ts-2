import { StrictPropertyEffect } from "../classes/intermediate/property_effect";

export class AutoRotateEffect extends StrictPropertyEffect<Humanoid, "AutoRotate"> {
    public Duration: number;
    public Strength: boolean;

    constructor (_str: boolean, _dur: number) {
        super("AutoRotate")

        this.Duration = _dur
        this.Strength = _str
        
        this.OnClientEnd = () => {
            print("ended")
        }
    }
}