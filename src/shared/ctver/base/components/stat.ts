import { Component } from "../../core/component";
import { Replicable } from "shared/ctver/utility/_ts_only/interfaces";
import { ReplciationRate } from "shared/ctver/utility/enums";

type StatReturns = {};

export abstract class Stat extends Component implements Replicable {
	Key: string = "Stat";

	ReplicationRate: ReplciationRate = ReplciationRate.Heartbeat;
	GetReplicationState: unknown;

	OnAttach(): void {
		this.Port.Host.GetPort("StatManager").GetStat("Health")?.GetState();
	}
	OnDetach(): void {}
	Update(): void {}
	GetState(): StatReturns {
		return {};
	}
}
