import { ConnectedStat, SeparatedStat } from "shared/ctver/fundamental/stat";
import { Stat } from "../components/stat";
import { UpdateRate } from "shared/ctver/utility/enums";

export class HealthStat extends Stat {
	Affects: string = "Health";
	UniqueKey: string = "HealthStat";

	PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number> = "Health";
	public UpdateRate: UpdateRate = UpdateRate.EveryXSeconds;
	protected UpdateEvery: number = 1;
}
