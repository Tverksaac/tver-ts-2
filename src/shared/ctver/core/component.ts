import { possible_dict_keys } from "../utility/_ts_only/types";
import { UpdateRate } from "../utility/enums";
import { SPECIAL_KEYS } from "../utility/shared";
import { get_id, get_logger } from "../utility/util";
import { Character } from "./character";
import { Port } from "./port";

const LOG_KEY = "COMPONENT";

const log = get_logger(LOG_KEY);
const dlog = get_logger(LOG_KEY, true);

type CallbackDict = { [key: possible_dict_keys]: () => void };

export abstract class Component {
	public readonly Id: number = get_id();

	public readonly Port: Port<Component[]>;
	public readonly Host: Character;

	abstract readonly Key: string;
	abstract readonly UniqueKey: string;

	public readonly UpdateRate: UpdateRate = UpdateRate.Heartbeat;
	protected UpdateEvery: number = 1;

	private _on_attach_callbacks: CallbackDict = {};
	private _on_detach_callbacks: CallbackDict = {};
	private _on_update_callbacks: CallbackDict = {};
	private _attach_conditions: { [key: possible_dict_keys]: (cmp: Component) => boolean } = {};

	constructor(ConnectToPort: Port<Component[]>) {
		this.Port = ConnectToPort;
		this.Host = this.Port.Host;
	}

	private _add_callback_to(dict: CallbackDict, key: possible_dict_keys, callback: () => void, override: boolean) {
		if (dict[key] && !override) {
			log.w(`There is already attach callback with key ${tostring(key)}!`);
			return;
		}
		dict[key] = callback;
	}
	private _remove_callback_from(dict: CallbackDict, key: possible_dict_keys) {
		if (!dict[key]) {
			log.w(`Threres no callback in dictionary with key ${tostring(key)}`);
			return;
		}
		delete dict[key];
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
		if (this._attach_conditions[key] && !override) {
			log.w(`There is already attach callback with key ${tostring(key)}!`);
			return;
		}
		this._attach_conditions[key] = condition;
	}
	public RemoveAttachCondition(key: possible_dict_keys): void {
		if (!this._attach_conditions[key]) {
			log.w(`Threres no callback in dictionary with key ${tostring(key)}`);
			return;
		}
		delete this._attach_conditions[key];
	}

	private _call_all_callbacks_in_dict(dict: { [key: string]: () => void }) {
		for (const key in dict) dict[key]();
	}
	private _call_callback_in_by_key(dict: CallbackDict, key: possible_dict_keys) {
		if (key === SPECIAL_KEYS.CALL_ALL_CALLBACKS) {
			this._call_all_callbacks_in_dict(dict);
			return;
		}
		const callback = dict[key];
		callback ? callback() : log.w(`Theres no callback in dictionary with key ${tostring(key)}`);
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
		for (const key in this._attach_conditions) {
			if (!this._attach_conditions[key](this)) {
				return false;
			}
		}
		return true;
	}
	public GetAmountOfAttachConditionsMet(): number {
		let met = 0;
		for (const key in this._attach_conditions) {
			if (this._attach_conditions[key](this)) {
				met++;
			}
		}
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
