import Signal from "@rbxts/signal";
import { array_to_string, get_id, get_logger, loggers } from "../utility/util";
import { Component } from "./component";
import { Character } from "./character";

const LOG_KEY = "PORT";

const log = get_logger(LOG_KEY, false);
const dlog = get_logger(LOG_KEY, true);

export abstract class Port<AttachableComponents extends Component[]> {
	public Id: number = get_id();
	public Host: Character;

	abstract Key: string;

	abstract AttachableComponentsKeys: string[];

	private _attached_components: AttachableComponents[number][] = [];

	public OnComponentAttached = new Signal<(ComponentAttached: AttachableComponents[number]) => void>();
	public OnComponentDetaching = new Signal<(ComponentDetached: AttachableComponents[number]) => void>();

	constructor(NewHost: Character) {
		this.Host = NewHost;
	}

	public AttachComponent<CMP extends AttachableComponents[number]>(cmp: CMP): void {
		if (!this.AttachableComponentsKeys.includes(cmp.Key)) {
			log.w(
				`Can not attach "${cmp.Key}" to the port which can only take "${array_to_string(this.AttachableComponentsKeys)}"`,
			);
			return;
		}

		if (cmp.AttachCondition(this) && this.AttachCondition(cmp)) {
			this._attached_components.push(cmp);
			this.OnComponentAttached.Fire(cmp);
		} else {
			dlog.w(`${cmp.Key}_${cmp.Id} was not attached, because conditions was not met`);
		}
	}
	public DetachComponent(id: number): void {
		this._attached_components.forEach((cmp, idx) => {
			if (cmp.Id == id) {
				this.OnComponentDetaching.Fire(cmp);
				this._attached_components.remove(idx);
				return;
			}
		});
	}

	public ListAttachedComponents(): AttachableComponents[number][] {
		return this._attached_components;
	}

	public GetComponent(key: string): AttachableComponents[number] | undefined {
		this._attached_components.forEach((cmp) => {
			if (cmp.Key == key) {
				return cmp;
			}
		});
		return undefined;
	}

	/**
	 * @override
	 */
	public AttachCondition(cmp: Component): boolean {
		return true;
	}

	public Destroy(): void {}
}
