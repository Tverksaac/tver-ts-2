import { get_id } from "../utility/util";
import { Port } from "./port";

export enum UpdateRateEnum {
	Tick,
	Custom,
}

export abstract class Component {
	public Id: number = get_id();

	public readonly Port: Port<Component[]>;

	abstract Key: string;
	abstract UniqueKey: string;
	abstract UpdateRate: UpdateRateEnum;

	constructor(ConnectToPort: Port<Component[]>) {
		this.Port = ConnectToPort;
	}

	abstract OnAttach(): void;
	abstract OnDetach(): void;
	abstract Update(): void;

	abstract GetState(): unknown;

	public AttachCondition(attaching_to: Port<Component[]>): boolean {
		return true;
	}

	public Destroy(): void {}
}
