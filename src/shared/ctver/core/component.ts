import { UpdateRate } from "../utility/enums";
import { get_id } from "../utility/util";
import { Character } from "./character";
import { Port } from "./port";

export abstract class Component {
	public readonly Id: number = get_id();

	public readonly Port: Port<Component[]>;

	abstract readonly Key: string;
	abstract readonly UniqueKey: string;

	public readonly UpdateRate: UpdateRate = UpdateRate.Heartbeat;
	protected UpdateEvery: number = 1;

	constructor(ConnectToPort: Port<Component[]>) {
		this.Port = ConnectToPort;
	}

	public abstract OnAttach(): void;
	public abstract OnDetach(): void;

	public Update(): void {
		this.UpdateCallback();
	}
	/**
	 * @override
	 */
	protected abstract UpdateCallback(): void;

	abstract GetState(): unknown;

	public AttachCondition(attaching_to: Port<Component[]>): boolean {
		return true;
	}
	public Host(): Character {
		return this.Port.Host;
	}

	public Destroy(): void {}
}
