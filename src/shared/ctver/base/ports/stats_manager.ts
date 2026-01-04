import { Stat } from "../components/stat";
import { Port } from "../../core/port";
import { HealthStat } from "../prebuilt/health";

export class StatsManager extends Port<[Stat]> {
	AttachableComponentsKeys: string[] = ["Stat"];
	Key: string = "StatManager";

	public AddStat(name: string) {
		this.AttachComponent(HealthStat);
	}
}
