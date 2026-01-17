import { Stat } from "../components/stat";
import { Port } from "../../core/port";
import { Component } from "shared/ctver/core/component";
import { HealthStat } from "../prebuilt/health";
import { get_logger } from "shared/ctver/utility/util";

const LOG_KEY = "StatsManager";

const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

export class StatsManager extends Port<[Stat]> {
	AttachableComponentsKeys: string[] = ["Stat"];
	Key: string = "StatManager";

	public AddStat<NewStat extends Stat>(ctor: new (port: Port<Component[]>) => NewStat): NewStat | undefined {
		return this.AttachComponent(ctor);
	}
	public RemoveStat(UniqueKey: string): void {
		const id = this.GetComponentByUniqueKey(UniqueKey)?.Id;
		id ? this.DetachComponent(id) : log.w(`Component with key ${UniqueKey} was not found`);
	}
	public GetStat(UniqueKey: string): Stat | undefined {
		return this.GetComponentByUniqueKey(UniqueKey);
	}
	public OnConstruct() {
		this.AddStat(Stat.Factory("MaxHealth"));
		this.AddStat(Stat.Factory("Health"));
		this.AddStat(Stat.Factory("WalkSpeed"));
		this.AddStat(Stat.Factory("JumpHeight"));
	}
}
