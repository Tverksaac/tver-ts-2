import { ConnectedStat, SeparatedStat } from "shared/ctver/fundamental/stat";
import { Stat } from "../components/stat";

export class HealthStat extends Stat {
	Affects: string = "Health";
	UniqueKey: string = "HealthStat";
	ConnectedStat = new SeparatedStat("Health", 300);
}
