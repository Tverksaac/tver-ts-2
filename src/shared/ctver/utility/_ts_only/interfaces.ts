import { ReplciationRate } from "../enums";

export interface Replicable {
	ReplicationRate: ReplciationRate;
	GetReplicationState: unknown;
}
