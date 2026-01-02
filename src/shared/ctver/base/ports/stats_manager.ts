import { Stat } from "../components/stats";
import { Port } from "../../core/port";

export class StatsManager extends Port<[Stat]> {
	AttachableComponentsKeys: string[] = ["Stats"];
	Key: string = "StatManager";
}
