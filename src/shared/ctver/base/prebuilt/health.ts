import { Stat } from "../components/stat";
import { UpdateRate } from "shared/ctver/utility/enums";

export class HealthStat extends Stat {
	UniqueKey: string = "Health";

	PropertyToAffect: ExtractKeys<WritableInstanceProperties<Humanoid>, number> = "Health";
	public UpdateRate: UpdateRate = UpdateRate.EveryXSeconds;
	protected UpdateEvery: number = 1;
}
