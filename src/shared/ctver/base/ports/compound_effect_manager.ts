import { CompoundEffect } from "../components/compound_effect";
import { Port } from "../../core/port";
import { Replicable } from "shared/ctver/utility/_ts_only/interfaces";

export class CompoundEffectManager extends Port<[CompoundEffect]> {
	AttachableComponentsKeys: string[] = ["CompoundEffect"];
	Key: string = "CompoundEffectManager";
}
