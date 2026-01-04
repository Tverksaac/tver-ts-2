import { Stat } from "../components/stat";
import { Port } from "../../core/port";
import { Component } from "shared/ctver/core/component";

export class StatsManager extends Port<[Stat]> {
	AttachableComponentsKeys: string[] = ["Stat"];
	Key: string = "StatManager";

	public AddStat<NewStat extends Stat>(ctor: new (port: Port<Component[]>) => NewStat): NewStat | undefined {
		return this.AttachComponent(ctor);
	}
	public GetStat(UniqueKey: string): Stat | undefined {
		return this.GetComponentByUniqueKey(UniqueKey);
	}
}
