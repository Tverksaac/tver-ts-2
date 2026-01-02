import { CompoundEffect } from "../components/compound_effect";
import { Port } from "../../core/port";

export class CompoundEffectManager extends Port<[CompoundEffect]> {
	AttachableComponentsKeys: string[] = ["CompoundEffect"];
	Key: string = "CompoundEffectManager";
}
