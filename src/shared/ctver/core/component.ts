import { possible_dict_keys } from "../utility/_ts_only/types";
import { UpdateRate } from "../utility/enums";
import { SPECIAL_KEYS } from "../utility/shared";
import { get_id, get_logger } from "../utility/util";
import { Character } from "./character";
import { Port } from "./port";

const LOG_KEY = "COMPONENT";

const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

type CallbackMap = Map<possible_dict_keys, () => void>;

export abstract class Component {
	public readonly Id: number = get_id();

	public readonly Port: Port<Component[]>;
	public readonly Host: Character;

	abstract readonly Key: string;
	abstract readonly UniqueKey: string;

	public readonly UpdateRate: UpdateRate = UpdateRate.EveryXSeconds;
	protected UpdateEvery: number = 1;

	private _on_attach_callbacks: CallbackMap = new Map();
	private _on_detach_callbacks: CallbackMap = new Map();
	private _on_update_callbacks: CallbackMap = new Map();
	private _attach_conditions: Map<possible_dict_keys, (cmp: Component) => boolean> = new Map();

	constructor(ConnectToPort: Port<Component[]>) {
		this.Port = ConnectToPort;
		this.Host = this.Port.Host;
	}

	private _add_callback_to(map: CallbackMap, key: possible_dict_keys, callback: () => void, override: boolean) {
		if (map.get(key) && !override) {
			log.w(`There is already attach callback with key ${tostring(key)}!`);
			return;
		}
		map.set(key, callback);
	}
	private _remove_callback_from(map: CallbackMap, key: possible_dict_keys) {
		if (!map.get(key)) {
			log.w(`Threres no callback in dictionary with key ${tostring(key)}`);
			return;
		}
		map.delete(key);
	}

	public AddOnAttachCallback(key: possible_dict_keys, callback: () => void, override = false): void {
		this._add_callback_to(this._on_attach_callbacks, key, callback, override);
	}
	public RemoveOnAttachCallback(key: possible_dict_keys): void {
		this._remove_callback_from(this._on_attach_callbacks, key);
	}
	public AddOnDetachCallback(key: possible_dict_keys, callback: () => void, override = false): void {
		this._add_callback_to(this._on_detach_callbacks, key, callback, override);
	}
	public RemoveOnDetachCallback(key: possible_dict_keys): void {
		this._remove_callback_from(this._on_detach_callbacks, key);
	}
	public AddOnUpdateCallback(key: possible_dict_keys, callback: () => void, override = false): void {
		this._add_callback_to(this._on_update_callbacks, key, callback, override);
	}
	public RemoveOnUpdateCallback(key: possible_dict_keys): void {
		this._remove_callback_from(this._on_update_callbacks, key);
	}
	public AddAttachCondition(key: possible_dict_keys, condition: (cmp: Component) => boolean, override = false): void {
		if (this._attach_conditions.get(key) && !override) {
			log.w(`There is already attach callback with key ${tostring(key)}!`);
			return;
		}
		this._attach_conditions.set(key, condition);
	}
	public RemoveAttachCondition(key: possible_dict_keys): void {
		if (!this._attach_conditions.get(key)) {
			log.w(`Threres no callback in dictionary with key ${tostring(key)}`);
			return;
		}
		this._attach_conditions.delete(key);
	}

	private _call_all_callbacks_in_map(map: CallbackMap) {
		map.forEach((callback) => callback());
	}
	private _call_callback_in_by_key(map: CallbackMap, key: possible_dict_keys) {
		if (key === SPECIAL_KEYS.CALL_ALL_CALLBACKS) {
			this._call_all_callbacks_in_map(map);
			return;
		}
		const callback = map.get(key);
		callback ? callback() : log.w(`Theres no callback in dictionary with key ${tostring(key)}`);
	}
	public ManualUpdate(): void {
		if (this.UpdateRate !== UpdateRate.Manual) {
			log.w("Cant update component manually when UpdateRate is not set to Manual!");
			return;
		}
		this._call_all_callbacks_in_map(this._on_update_callbacks);
	}
	public CallOnAttachCallbackWithKey(key: possible_dict_keys) {
		this._call_callback_in_by_key(this._on_attach_callbacks, key);
	}
	public CallOnDetachCallbackWithKey(key: possible_dict_keys) {
		this._call_callback_in_by_key(this._on_detach_callbacks, key);
	}
	public CallOnUpdateCallbackWithKey(key: possible_dict_keys) {
		this._call_callback_in_by_key(this._on_update_callbacks, key);
	}
	public CanBeAttached(): boolean {
		this._attach_conditions.forEach((callback) => {
			if (!callback(this)) {
				return false;
			}
		});
		return true;
	}
	public GetAmountOfAttachConditionsMet(): number {
		let met = 0;
		this._attach_conditions.forEach((callback) => {
			if (callback(this)) {
				met++;
			}
		});
		return met;
	}
	public IsAtLeastXConditionsMet(HowMuchConditionsMet: number): boolean {
		if (this.GetAmountOfAttachConditionsMet() >= HowMuchConditionsMet) {
			return true;
		} else {
			return false;
		}
	}

	/**
	 * @override
	 */
	public OnConstruct(): void {}

	abstract GetState(): unknown;

	public Destroy(): void {}
}
